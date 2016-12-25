import platform

from ScreenRec.AudioRecorder import AudioRecorder, default_audio_device
from .config import Config

class AudioConfig(Config):

    def __init__(self):
        self.device = default_audio_device
        self.encoder = AudioRecorder.ENCODERS[0]
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
        self.device = data.get('device', default_audio_device)
        self.encoder = data['encoder'] \
            if 'encoder' in data \
               and data['encoder'] in AudioRecorder.ENCODERS \
            else AudioRecorder.ENCODERS[0]
        self.bitrate = int(data.get('bitrate', 128))

        self.samplerate = int(data.get('samplerate', 44100))
        self.channels = int(data.get('channels', 2))
