import platform
from collections import OrderedDict
import gi

available_audio_devices = []
if platform.system() == 'Linux':
    from pulsectl import Pulse
    with Pulse('ScreenRecorder') as pulse:
        for source in pulse.source_list():
            available_audio_devices.append(
                (source.description, source.name)
            )

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

from .tools import make_settings_page
from ScreenRec.ScreenRecorder import ScreenRecorder


def build_stack_page(config, size_groups):
    container = Gtk.Grid()
    container.set_column_homogeneous(False)

    make_settings_page(
        container,
        config,
        OrderedDict([
            ('device', [available_audio_devices, config.device]),
            ('encoder', (ScreenRecorder.AUDIO_ENCODERS, config.encoder)),
            ('samplerate', (['8000', '11025', '22050', '44100', '48000', '96000'], str(config.samplerate))),
            ('channels', ('int', (config.channels, 1, 6))),
            ('bitrate', ('int', (config.bitrate, 64, 256)))
        ]),
        size_groups=size_groups
    )
    return container
