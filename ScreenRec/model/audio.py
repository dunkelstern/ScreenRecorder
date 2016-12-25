import platform

from ScreenRec.ScreenRecorder import ScreenRecorder
from .config import Config

default_source = 'None'
if platform.system() == 'Linux':
    # we use pulse audio here
    from pulsectl import Pulse
    with Pulse('ScreenRecorder') as pulse:
        default_source = pulse.server_info().default_source_name


class AudioConfig(Config):

    def __init__(self):
        self.device = default_source
        self.encoder = ScreenRecorder.AUDIO_ENCODERS[0]
        self.samplerate = 44100
        self.channels = 2
        self.bitrate = 128

    def serialize(self):
        return {
            'device': self.device,
            'encoder': self.encoder,
            'samplerate': self.samplerate,
            'channels': self.channels,
            'bitrate': self.bitrate
        }

    def deserialize(self, data):
        self.device = data.get('device', default_source)
        self.encoder = data['encoder'] \
            if 'encoder' in data \
               and data['encoder'] in ScreenRecorder.AUDIO_ENCODERS \
            else ScreenRecorder.AUDIO_ENCODERS[0]
        self.bitrate = int(data.get('bitrate', 128))

        self.samplerate = int(data.get('samplerate', 44100))
        self.channels = int(data.get('channels', 2))
