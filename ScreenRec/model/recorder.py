import platform

# we need Gtk 3.0
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gdk

from .config import Config
from ScreenRec.ScreenRecorder import ScreenRecorder


class RecorderConfig(Config):

    def __init__(self):
        self.screen = 0
        self.encoder = ScreenRecorder.ENCODERS[0]
        if platform.system() == 'Linux':
            self.filename = '~/Capture/cap-%Y-%m-%d_%H:%M:%S.mkv'
        else:
            self.filename = '~/Capture/cap-%Y-%m-%d_%H-%M-%S.mkv'

        self.width = Gdk.Screen.get_default().get_width()
        self.height = Gdk.Screen.get_default().get_height()

        self.scale_width = 0
        self.scale_height = 0

    def serialize(self):
        return {
            'screen': self.screen,
            'encoder': self.encoder,
            'filename': self.filename,
            'width': self.width,
            'height': self.height,
            'scale_width': self.scale_width,
            'scale_height': self.scale_height
        }

    def deserialize(self, data):
        self.screen = int(data.get('screen', 0))
        self.encoder = data['encoder'] \
            if 'encoder' in data \
               and data['encoder'] in ScreenRecorder.ENCODERS \
            else ScreenRecorder.ENCODERS[0]

        if platform.system() == 'Linux':
            self.filename = '~/Capture/cap-%Y-%m-%d_%H:%M:%S.mkv'
        else:
            self.filename = '~/Capture/cap-%Y-%m-%d_%H-%M-%S.mkv'
        self.filename = data.get('filename', self.filename)

        self.width = Gdk.Screen.get_default().get_width()
        self.width = int(data.get('width', self.width))
        self.height = Gdk.Screen.get_default().get_height()
        self.height = int(data.get('height', self.height))

        self.scale_width = int(data.get('scale_width', 0))
        self.scale_height = int(data.get('scale_height', 0))