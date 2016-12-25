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
from .PlayerWindow import main as player_main
from ScreenRec.ScreenRecorder import main as record_main
from ScreenRec.model.configfile import config

entrypoints = {
    'v4l2': v4l2_main,
    'mjpeg': mjpeg_main,
    'rtmp': rtmp_main,
    'avf': osxcam_main,
    # 'ks': ks_main,
    'player': player_main
}

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
        del data['id']
        del data['button_type']
        if main:
            self.processes[button.id] = mp.Process(target=main, kwargs=data)
            self.processes[button.id].start()

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

            val = config.rec_settings

            output_path = datetime.now().strftime(val.filename)
            self.processes['recorder'] = mp.Process(target=record_main, kwargs={
                'display': val.screen,
                'encoder': val.encoder,
                'filename': output_path,
                'width': val.width,
                'height': val.height,
                'scale_width': None if int(val.scale_width) == 0 else int(val.scale_width),
                'scale_height': None if int(val.scale_height) == 0 else int(val.scale_height)
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
        self.fill_source_buttons()
        self.config_window = None

    def quit(self, sender, gparam):
        # terminate all other windows
        for process in self.processes.values():
            process.terminate()
        if self.config_window:
            self.config_window.set_visible(False)
        Gtk.main_quit()
