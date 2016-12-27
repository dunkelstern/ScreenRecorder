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

available_encoders = []
if platform.system() == 'Linux':
    available_encoders = [
        'aac',  # using faac
        'mp3',  # using lame
        'opus',
        'speex',
        'vorbis'
    ]
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


class RTPMuxer:

    AUDIO_ENCODERS = available_encoders

    def __init__(self, audio_port=7654, video_port=7655, audio_delay=1150, audio_codec=None, audio_bitrate=128):
        self.audio_port = audio_port
        self.video_port = video_port
        self.audio_delay = audio_delay
        self.audio_codec = audio_codec if audio_codec else RTPMuxer.AUDIO_ENCODERS[0]
        self.audio_bitrate = audio_bitrate
        self.build_gst_pipeline()

    def build_gst_pipeline(self):

        audio_src = Gst.ElementFactory.make('udpsrc', 'audiosrc')
        audio_src.set_property('port', self.audio_port)
        audio_src.set_property('reuse', True)
        audio_src.set_property('address', '127.0.0.1')
        audio_src.set_property('do-timestamp', True)

        audio_caps_string = 'application/x-rtp,media=audio,payload=96,clock-rate=44100,encoding-name=L16,encoding-params=2,channels=2'
        depayloader = 'rtpL16depay'

        caps = Gst.Caps.from_string(audio_caps_string)
        audio_filter = Gst.ElementFactory.make('capsfilter')
        audio_filter.set_property('caps', caps)

        audio_jitterbuffer = Gst.ElementFactory.make('rtpjitterbuffer')
        audio_jitterbuffer.set_property('latency', 2000)
        print(self.audio_delay)
        if self.audio_delay != 0:
            audio_jitterbuffer.set_property('ts-offset', self.audio_delay * 1000000)

        audio_depay = Gst.ElementFactory.make(depayloader)
        audio_queue = Gst.ElementFactory.make('queue')
        audio_queue.set_property('max-size-buffers', 200)
        audio_queue.set_property('max-size-bytes', 104857600)  # 10 MB
        audio_queue.set_property('max-size-time', 10000000000)  # 10 sec

        video_src = Gst.ElementFactory.make('udpsrc', 'videosrc')
        video_src.set_property('port', self.video_port)
        video_src.set_property('reuse', True)
        video_src.set_property('address', '127.0.0.1')
        video_src.set_property('do-timestamp', True)

        video_caps_string = 'application/x-rtp,media=video,payload=96,clock-rate=90000,encoding-name=H264,a-framerate=25'
        caps = Gst.Caps.from_string(video_caps_string)
        video_filter = Gst.ElementFactory.make('capsfilter')
        video_filter.set_property('caps', caps)

        video_jitterbuffer = Gst.ElementFactory.make('rtpjitterbuffer')
        video_jitterbuffer.set_property('latency', 2000)

        video_depay = Gst.ElementFactory.make('rtph264depay')
        video_parser = Gst.ElementFactory.make('h264parse')
        video_queue = Gst.ElementFactory.make('queue')
        video_queue.set_property('max-size-buffers', 200)
        video_queue.set_property('max-size-bytes', 104857600)  # 10 MB
        video_queue.set_property('max-size-time', 10000000000)  # 10 sec

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.use_clock(Gst.SystemClock.obtain())
        self.pipeline.add(audio_src)
        self.pipeline.add(audio_filter)
        self.pipeline.add(audio_jitterbuffer)
        self.pipeline.add(audio_depay)
        self.pipeline.add(audio_queue)
        self.pipeline.add(video_src)
        self.pipeline.add(video_filter)
        self.pipeline.add(video_jitterbuffer)
        self.pipeline.add(video_depay)
        self.pipeline.add(video_parser)
        self.pipeline.add(video_queue)
        audio_src.link(audio_filter)
        audio_filter.link(audio_jitterbuffer)
        audio_jitterbuffer.link(audio_depay)
        audio_depay.link(audio_queue)
        video_src.link(video_filter)
        video_filter.link(video_jitterbuffer)
        video_jitterbuffer.link(video_depay)
        video_depay.link(video_parser)
        video_parser.link(video_queue)

        muxer = Gst.ElementFactory.make('matroskamux')
        self.pipeline.add(muxer)

        audio_pad = muxer.get_request_pad('audio_%u')
        video_pad = muxer.get_request_pad('video_%u')
        self.sink = Gst.ElementFactory.make('filesink')
        self.sink.set_property('sync', True)
        self.pipeline.add(self.sink)

        # audio encoder

        # build encoding pipelines
        encoder = None
        if self.audio_codec == 'aac':
            encoder = Gst.ElementFactory.make('faac')
            encoder.set_property('bitrate', self.audio_bitrate * 1000)
        elif self.audio_codec == 'mp3':
            encoder = Gst.ElementFactory.make('lamemp3enc')
            encoder.set_property('bitrate', self.audio_bitrate)
            encoder.set_property('cbr', True)
        elif self.audio_codec == 'opus':
            encoder = Gst.ElementFactory.make('opusenc')
            encoder.set_property('bitrate', self.audio_bitrate * 1000)
            encoder.set_property('bitrate-type', 0)  # cbr
        elif self.audio_codec == 'speex':
            encoder = Gst.ElementFactory.make('speexenc')
            encoder.set_property('bitrate', self.audio_bitrate * 1000)
            encoder.set_property('abr', True)
        elif self.audio_codec == 'vorbis':
            encoder = Gst.ElementFactory.make('vorbisenc')
            encoder.set_property('bitrate', self.audio_bitrate * 1000)
            encoder.set_property('managed', True)

        audio_convert = Gst.ElementFactory.make('audioconvert')

        self.pipeline.add(audio_convert)
        self.pipeline.add(encoder)
        audio_queue.link(audio_convert)
        audio_convert.link(encoder)

        # add remaining parts
        Gst.Element.link_pads(encoder, 'src', muxer, audio_pad.get_name())
        Gst.Element.link_pads(video_queue, 'src', muxer, video_pad.get_name())

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

    def start(self, path='~/output.mkv'):
        path = os.path.expanduser(path)
        self.sink.set_property('location', path)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipeline.set_state(Gst.State.READY)
        self.pipeline.set_state(Gst.State.NULL)


