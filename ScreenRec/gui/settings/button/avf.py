from collections import OrderedDict
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

from ScreenRec.gui.settings.tools import make_settings_page


def make_button_settings_page(config):
    container = Gtk.Grid()

    # screen_width = Gdk.Screen.get_default().get_width()
    # screen_height = Gdk.Screen.get_default().get_height()
    #
    # make_settings_page(
    #     container,
    #     config,
    #     size_groups,
    #     OrderedDict([
    #         ('screen', ('int', (config.screen, 0, 16))),
    #         ('encoder', (ScreenRecorder.ENCODERS, config.encoder)),
    #         ('filename', ('filepicker', config.filename)),
    #         ('width', ('int', (config.width, 0, screen_width))),
    #         ('height', ('int', (config.height, 0, screen_height))),
    #         ('scale_width', ('int', (config.scale_width, 0, screen_width))),
    #         ('scale_height', ('int', (config.scale_height, 0, screen_height)))
    #     ])
    # )
    return container
