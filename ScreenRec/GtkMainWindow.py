import json
import os
from collections import OrderedDict
from datetime import datetime
import platform

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, GObject, Gdk, GLib

import multiprocessing as mp

from .V4L2Window import main as v4l2_main, V4L2Window
from .OSXCamWindow import main as osxcam_main, OSXCamWindow
from .MJPEGPipeWindow import main as mjpeg_main, MJPEPPipeWindow
from .RTMPWindow import main as rtmp_main, RTMPWindow
from .ScreenRecorder import main as record_main
from .ScreenRecorder import ScreenRecorder


# Control window
class ControlWindow(Gtk.Window):
    def __init__(self, data=None, title="Video recorder"):
        mp.set_start_method('spawn')
        self.load_config()

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

        for button in self.button_settings:
            if 'title' not in button or not button['title']:
                continue
            button_widget = Gtk.Button(label=button['title'])
            button_widget.set_name('source_{}'.format(self.button_settings.index(button)))
            button_widget.connect('clicked', self.on_button_clicked)
            self.box.pack_start(button_widget, True, True, 0)

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

    def load_config(self):
        self.button_settings = []
        self.recording_settings = []
        filename = os.path.expanduser('~/.config/ScreenRecorder/default.json')
        if os.path.exists(filename):
            config = json.load(open(filename, 'r'))
            for key, value in config.items():
                setattr(self, key, value)

    def save_config(self):
        filename = os.path.expanduser('~/.config/ScreenRecorder/default.json')
        if not os.path.exists(os.path.dirname(filename)):
            os.makedirs(os.path.dirname(filename))
        config = {}
        config['recording_settings'] = getattr(self, 'recording_settings', {})
        config['button_settings'] = getattr(self, 'button_settings', [])
        json.dump(config, open(filename, 'w'), indent=4)

    def build_config_section(self, stack):
        columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        columns.set_homogeneous(False)
        stack.add_titled(columns, 'config', 'Settings')

        # left column, listview with defined buttons
        left_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        left_column.set_homogeneous(False)
        columns.pack_start(left_column, True, True, 0)

        # listview
        self.listview_store = Gtk.ListStore(str)
        self.list_view = Gtk.TreeView.new_with_model(self.listview_store)
        self.list_view.set_size_request(150,300)
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Title", renderer, text=0)
        self.list_view.append_column(column)
        self.list_view.connect('cursor-changed', self.on_listview_changed)
        left_column.pack_start(self.list_view, True, True, 0)
        self.populate_listview()
        self.current_item = None

        # add / delete buttons
        list_view_buttons = Gtk.ActionBar()
        left_column.pack_start(list_view_buttons, True, True, 0)

        self.remove_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="list-remove")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.remove_button.set_image(image)
        self.remove_button.set_sensitive(False)
        self.remove_button.connect('clicked', self.on_remove_click)
        list_view_buttons.pack_start(self.remove_button)

        self.add_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="list-add")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.add_button.set_image(image)
        self.add_button.connect('clicked', self.on_add_click)
        list_view_buttons.pack_start(self.add_button)

        # config column
        self.type_store = Gtk.ListStore(str)

        self.right_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.right_column.set_homogeneous(False)
        columns.pack_start(self.right_column, True, True, 0)
        self.config_type_combobox = Gtk.ComboBox.new_with_model(self.type_store)
        renderer_text = Gtk.CellRendererText()
        self.config_type_combobox.pack_start(renderer_text, True)
        self.config_type_combobox.add_attribute(renderer_text, "text", 0)
        self.config_type_combobox.set_sensitive(False)
        self.config_type_combobox.connect('changed', self.on_config_type_changed)
        self.right_column.pack_start(self.config_type_combobox, True, True, 0)

        if platform.system() == 'Linux':
            self.type_store.append(['V4L2 Device'])
        if platform.system() == 'Darwin':
            self.type_store.append(['AV Device'])
        self.type_store.append(['MJPEG Pipe'])
        self.type_store.append(['Stream URL'])


    def on_config_type_changed(self, combo):
        id = combo.get_active()
        if id != None:
            model = combo.get_model()
            entry = list(model[id])

            print('combo selected', entry[0])

            visible = self.right_column.get_children()
            if len(visible) > 1:
                self.right_column.remove(visible[1])

            if entry[0] == 'V4L2 Device':
                defaults = self.button_settings.get(self.current_item, None)
                if not defaults or 'title' not in defaults:
                    defaults = {
                        'device': '/dev/video0',
                        'title': "Webcam",
                        'format': "image/jpeg",
                        'width': 1280,
                        'height': 720,
                        'framerate': 20,
                        'hwaccel': V4L2Window.HW_ACCELS[0]
                    }

                page = self.build_v4l2_config(defaults)
                self.right_column.pack_start(page, True, True, 0)
                page.show_all()
            elif entry[0] == 'AV Device':
                pass
            elif entry[0] == 'MJPEG Pipe':
                defaults = self.button_settings.get(self.current_item, None)
                if not defaults or 'title' not in defaults:
                    defaults = {
                        # 'command': 'gphoto2 --stdout --capture-movie',
                        'command': 'gst-launch-1.0 videotestsrc ! video/x-raw,format=I420,width=1056,height=704,framerate=10/1 ! avenc_mjpeg ! jpegparse ! fdsink',
                        'width': 1056,
                        'height': 704,
                        'title': "MJPEG Pipe",
                        'hwaccel': MJPEPPipeWindow.HW_ACCELS[0]
                    }
                page = self.build_mjpeg_config(defaults)
                self.right_column.pack_start(page, True, True, 0)
                page.show_all()
            elif entry[0] == 'Stream URL':
                defaults = self.button_settings.get(self.current_item, None)
                if not defaults or 'title' not in defaults:
                    defaults = {
                        'url': 'rtmp://127.0.0.1:1935/live/stream1',
                        'title': "RTMP Stream",
                        'max_width': int((1920 / 1080) * 1000),
                        'max_height': 1000,
                        'hwaccel': V4L2Window.HW_ACCELS[0]
                    }
                page = self.build_stream_config(defaults)
                self.right_column.pack_start(page, True, True, 0)
                page.show_all()
        self.save_config()

    def populate_listview(self):
        self.listview_store.clear()
        for item in self.button_settings:
            if 'title' not in item or not item['title']:
                continue
            self.listview_store.append([item['title']])

        # TODO: re-select self.current_item

    def on_listview_changed(self, listview):
        listview_model = self.list_view.get_model()
        path, _ = self.list_view.get_cursor()
        print(list(listview_model))
        current_entry = list(listview_model).index(list(listview_model[path])) if path else 0

        print(current_entry, 'old', self.current_item)

        new_entry = current_entry

        if self.current_item != new_entry:
            val = getattr(self, 'button_settings', [])
            val[self.current_item] = getattr(self, 'current_settings', {})
            setattr(self, 'button_settings', val)
            self.save_config()

            self.config_type_combobox.set_sensitive(True)
            # TODO: set combobox to correct value
            # self.config_type_combobox.set_active(self.type_store)
            self.on_config_type_changed(self.config_type_combobox)
        self.current_item = current_entry

    def on_remove_click(self, button):
        pass

    def on_add_click(self, button):
        if len(list(self.listview_store)) == 0:
            self.current_item = 0
        self.listview_store.append(['Unnamed'])
        self.list_view.set_cursor(len(self.listview_store))

    def build_recording_config_section(self, stack):
        container = Gtk.Grid()
        stack.add_titled(container, 'record', 'Rec Settings')

        screen_width = Gdk.Screen.get_default().get_width()
        screen_height = Gdk.Screen.get_default().get_height()
        val = getattr(self, 'recording_settings', {})
        default_screen = val.get('screen', 0)
        default_encoder = val.get('encoder', ScreenRecorder.ENCODERS[0])
        default_file = val.get('filename', '~/Capture/cap-%Y-%m-%d_%H:%M:%S.mkv')
        default_width = val.get('width', screen_width)
        default_height = val.get('height', screen_height)
        default_scale_width = val.get('scale_width', 0)
        default_scale_height = val.get('scale_height', 0)

        self.make_settings_page(container, 'recording_settings',
            OrderedDict([
                ('screen', ('int', (default_screen, 0, 16))),
                ('encoder', (ScreenRecorder.ENCODERS, default_encoder)),
                ('filename', ('filepicker', default_file)),
                ('width', ('int', (default_width, 0, screen_width))),
                ('height', ('int', (default_height, 0, screen_height))),
                ('scale_width', ('int', (default_scale_width, 0, screen_width))),
                ('scale_height', ('int', (default_scale_height, 0, screen_height)))
            ])
        )

    def make_settings_page(self, container, name, layout):
        container.set_row_spacing(10)
        container.set_column_spacing(10)
        container.set_column_homogeneous(True)
        container.set_border_width(10)

        val = getattr(self, name, {})

        last_item = None
        for setting, (setting_type, default) in layout.items():
            label = Gtk.Label(setting.replace("_", " ").title())
            label.set_halign(Gtk.Align.START)
            container.attach_next_to(label, last_item, Gtk.PositionType.BOTTOM, 1, 1)

            if isinstance(setting_type, list):
                # combobox
                list_store = Gtk.ListStore(str)
                combobox = Gtk.ComboBox.new_with_model(list_store)
                renderer_text = Gtk.CellRendererText()
                combobox.pack_start(renderer_text, True)
                combobox.add_attribute(renderer_text, "text", 0)

                for item in setting_type:
                    list_store.append([item])

                try:
                    combobox.set_active(setting_type.index(default))
                except ValueError:
                    combobox.set_active(0)
                combobox.set_name(setting)
                combobox.connect('changed', lambda combo: self.on_combobox_changed(combo, name))
                container.attach_next_to(combobox, label, Gtk.PositionType.RIGHT, 1, 1)
                val[setting] = default
            elif setting_type == 'int':
                # spinner
                adjustment = Gtk.Adjustment(default[0], default[1], default[2], 1, 100, 0)
                spinner = Gtk.SpinButton.new(adjustment, 100, 0)
                spinner.set_value(default[0])
                spinner.set_name(setting)
                spinner.connect('value-changed', lambda spinner: self.on_spinner_changed(spinner, name))
                container.attach_next_to(spinner, label, Gtk.PositionType.RIGHT, 1, 1)
                val[setting] = default[0]
            elif setting_type == 'float':
                # spinner with decimal
                adjustment = Gtk.Adjustment(default[0], default[1], default[2], 1, 100, 0)
                spinner = Gtk.SpinButton.new(adjustment, 100, 2)
                spinner.set_value(default[0])
                spinner.set_name(setting)
                spinner.connect('value-changed', lambda spinner: self.on_spinner_changed(spinner, name))
                container.attach_next_to(spinner, label, Gtk.PositionType.RIGHT, 1, 1)
                val[setting] = default[0]
            elif setting_type == 'string':
                # textbox
                textbox = Gtk.Entry()
                textbox.set_text(default)
                textbox.set_name(setting)
                textbox.connect('changed', lambda textbox: self.on_textbox_changed(textbox, name))
                container.attach_next_to(textbox, label, Gtk.PositionType.RIGHT, 1, 1)
                val[setting] = default
            elif setting_type == 'filepicker':
                # file picker box
                picker = Gtk.Entry.new()
                picker.set_text(default)
                picker.set_name(setting)
                picker.connect('changed', lambda picker: self.on_textbox_changed(picker, name))
                container.attach_next_to(picker, label, Gtk.PositionType.RIGHT, 1, 1)
                val[setting] = default
        setattr(self, name, val)

    def on_spinner_changed(self, spinner, name):
        val = getattr(self, name, {})
        val[spinner.get_name()] = spinner.get_value()
        setattr(self, name, val)
        self.save_config()

    def on_textbox_changed(self, textbox, name):
        val = getattr(self, name, {})
        val[textbox.get_name()] = textbox.get_text()
        setattr(self, name, val)
        self.save_config()

    def on_combobox_changed(self, combo, name):
        id = combo.get_active()
        if id != None:
            model = combo.get_model()
            entry = list(model[id])
            val = getattr(self, name, {})
            val[combo.get_name()] = entry[0]
            setattr(self, name, val)
            self.save_config()

    def build_v4l2_config(self, defaults):
        container = Gtk.Grid()

        screen_width = Gdk.Screen.get_default().get_width()
        screen_height = Gdk.Screen.get_default().get_height()

        setattr(self, 'current_settings', { 'type': 'v4l2' })
        self.make_settings_page(container, 'current_settings',
            OrderedDict([
                ('title', ('string', defaults['title'])),
                ('device', ('filepicker', defaults['device'])),
                ('format', ('string', defaults['format'])),
                ('width', ('int', (defaults['width'], 0, screen_width))),
                ('height', ('int', (defaults['height'], 0, screen_height))),
                ('framerate', ('int', (defaults['framerate'], 1, 120))),
                ('hwaccel', (V4L2Window.HW_ACCELS, defaults['hwaccel']))
            ])
        )
        return container

    def build_mjpeg_config(self, defaults):
        container = Gtk.Grid()

        screen_width = Gdk.Screen.get_default().get_width()
        screen_height = Gdk.Screen.get_default().get_height()

        setattr(self, 'current_settings', { 'type': 'mjpeg' })
        self.make_settings_page(container, 'current_settings',
            OrderedDict([
                ('title', ('string', defaults['title'])),
                ('command', ('string', defaults['command'])),
                ('width', ('int', (defaults['width'], 0, screen_width))),
                ('height', ('int', (defaults['height'], 0, screen_height))),
                ('hwaccel', (MJPEPPipeWindow.HW_ACCELS, defaults['hwaccel']))
            ])
        )
        return container

    def build_stream_config(self, defaults):
        container = Gtk.Grid()

        screen_width = Gdk.Screen.get_default().get_width()
        screen_height = Gdk.Screen.get_default().get_height()

        setattr(self, 'current_settings', { 'type': 'stream' })
        self.make_settings_page(container, 'current_settings',
            OrderedDict([
                ('title', ('string', defaults['title'])),
                ('url', ('string', defaults['url'])),
                ('max_width', ('int', (defaults['max_width'], 0, screen_width))),
                ('max_height', ('int', (defaults['max_height'], 0, screen_height))),
                ('hwaccel', (RTMPWindow.HW_ACCELS, defaults['hwaccel']))
            ])
        )
        return container

    def present_window(self, window):
        self.windows[window].set_visible(True)
        self.windows[window].present()

    def on_button_clicked(self, button):
        settings = self.button_settings[button.get_name().replace('source_', '')]
        config = settings
        del config['type']

        start = None
        if settings['type'] == 'v4l2':
            start = v4l2_main
        elif settings['type'] == 'mjpeg':
            start = mjpeg_main
        elif settings['type'] == 'stream':
            start = rtmp_main
        self.processes[button.get_name()] = mp.Process(target=start, kwargs=config)
        self.processes[button.get_name()].start()

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
