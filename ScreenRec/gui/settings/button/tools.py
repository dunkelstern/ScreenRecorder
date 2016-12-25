from .v4l2 import make_button_settings_page as v4l2_page
from .rtmp import make_button_settings_page as rtmp_page
from .mjpeg import make_button_settings_page as mjpeg_page
from .avf import make_button_settings_page as avf_page
from .ks import make_button_settings_page as ks_page
from .player import make_button_settings_page as player_page


def make_button_settings_page(config):
    if config.button_type is None:
        raise AttributeError('No button type set')

    if config.button_type == 'v4l2':
        return v4l2_page(config)
    if config.button_type == 'rtmp':
        return rtmp_page(config)
    if config.button_type == 'mjpeg':
        return mjpeg_page(config)
    if config.button_type == 'avf':
        return avf_page(config)
    if config.button_type == 'ks':
        return ks_page(config)
    if config.button_type == 'player':
        return player_page(config)
