import platform
from .config import Config


available_sources = []
if platform.system() == 'Linux':
    available_sources = [
        ('Video 4 Linux Device', 'v4l2'),
        ('RTMP Stream', 'rtmp'),
        ('MJPEG Pipe', 'mjpeg'),
        ('Video Player', 'player')
    ]
elif platform.system() == 'Darwin':
    available_sources = [
        ('AVFoundation Device', 'avf'),
        ('RTMP Stream', 'rtmp'),
        ('MJPEG Pipe', 'mjpeg'),
        ('Video Player', 'player')
    ]
elif platform.system() == 'Windows':
    available_sources = [
        ('Video device', 'ks'),
        ('RTMP Stream', 'rtmp'),
        ('Video Player', 'player')
    ]


class ButtonConfig(Config):

    VALID_SOURCES = available_sources

    def __init__(self, button_type=None):
        self.id = None
        if button_type is None:
            self.button_type = ButtonConfig.VALID_SOURCES[0][1]
        else:
            self.button_type = button_type
        defaults = ButtonConfig.default_for_type(self.button_type)
        for key, value in defaults.items():
            setattr(self, key, value)

    def serialize(self):
        values = {}
        for key in ButtonConfig.valid_keys(self.button_type):
            values[key] = getattr(self, key, None)
        values['button_type'] = self.button_type
        return values

    def deserialize(self, data):
        button_type = data.get('button_type', None)
        if button_type:
            self.button_type = button_type
        if self.button_type is None:
            raise AttributeError('No button type set')
        for key in ButtonConfig.valid_keys(self.button_type):
            value = data.get(key, None)
            setattr(self, key, value)
        defaults = ButtonConfig.default_for_type(self.button_type)
        for key, value in defaults.items():
            if getattr(self, key, None) is None:
                setattr(self, key, value)
        return self

    @staticmethod
    def valid_keys(button_type):
        keys = ['title', 'id']
        if button_type == 'v4l2':
            keys.extend([
                'device',
                'format',
                'width',
                'height',
                'framerate',
                'hwaccel'
            ])
        if button_type == 'avf':
            keys.extend([
                'device',
                'width',
                'height',
                'framerate'
            ])
        if button_type == 'ks':
            # TODO: windows
            keys.extend([
            ])
        if button_type == 'rtmp':
            keys.extend([
                'url',
                'max_width',
                'max_height',
                'hwaccel'
            ])
        if button_type == 'mjpeg':
            keys.extend([
                'command',
                'width',
                'height',
                'hwaccel'
            ])
        if button_type == 'player':
            keys.extend([
                'filename',
                'auto_play',
                'restart_on_deactivate',
                'seek_bar',
                'hwaccel'
            ])
        return keys

    @staticmethod
    def default_for_type(button_type):
        if button_type == 'v4l2':
            # linux video device
            return {
                'title': "Webcam",
                'device': '/dev/video0',
                'format': "image/jpeg",
                'width': 1280,
                'height': 720,
                'framerate': 30,
                'hwaccel': 'opengl'  # TODO: replace with first from AVAILABLE_HWACCELS
            }
        if button_type == 'avf':
            # mac OS video device
            return {
                'title': "Webcam",
                'device': 0,
                'width': 1280,
                'height': 720,
                'framerate': 30
            }
        if button_type == 'ks':
            # TODO: windows video device
            pass
        if button_type == 'rtmp':
            # rtmp network stream
            return {
                'title': "RTMP Stream",
                'url': 'rtmp://127.0.0.1:1935/live/stream',
                'max_width': 1920,
                'max_height': 1080,
                'hwaccel': 'opengl'  # TODO: replace with first from AVAILABLE_HWACCELS
            }
        if button_type == 'mjpeg':
            # mjpeg pipe input
            return {
                'title': "MJPEG Pipe",
                # 'command': 'gphoto2 --stdout --capture-movie',
                'command': 'gst-launch-1.0 videotestsrc ! video/x-raw,format=I420,width=1056,height=704,framerate=10/1 ! avenc_mjpeg ! jpegparse ! fdsink',
                'width': 1280,
                'height': 720,
                'hwaccel': 'opengl'  # TODO: replace with first from AVAILABLE_HWACCELS
            }
        if button_type == 'player':
            # video player
            return {
                'title': "Video player",
                'filename': '~/Movies/video.mp4',
                'auto_play': False,
                'restart_on_deactivate': True,
                'seek_bar': False,
                'hwaccel': 'opengl'  # TODO: replace with first from AVAILABLE_HWACCELS
            }
        return None
