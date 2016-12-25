from collections import OrderedDict

import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

from ScreenRec.model.configfile import config
from .settings.recorder import build_stack_page as recording_config
from .settings.stream import build_stack_page as streaming_config
from .settings.audio import build_stack_page as audio_config
from .settings.buttons import build_stack_page as button_config

# Control window
class SettingsWindow(Gtk.Window):
    def __init__(self, toplevel):
        self.toplevel = toplevel

        # initialize window
        Gtk.Window.__init__(self, title="Settings")

        # add header bar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(False)
        self.header.props.title = "Settings"
        self.set_titlebar(self.header)

        # Close button
        close_button = Gtk.Button('Save')
        close_button.connect('clicked', self.on_close_button)
        context = close_button.get_style_context()
        context.add_class('suggested-action')
        self.header.pack_end(close_button)

        # config stack
        stack_switcher = Gtk.StackSwitcher()
        self.header.set_custom_title(stack_switcher)

        stack = Gtk.Stack()
        stack_switcher.set_stack(stack)
        self.add(stack)

        # config section
        size_group_left = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)
        size_group_right = Gtk.SizeGroup(Gtk.SizeGroupMode.HORIZONTAL)

        # Recording config
        rec_config = recording_config(config.rec_settings, [size_group_left, size_group_right])
        stack.add_titled(rec_config, 'recording_config', 'Recording')

        # Streaming config
        stream_config = streaming_config(config.stream_settings, [size_group_left, size_group_right])
        stack.add_titled(stream_config, 'streaming_config', 'Streaming')

        # Sound device
        aud_config = audio_config(config.audio_settings, [size_group_left, size_group_right])
        stack.add_titled(aud_config, 'audio_config', 'Audio')

        # Buttons
        btn_config = button_config(config, [size_group_left, size_group_right])
        stack.add_titled(btn_config, 'button_config', 'Source Buttons')

        # no border
        self.set_border_width(0)

        # show all window elements
        self.show_all()
        self.set_transient_for(toplevel)
        self.set_modal(True)
        self.set_destroy_with_parent(True)

        # resize the window and disable resizing by user if needed
        self.set_resizable(False)

    def on_close_button(self, sender):
        config.save()
        self.toplevel.on_settings_quit()
        self.destroy()

