import platform
import threading
from datetime import datetime

import gi

# we need GStreamer 1.0 and Gtk 3.0
from ScreenRec.gui.SettingsWindow import SettingsWindow

gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

import multiprocessing as mp

from .V4L2Window import main as v4l2_main
from .OSXCamWindow import main as osxcam_main
from .MJPEGPipeWindow import main as mjpeg_main
from .RTMPWindow import main as rtmp_main
from .PlayerWindow import main as player_main
from ScreenRec.ScreenRecorder import main as screenrecord_main, ScreenRecorder
from ScreenRec.AudioRecorder import main as audiorecord_main
from ScreenRec.RTPMuxer import main as mux_main
from ScreenRec.model.configfile import config

entrypoints = {
    'v4l2': v4l2_main,
    'mjpeg': mjpeg_main,
    'rtmp': rtmp_main,
    'avf': osxcam_main,
    # 'ks': ks_main,
    'player': player_main
}

class QueueManager(threading.Thread):

    def __init__(self):
        self.ctx = mp.get_context('spawn')
        self.queue = self.ctx.Queue()
        self.outQueues = {}
        self.processes = {}
        self.process_info = {}
        super().__init__()
        
    def run(self):
        quit = False
        while not quit:
            command = self.queue.get()

            if 'quit' in command:
                print('MainWindow: IPC quitting')
                quit = True
            if 'terminate' in command:
                if command['terminate'] in self.process_info:
                    print('MainWindow: IPC terminating {}'.format(
                        self.process_info[command['terminate']]['main']
                    ))
                self.terminate(command['terminate'])
            if 'execute' in command:
                print('MainWindow: IPC executing {}'.format(
                    command['execute']['main']
                ))
                self.execute(**command['execute'])
            if 'exclusive' in command:
                print('MainWindow: IPC {} going into exclusive mode, terminating screen recorder'.format(
                    command['exclusive']
                ))
                self.terminate('screen_recorder', forget_everything=False)
                self.outQueues[command['exclusive']].put({ 'record': 7655 })
            if 'cooperative' in command:
                rec = self.process_info.get('screen_recorder', None)
                if rec:
                    print('MainWindow: IPC {} resigned exclusive mode, resuming screen recorder'.format(
                        command['cooperative']
                    ))
                    self.outQueues[command['cooperative']].put({ 'stop': True })
                    self.execute('screen_recorder', main=rec['main'], kwargs=rec['kwargs'])

        # terminate all other processes
        for id, process in self.processes.items():
            if process.is_alive():
                print('Sending quit to {}'.format(id))
                self.outQueues[id].put({ 'quit': True })
                process.join()
        for id, process in self.processes.items():
            if process.is_alive():
                print('Force terminating {}'.format(id))
                process.terminate()

    def execute(self, id=None, main=None, kwargs={}):
        if id and main:
            if id in self.processes and self.processes[id].is_alive():
                self.outQueues[id].put({ 'raise': True })
                return
            self.outQueues[id] = self.ctx.Queue()
            kwargs['comm_queues'] = (self.queue, self.outQueues[id])
            self.processes[id] = self.ctx.Process(target=main, kwargs=kwargs)
            self.processes[id].start()
            self.process_info[id] = { 'main': main, 'kwargs': kwargs }

    def terminate(self, id, forget_everything=True):
        if id in self.processes and self.processes[id].is_alive():
            print('Sending quit to {}'.format(id))
            self.outQueues[id].put({ 'quit': True })
            self.processes[id].join()
            # self.processes[id].terminate()
        if forget_everything and id in self.process_info:
            del self.process_info[id]
        if id in self.processes:
            del self.processes[id]


