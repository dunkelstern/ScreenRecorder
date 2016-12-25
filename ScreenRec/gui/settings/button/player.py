from collections import OrderedDict
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

from ScreenRec.gui.settings.tools import make_settings_page
from ScreenRec.gui.PlayerWindow import PlayerWindow


def make_button_settings_page(config):
    container = Gtk.Grid()

    # TODO: missing settings
    # 'auto_play',
    # 'restart_on_deactivate',
    # 'seek_bar',

    make_settings_page(
        container,
        config,
        OrderedDict([
            ('title', ('string', config.title)),
            ('filename', ('filepicker', config.filename)),
            ('hwaccel', (PlayerWindow.HW_ACCELS, config.hwaccel))
        ])
    )
    return container
