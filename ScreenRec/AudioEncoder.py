import platform

available_audio_devices = []
default_audio_device = None

available_encoders = []
if platform.system() == 'Linux':
    available_encoders = [
        'aac',  # using faac
        'mp3',  # using lame
        'opus',
        'speex',
        'vorbis'
    ]
    from pulsectl import Pulse
    with Pulse('ScreenRecorder') as pulse:
        for source in pulse.source_list():
            available_audio_devices.append(
                (source.description, source.name)
            )
        default_audio_device = pulse.server_info().default_source_name
elif platform.system() == 'Darwin':
    available_encoders = [
        'opus',
        'speex'
    ]
elif platform.system() == 'Windows':
    available_encoders = [
        'opus',
        'speex'
    ]