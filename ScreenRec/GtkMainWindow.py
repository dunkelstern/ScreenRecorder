from datetime import datetime

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, GObject, Gdk, GLib

import multiprocessing as mp

from .V4L2Window import main as v4l2_main
from .MJPEGPipeWindow import main as mjpeg_main
from .RTMPWindow import main as rtmp_main
from .ScreenRecorder import main as record_main


# Control window
class ControlWindow(Gtk.Window):
    def __init__(self, data=None, title="Video recorder"):
        mp.set_start_method('spawn')

        self.recording = False
        self.streaming = False

        self.processes = {}
        self.queues = {}

        # initialize window
        Gtk.Window.__init__(self, title=title)

        # add header bar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = title
        self.set_titlebar(self.header)

        # add record button
        self.record_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="media-record-symbolic")
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

        # video source buttons
        self.box = Gtk.VBox(spacing=10)
        self.add(self.box)

        self.webcam_button = Gtk.Button(label="Webcam")
        self.webcam_button.connect('clicked', self.on_webcam)
        self.box.pack_start(self.webcam_button, True, True, 0)

        self.microscope_button = Gtk.Button(label="Microscope")
        self.microscope_button.connect('clicked', self.on_microscope)
        self.box.pack_start(self.microscope_button, True, True, 0)

        self.rtmp_button = Gtk.Button(label="iPhone")
        self.rtmp_button.connect('clicked', self.on_rtmp)
        self.box.pack_start(self.rtmp_button, True, True, 0)

        # no border
        self.set_border_width(0)

        # show all window elements
        self.show_all()

        # resize the window and disable resizing by user if needed
        # self.set_default_size(320, 240)
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
            self.processes['webcam'] = mp.Process(target=v4l2_main, kwargs={
                'device': '/dev/video0',
                'title': "Webcam",
                'mime': "image/jpeg",
                'width': 1280,
                'height': 720,
                'framerate': 20
            })
            self.processes['webcam'].start()

    def on_microscope(self, sender):
        # Microsope window
        if 'microscope' in self.processes and self.processes['microscope'].is_alive():
            self.queues['microscope'].put('raise')
        else:
            self.queues['microscope'] = mp.Queue()
            # TODO: implement settings page for mjpeg stream
            self.processes['microscope'] = mp.Process(target=mjpeg_main, kwargs={
                'command': 'gphoto2 --stdout --capture-movie',
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
            icon = Gio.ThemedIcon(name="media-record-symbolic")
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
            self.record_button.set_image(image)
        else:
            # start recording
            self.output_path = datetime.now().strftime('~/Capture/cap-%Y-%m-%d_%H:%M:%S.mkv')

            if 'recorder' in self.processes and self.processes['recorder'].is_alive():
                self.processes['recorder'].terminate()

            # TODO: implement settings page for encoder
            self.processes['recorder'] = mp.Process(target=record_main, kwargs={
                'filename': self.output_path,
                'width': 1920,
                'height': 1080,
                'scale_width': None,
                'scale_height': None
            })
            self.processes['recorder'].start()

            self.recording = True
            self.stream_button.set_sensitive(False)
            icon = Gio.ThemedIcon(name="media-playback-stop-symbolic")
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
            icon = Gio.ThemedIcon(name="media-playback-stop-symbolic")
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
            self.stream_button.set_image(image)

    def quit(self, sender, gparam):
        # terminate all other windows
        for process in self.processes.values():
            process.terminate()
        Gtk.main_quit()
