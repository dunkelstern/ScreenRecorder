import platform
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
from ScreenRec.ScreenRecorder import main as record_main


# Control window
class ControlWindow(Gtk.Window):
    def __init__(self):
        mp.set_start_method('spawn')

        self.recording = False
        self.streaming = False

        self.processes = {}
        self.queues = {}

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
        self.stream_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="internet-radio-new")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.stream_button.set_image(image)
        self.stream_button.connect("clicked", self.on_stream)
        self.header.pack_end(self.stream_button)

        # add config button
        self.config_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="preferences-system")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.config_button.set_image(image)
        self.config_button.connect("clicked", self.on_config)
        self.header.pack_end(self.config_button)

        # video source buttons
        self.box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.VERTICAL)

        # TODO: make dynamic
        self.webcam_button = Gtk.Button(label="Webcam")
        self.webcam_button.connect('clicked', self.on_webcam)
        self.box.pack_start(self.webcam_button, True, True, 0)

        self.microscope_button = Gtk.Button(label="Microscope")
        self.microscope_button.connect('clicked', self.on_microscope)
        self.box.pack_start(self.microscope_button, True, True, 0)

        self.rtmp_button = Gtk.Button(label="iPhone")
        self.rtmp_button.connect('clicked', self.on_rtmp)
        self.box.pack_start(self.rtmp_button, True, True, 0)

        self.add(self.box)

        # no border
        self.set_border_width(0)

        # show all window elements
        self.show_all()

        # resize the window and disable resizing by user if needed
        self.set_resizable(False)

        # on quit run callback to stop pipeline
        self.connect("delete-event", self.quit)

    def present_window(self, window):
        self.windows[window].set_visible(True)
        self.windows[window].present()

    def on_webcam(self, sender):
        # Webcam window
        if 'webcam' in self.processes and self.processes['webcam'].is_alive():
            self.queues['webcam'].put('raise')
        else:
            self.queues['webcam'] = mp.Queue()
            # TODO: implement settings page for webcam
            if platform.system() == 'Linux':
                self.processes['webcam'] = mp.Process(target=v4l2_main, kwargs={
                    'device': '/dev/video0',
                    'title': "Webcam",
                    'mime': "image/jpeg",
                    'width': 1280,
                    'height': 720,
                    'framerate': 30,
                    'hwaccel': 'opengl'
                })
            elif platform.system() == 'Darwin':
                self.processes['webcam'] = mp.Process(target=osxcam_main, kwargs={
                    'device': 0,
                    'title': "Webcam",
                    'width': 1280,
                    'height': 720,
                    'framerate': 25
                })
            elif platform.system() == 'Windows':
                pass
            self.processes['webcam'].start()


    def on_microscope(self, sender):
        # Microsope window
        if 'microscope' in self.processes and self.processes['microscope'].is_alive():
            self.queues['microscope'].put('raise')
        else:
            self.queues['microscope'] = mp.Queue()
            # TODO: implement settings page for mjpeg stream
            self.processes['microscope'] = mp.Process(target=mjpeg_main, kwargs={
                #'command': 'gphoto2 --stdout --capture-movie',
                'command': 'gst-launch-1.0 videotestsrc ! video/x-raw,format=I420,width=1056,height=704,framerate=10/1 ! avenc_mjpeg ! jpegparse ! fdsink',
                'width': 1056,
                'height': 704,
                'title': "Microscope"
            })
            self.processes['microscope'].start()

    def on_rtmp(self, sender):
        # RTMP stream window
        if 'rtmp' in self.processes and self.processes['rtmp'].is_alive():
            self.queues['rtmp'].put('raise')
        else:
            self.queues['rtmp'] = mp.Queue()
            # TODO: implement settings page for rtmp
            self.processes['rtmp'] = mp.Process(target=rtmp_main, kwargs={
                'url': 'rtmp://127.0.0.1:1935/live/stream1',
                'title': "RTMP Stream",
                'max_width': int((1920 / 1080) * 1000),
                'max_height': 1000
            })
            self.processes['rtmp'].start()

    def on_record(self, sender):
        if self.recording:
            # stop recording
            if 'recorder' in self.processes and self.processes['recorder'].is_alive():
                self.processes['recorder'].terminate()
                del self.processes['recorder']

            self.recording = False
            self.stream_button.set_sensitive(True)
            icon = Gio.ThemedIcon(name="media-record")
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
            self.record_button.set_image(image)
        else:
            # start recording

            if 'recorder' in self.processes and self.processes['recorder'].is_alive():
                self.processes['recorder'].terminate()

            val = getattr(self, 'recording_settings')

            output_path = datetime.now().strftime(val['filename'])
            self.processes['recorder'] = mp.Process(target=record_main, kwargs={
                'display': val['screen'],
                'encoder': val['encoder'],
                'filename': output_path,
                'width': val['width'],
                'height': val['height'],
                'scale_width': None if int(val['scale_width']) == 0 else int(val['scale_width']),
                'scale_height': None if int(val['scale_height']) == 0 else int(val['scale_height'])
            })
            self.processes['recorder'].start()

            self.recording = True
            self.stream_button.set_sensitive(False)
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
        self.config_window = None

    def quit(self, sender, gparam):
        # terminate all other windows
        for process in self.processes.values():
            process.terminate()
        if self.config_window:
            self.config_window.set_visible(False)
        Gtk.main_quit()
