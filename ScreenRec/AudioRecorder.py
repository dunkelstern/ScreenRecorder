import argparse
import os, subprocess
import platform

# gi is GObject instrospection
import gi

# we need GStreamer 1.0
gi.require_version('Gst', '1.0')

# Import GStreamer
from gi.repository import Gst, GObject

from ScreenRec.tools import dump_pipeline

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


class AudioRecorder:

    ENCODERS = available_encoders
    DEVICES = available_audio_devices

    def __init__(self, device=None, encoder=None, samplerate=44100, channels=2, bitrate=128, port=None):
        if encoder and encoder not in AudioRecorder.ENCODERS:
            raise NotImplementedError("Encoder '{}' not implemented".format(encoder))

        self.encoder = encoder if encoder else AudioRecorder.ENCODERS[0]
        self.device = device
        if encoder == 'opus':
            self.samplerate = 48000
        else:
            self.samplerate = samplerate
        self.channels = channels
        self.bitrate = bitrate
        self.port = port
        self.build_gst_pipeline(encoder)

    def build_gst_pipeline(self, encoding_method):
        # display src
        src = None

        if platform.system() == 'Linux':
            src = Gst.ElementFactory.make('pulsesrc', 'source')
            src.set_property('device', self.device)
            src.set_property('client-name', 'ScreenRecorder')
        elif platform.system() == 'Darwin':
            src = Gst.ElementFactory.make('avfaudiosrc', 'source')
            # TODO: settings?
        elif platform.system() == 'Windows':
            src = None
            # TODO: Windows

        src.set_property('do-timestamp', True)

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.use_clock(Gst.SystemClock.obtain())

        self.pipeline.add(src)

        print('Using {} encoder, device: {}'.format(encoding_method, self.device))

        # output part of pipeline
        if self.port:
            cap_string = 'audio/x-raw,format=S16BE,rate=44100,channels=2'
        else:
            cap_string = 'audio/x-raw,format=S16LE,rate={},channels={}'.format(
                self.samplerate, self.channels
            )
        caps = Gst.Caps.from_string(cap_string)
        filter = Gst.ElementFactory.make('capsfilter')
        filter.set_property('caps', caps)
        self.pipeline.add(filter)
        src.link(filter)

        encoder = None
        if not self.port:
            # build encoding pipelines
            if encoding_method == 'aac':
                encoder = Gst.ElementFactory.make('faac')
                encoder.set_property('bitrate', self.bitrate * 1000)
            elif encoding_method == 'mp3':
                encoder = Gst.ElementFactory.make('lamemp3enc')
                encoder.set_property('bitrate', self.bitrate)
                encoder.set_property('cbr', True)
            elif encoding_method == 'opus':
                encoder = Gst.ElementFactory.make('opusenc')
                encoder.set_property('bitrate', self.bitrate * 1000)
                encoder.set_property('bitrate-type', 0)  # cbr
            elif encoding_method == 'speex':
                encoder = Gst.ElementFactory.make('speexenc')
                encoder.set_property('bitrate', self.bitrate * 1000)
                encoder.set_property('abr', True)
            elif encoding_method == 'vorbis':
                encoder = Gst.ElementFactory.make('vorbisenc')
                encoder.set_property('bitrate', self.bitrate * 1000)
                encoder.set_property('managed', True)

            self.pipeline.add(encoder)
            filter.link(encoder)

        if self.port:
            payloader = 'rtpL16pay'
            rtp_payload = Gst.ElementFactory.make(payloader)
            self.pipeline.add(rtp_payload)
            filter.link(rtp_payload)

            self.sink = Gst.ElementFactory.make('udpsink')
            self.sink.set_property('sync', False)
            self.sink.set_property('host', '127.0.0.1')
            self.sink.set_property('port', self.port)
            self.pipeline.add(self.sink)
            rtp_payload.link(self.sink)
        else:
            muxer = Gst.ElementFactory.make('matroskamux')
            self.sink = Gst.ElementFactory.make('filesink')

            # add remaining parts
            self.pipeline.add(muxer)
            self.pipeline.add(self.sink)

            # link remaining parts
            encoder.link(muxer)
            muxer.link(self.sink)

        # dump_pipeline(self.pipeline)
        self.create_bus()

    def create_bus(self):
        # create a bus
        self.bus = self.pipeline.get_bus()

        # we want signal watchers
        self.bus.add_signal_watch()

        # on message print errors
        self.bus.connect('message', self.on_message)

    def on_message(self, bus, message):
        t = message.type

        if t == Gst.MessageType.EOS:
            # end of stream, just disable the switch and stop processing
            self.stop()
        if t == Gst.MessageType.ERROR:
            # some error occured, log and stop
            print('ERROR: ', message.parse_error())
            self.stop()

    def start(self, path=None):
        if path:
            path = os.path.expanduser(path)
            self.sink.set_property('location', path)
        self.pipeline.set_state(Gst.State.PLAYING)

        clock = self.pipeline.get_pipeline_clock().get_time()
        print('clock', clock)
        print('latency', self.pipeline.get_latency())
        print('delay', self.pipeline.get_delay())

    def stop(self):
        self.pipeline.set_state(Gst.State.READY)
        self.pipeline.set_state(Gst.State.NULL)


