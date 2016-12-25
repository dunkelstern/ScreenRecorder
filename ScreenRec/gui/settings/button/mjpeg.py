from collections import OrderedDict
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

from ScreenRec.gui.settings.tools import make_settings_page
from ScreenRec.gui.MJPEGPipeWindow import MJPEGPipeWindow


def make_button_settings_page(config):
    container = Gtk.Grid()

    make_settings_page(
        container,
        config,
        OrderedDict([
            ('title', ('string', config.title)),
            ('command', ('string', config.command)),
            ('width', ('int', (config.width, 0, 1920*2))),
            ('height', ('int', (config.height, 0, 1080*2))),
            ('hwaccel', (MJPEGPipeWindow.HW_ACCELS, config.hwaccel))
        ])
    )
    return container
