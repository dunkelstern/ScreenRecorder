import os
from collections import OrderedDict
import gi

# we need GStreamer 1.0 and Gtk 3.0
from ScreenRec.gui.V4L2Window import V4L2Window

gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

from ScreenRec.gui.settings.tools import make_settings_page

# fetch available devices
v4l2_devices = []
sys_dir = '/sys/class/video4linux'
for dev in os.listdir(sys_dir):
    if os.path.isdir(os.path.join(sys_dir, dev)):
        name = 'Unknown'
        device = os.path.join('/dev/', dev)
        try:
            with open(os.path.join(sys_dir, dev, 'name')) as fp:
                name = fp.read().strip()
        except:
            pass

        v4l2_devices.append(
            (name, device)
        )

v4l2_formats = [
    ('Motion JPEG', 'image/jpeg'),
    ('YUYV 4:2:2', 'video/x-raw,format=YUYV'),
    ('RGB', 'video/x-raw,format=RGB3'),
    ('BGR', 'video/x-raw,format=BGR3'),
    ('YU12', 'video/x-raw,format=YU12'),
    ('YV12', 'video/x-raw,format=YV12')
]


def make_button_settings_page(config):
    container = Gtk.Grid()

    make_settings_page(
        container,
        config,
        OrderedDict([
            ('title', ('string', config.title)),
            ('device', (v4l2_devices, config.device)),
            ('format', (v4l2_formats, config.format)),
            ('width', ('int', (config.width, 0, 1920*2))),
            ('height', ('int', (config.height, 0, 1080*2))),
            ('framerate', ('int', (config.framerate, 1, 120))),
            ('hwaccel', (V4L2Window.HW_ACCELS, config.hwaccel))
        ])
    )
    return container
