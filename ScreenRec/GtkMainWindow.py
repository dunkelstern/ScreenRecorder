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

        # config/execute stack

        main_layout = Gtk.Box(spacing=6, orientation=Gtk.Orientation.VERTICAL)
        main_layout.set_homogeneous(False)
        self.add(main_layout)

        stack_switcher_container = Gtk.HeaderBar()
        stack_switcher = Gtk.StackSwitcher()
        stack_switcher_container.set_custom_title(stack_switcher)
        main_layout.pack_start(stack_switcher_container, True, True, 0)
        #stack_switcher.set_property('halign', Gtk.Align.CENTER)

        stack = Gtk.Stack()
        stack_switcher.set_stack(stack)
        main_layout.pack_start(stack, True, True, 0)

        # video source buttons
        self.box = Gtk.Box(spacing=10, orientation=Gtk.Orientation.VERTICAL)
        stack.add_titled(self.box, 'exec', 'Run')

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

        # config section
        self.build_config_section(stack)
        self.build_recording_config_section(stack)

        # no border
        self.set_border_width(0)

        # show all window elements
        self.show_all()

        # resize the window and disable resizing by user if needed
        self.set_resizable(False)

        # on quit run callback to stop pipeline
        self.connect("delete-event", self.quit)

    def build_config_section(self, stack):
        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        columns.set_homogeneous(False)
        stack.add_titled(columns, 'config', 'Settings')

        # left column, listview with defined buttons
        left_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_column.set_homogeneous(False)
        columns.pack_start(left_column, True, True, 0)

        # listview
        self.list_view = Gtk.TreeView()
        self.list_view.set_size_request(150,300)
        left_column.pack_start(self.list_view, True, True, 0)

        # add / delete buttons
        list_view_buttons = Gtk.ActionBar()
        left_column.pack_start(list_view_buttons, True, True, 0)

        self.remove_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="list-remove")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.remove_button.set_image(image)
        list_view_buttons.pack_start(self.remove_button)

        self.add_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="list-add")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.add_button.set_image(image)
        list_view_buttons.pack_start(self.add_button)

        # config column
        self.type_store = Gtk.ListStore(str)

        right_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        right_column.set_homogeneous(False)
        columns.pack_start(right_column, True, True, 0)
        self.config_type_combobox = Gtk.ComboBox.new_with_model(self.type_store)
        renderer_text = Gtk.CellRendererText()
        self.config_type_combobox.pack_start(renderer_text, True)
        self.config_type_combobox.add_attribute(renderer_text, "text", 0)
        right_column.pack_start(self.config_type_combobox, True, True, 0)

        self.config_stack = Gtk.Stack()
        self.type_store.append(['V4L2 Device'])
        self.build_v4l2_config(self.config_stack)
        self.type_store.append(['MJPEG Pipe'])
        self.build_mjpeg_config(self.config_stack)
        self.type_store.append(['Stream URL'])
        self.build_stream_config(self.config_stack)

        right_column.pack_start(self.config_stack, True, True, 0)

    def build_recording_config_section(self, stack):
        container = Gtk.Grid()
        stack.add_titled(container, 'record', 'Rec Settings')


    def build_v4l2_config(self, stack):
        pass

    def build_mjpeg_config(self, stack):
        pass

    def build_stream_config(self, stack):
        pass

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