def main(
        filename='~/capture.mkv',
        audio_port=7654,
        video_port=7655,
        audio_delay=1150,
        audio_codec=None,
        audio_bitrate=128):

    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - Muxer')

    # Initialize Gstreamer
    GObject.threads_init()
    mainloop = GObject.MainLoop()
    Gst.init(None)

    # Start screen recorder
    recorder = RTPMuxer(
        audio_port=audio_port,
        video_port=video_port,
        audio_delay=audio_delay,
        audio_codec=audio_codec,
        audio_bitrate=audio_bitrate
    )
    recorder.start(path=filename)

    # run the main loop
    try:
        mainloop.run()
    except:
        recorder.stop()
        mainloop.quit()


# if run as script start recording
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Mux audio and video RTP streams')
    parser.add_argument(
        '-a', '--audio-port',
        type=int,
        nargs=1,
        dest='audio_port',
        default=[7654],
        help='audio port to listen on, we want S16BE audio data here'
    )
    parser.add_argument(
        '-b', '--audio-bitrate',
        type=str,
        nargs=1,
        dest='audio_bitrate',
        default=[128],
        help='audio bitrate to use for storage'
    )
    parser.add_argument(
        '-e', '--audio-codec',
        type=str,
        nargs=1,
        dest='audio_codec',
        default=[RTPMuxer.AUDIO_ENCODERS[0]],
        choices=RTPMuxer.AUDIO_ENCODERS,
        help='audio codec to use for storage'
    )
    parser.add_argument(
        '-d', '--avsync',
        type=int,
        nargs=1,
        dest='audio_delay',
        default=[0],
        help='A/V delay to synchronize audio track to video track, milliseconds (x264 veryfast: 1150)'
    )
    parser.add_argument(
        '-v', '--video-port',
        type=int,
        nargs=1,
        dest='video_port',
        default=[7655],
        help='video port to listen on'
    )
    parser.add_argument(
        'filename',
        nargs=1,
        type=str,
        help='output file'
    )
    args = parser.parse_args()

    main(
        filename=args.filename[0],
        audio_port=args.audio_port[0],
        video_port=args.video_port[0],
        audio_codec=args.audio_codec[0],
        audio_bitrate=args.audio_bitrate[0],
        audio_delay=args.audio_delay[0]
    )

