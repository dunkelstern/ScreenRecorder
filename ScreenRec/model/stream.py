from .config import Config

# we need Gtk 3.0
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk

from .config import Config


class StreamConfig(Config):

    def __init__(self):
        from ScreenRec.ScreenRecorder import ScreenRecorder
        self.screen = 0
        self.encoder = ScreenRecorder.ENCODERS[0]
        self.url = 'rtmp://127.0.0.1:1935/live/stream'

        self.bitrate = 2000

        self.width = Gdk.Screen.get_default().get_width()
        self.height = Gdk.Screen.get_default().get_height()

        self.scale_width = 0
        self.scale_height = 0

    def serialize(self):
        return {
            'screen': self.screen,
            'encoder': self.encoder,
            'url': self.url,
            'bitrate': self.bitrate,
            'width': self.width,
            'height': self.height,
            'scale_width': self.scale_width,
            'scale_height': self.scale_height
        }

    def deserialize(self, data):
        from ScreenRec.ScreenRecorder import ScreenRecorder

        self.screen = int(data.get('screen', 0))
        self.encoder = data['encoder'] \
            if 'encoder' in data \
               and data['encoder'] in ScreenRecorder.ENCODERS \
            else ScreenRecorder.ENCODERS[0]
        self.bitrate = int(data.get('bitrate', 2000))

        self.url = 'rtmp://127.0.0.1:1935/live/stream'
        self.url = data.get('url', self.url)

        self.width = Gdk.Screen.get_default().get_width()
        self.width = int(data.get('width', self.width))
        self.height = Gdk.Screen.get_default().get_height()
        self.height = int(data.get('height', self.height))

        self.scale_width = int(data.get('scale_width', 0))
        self.scale_height = int(data.get('scale_height', 0))