def main(filename=None, port=None, device=None, encoder=None, samplerate=44100, channels=2, bitrate=128):
    if not device:
        raise AttributeError('no device supplied')

    if not filename and not port:
        raise AttributeError('either set filename or port')

    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - AudioCapture for device {}'.format(device))

    # Initialize Gstreamer
    GObject.threads_init()
    mainloop = GObject.MainLoop()
    Gst.init(None)

    # Start audio recorder
    if filename:
        recorder = AudioRecorder(
            device=device,
            encoder=encoder,
            samplerate=samplerate,
            channels=channels,
            bitrate=bitrate
        )
        recorder.start(path=filename)
    else:
        recorder = AudioRecorder(
            device=device,
            port=port
        )
        recorder.start()

    # run the main loop
    try:
        mainloop.run()
    except:
        recorder.stop()
        mainloop.quit()


# if run as script start recording
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Record audio')
    parser.add_argument(
        '-d', '--device',
        type=str,
        nargs=1,
        default=[default_audio_device],
        choices=[d[1] for d in AudioRecorder.DEVICES],
        dest='device',
        help='device to capture'
    )
    parser.add_argument(
        '-e', '--encoder',
        type=str,
        nargs=1,
        dest='encoder',
        default=[AudioRecorder.ENCODERS[0]],
        choices=AudioRecorder.ENCODERS,
        help='encoder to use'
    )
    parser.add_argument(
        '-s', '--samplerate',
        type=int,
        nargs=1,
        dest='samplerate',
        default=44100,
        help='audio samplerate'
    )
    parser.add_argument(
        '-c', '--channels',
        type=int,
        nargs=1,
        dest='channels',
        default=2,
        help='number of channels'
    )
    parser.add_argument(
        '-b', '--bitrate',
        type=int,
        nargs=1,
        dest='bitrate',
        default=128,
        help='audio encoder bitrate'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        nargs=1,
        dest='port',
        default=7654,
        help='do not save to file but stream to port'
    )
    parser.add_argument(
        'filename',
        nargs='*',
        type=str,
        help='output file'
    )
    args = parser.parse_args()

    if args.filename:
        main(
            filename=args.filename[0],
            encoder=args.encoder[0],
            device=args.device[0],
            channels=args.channels,
            samplerate=args.samplerate,
            bitrate=args.bitrate
        )
    else:
        main(
            port=args.port[0],
            encoder=args.encoder[0],
            device=args.device[0],
            channels=args.channels,
            samplerate=args.samplerate,
            bitrate=args.bitrate
        )
