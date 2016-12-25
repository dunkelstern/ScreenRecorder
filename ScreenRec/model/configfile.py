import json
import os
from uuid import uuid4

from .button import ButtonConfig
from .recorder import RecorderConfig
from .stream import StreamConfig
from .audio import AudioConfig


class ConfigFile:

    def __init__(self, path="~/.config/ScreenRecorder/default.json"):
        self.path = os.path.expanduser(path)
        self.buttons = []
        self.rec_settings = None
        self.stream_settings = None
        self.audio_settings = None
        self.load()

    def save(self):
        if not os.path.exists(os.path.dirname(self.path)):
            os.makedirs(os.path.dirname(self.path))
        conf = {
            'buttons': [button.serialize() for button in self.buttons],
            'rec_settings': self.rec_settings.serialize(),
            'stream_settings': self.stream_settings.serialize(),
            'audio_settings': self.audio_settings.serialize()
        }
        json.dump(conf, open(self.path, 'w'), indent=4)

    def load(self):
        self.load_defaults()
        try:
            conf = json.load(open(self.path, 'r'))
            for key, value in conf.items():
                if key == 'buttons':
                    for button in value:
                        self.buttons.append(ButtonConfig().deserialize(button))
                if key == 'rec_settings':
                    self.rec_settings.deserialize(value)
                if key == 'stream_settings':
                    self.stream_settings.deserialize(value)
                if key == 'audio_settings':
                    self.audio_settings.deserialize(value)
        except IOError:
            pass

    def load_defaults(self):
        self.buttons = []
        self.rec_settings = RecorderConfig()
        self.stream_settings = StreamConfig()
        self.audio_settings = AudioConfig()

    def button(self, button_id):
        for button in self.buttons:
            if button.id == button_id:
                return button
        return None

    def remove_button(self, button_id):
        self.buttons = [button for button in self.buttons if button.id != button_id]

    def add_button(self, button_config):
        button_config.id = str(uuid4())
        self.buttons.append(button_config)

config = ConfigFile()