# Control window
class ControlWindow(Gtk.Window):
    def __init__(self):
        self.comm = QueueManager()
        self.comm.start()
        print('Running main window')

        self.recording = False
        self.streaming = False

        self.config_window = None

        # initialize window
        Gtk.Window.__init__(self, title="Screen Recorder")

        # add header bar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = "Screen Recorder"
        self.set_titlebar(self.header)

        # add record button
        self.record_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="media-record")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.record_button.set_image(image)
        self.record_button.connect("clicked", self.on_record)
        self.header.pack_end(self.record_button)

        # add stream button
        # self.stream_button = Gtk.Button()
        # icon = Gio.ThemedIcon(name="internet-radio-new")
        # image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        # self.stream_button.set_image(image)
        # self.stream_button.connect("clicked", self.on_stream)
        # self.header.pack_end(self.stream_button)

        # add config button
        self.config_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="preferences-system")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.config_button.set_image(image)
        self.config_button.connect("clicked", self.on_config)
        self.header.pack_end(self.config_button)

        # video source buttons
        self.box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.VERTICAL)
        self.add(self.box)

        self.fill_source_buttons()

        # no border
        self.set_border_width(0)

        # show all window elements
        self.show_all()

        # resize the window and disable resizing by user if needed
        self.set_resizable(False)

        # on quit run callback to stop pipeline
        self.connect("delete-event", self.quit)

    def __del__(self):
        self.quit()

    def fill_source_buttons(self):
        children = list(self.box.get_children())
        for child in children:
            self.box.remove(child)

        for button in config.buttons:
            gui_button = Gtk.Button(label=button.title)
            gui_button.connect('clicked', self.on_source_button, button)
            self.box.pack_start(gui_button, True, True, 0)

        self.box.show_all()

    def on_source_button(self, sender, button):
        main = entrypoints.get(button.button_type, None)
        data = button.serialize()
        del data['button_type']
        if main:
            self.comm.queue.put({
                'execute': {
                    'id': data['id'],
                    'main': main,
                    'kwargs': data
                }
            })

    def on_record(self, sender):
        if self.recording:
            # stop recording
            self.comm.queue.put({ 'terminate': 'audio_recorder'})
            self.comm.queue.put({ 'terminate': 'screen_recorder'})
            self.comm.queue.put({ 'terminate': 'muxer'})

            self.recording = False
            # self.stream_button.set_sensitive(True)
            icon = Gio.ThemedIcon(name="media-record")
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
            self.record_button.set_image(image)
        else:
            # start recording
            self.comm.queue.put({ 'terminate': 'audio_recorder'})
            self.comm.queue.put({ 'terminate': 'screen_recorder'})
            self.comm.queue.put({ 'terminate': 'muxer'})

            val = config.rec_settings

            output_path = datetime.now().strftime(val.filename)

            self.comm.queue.put({
                'execute': {
                    'id': 'muxer',
                    'main': mux_main,
                    'kwargs': {
                        'filename': output_path,
                        'audio_port': 7654,
                        'video_port': 7655,
                        'audio_codec': config.audio_settings.encoder,
                        'audio_delay': ScreenRecorder.ENCODER_DELAY[val.encoder],
                        'audio_bitrate': config.audio_settings.bitrate
                    }
                }
            })

            self.comm.queue.put({
                'execute': {
                    'id': 'screen_recorder',
                    'main': screenrecord_main,
                    'kwargs': {
                        'display': val.screen,
                        'encoder': val.encoder,
                        'port': 7655,
                        'width': val.width,
                        'height': val.height,
                        'scale_width': None if int(val.scale_width) == 0 else int(val.scale_width),
                        'scale_height': None if int(val.scale_height) == 0 else int(val.scale_height)
                    }
                }
            })

            self.comm.queue.put({
                'execute': {
                    'id': 'audio_recorder',
                    'main': audiorecord_main,
                    'kwargs': {
                        'device': config.audio_settings.device,
                        'port': 7654
                    }
                }
            })

            self.recording = True
            # self.stream_button.set_sensitive(False)
            icon = Gio.ThemedIcon(name="media-playback-stop")
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
            self.record_button.set_image(image)

    def on_stream(self, sender):
        if self.streaming:
            # TODO: stop streaming
            self.streaming = False
            self.record_button.set_sensitive(True)
            icon = Gio.ThemedIcon(name="internet-radio-new")
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
            self.stream_button.set_image(image)
        else:
            # TODO: start streaming
            self.streaming = True
            self.record_button.set_sensitive(False)
            icon = Gio.ThemedIcon(name="media-playback-stop")
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
            self.stream_button.set_image(image)

    def on_config(self, sender):
        if self.config_window:
            self.config_window.present()
        else:
            self.config_window = SettingsWindow(self)
            self.config_window.show_all()

    def on_settings_quit(self):
        self.fill_source_buttons()
        self.config_window = None

    def quit(self, sender, gparam):
        self.comm.queue.put({ 'quit': True })
        self.comm.join()

        if self.config_window:
            self.config_window.set_visible(False)
        Gtk.main_quit()
