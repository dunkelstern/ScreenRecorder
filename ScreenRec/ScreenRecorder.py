import argparse
import os, subprocess
import platform

# gi is GObject instrospection
import gi

# we need GStreamer 1.0
gi.require_version('Gst', '1.0')
gi.require_version('GstNet', '1.0')
gi.require_version('GstRtsp', '1.0')

# Import GStreamer
from gi.repository import Gst, GObject, GstNet, GstRtsp

if platform.system() == 'Linux':
    available_encoders = [
        'x264',   # Uses libx264 'veryfast' preset, needs much CPU power
        'vaapi',  # Intel CPU driver (only when running Xorg on Intel or Glamour drivers
        'nvenc',  # NVidia encoder, needs GTX680 or higher (GK104/Keppler or higher) and ffmpeg with support compiled in
        # TODO: What about AMD graphics card acceleration?
    ]
elif platform.system() == 'Darwin':
    available_encoders = [
        'vtenc_h264',
        'vtenc_h264_hw'
    ]
elif platform.system() == 'Windows':
    available_encoders = [
        'openh264',
        'x264'
    ]

def get_recording_sink(**kwargs):
        # read settings
        from ScreenRec.model.configfile import config
        
        scale_width = kwargs.get('scale_width', config.rec_settings.scale_width)
        scale_height = kwargs.get('scale_height', config.rec_settings.scale_height)
        if scale_width == 0:
            scale_width = config.rec_settings.width
        if scale_height == 0:
            scale_height = config.rec_settings.height
        encoder = kwargs.get('encoder', config.rec_settings.encoder)
        if not encoder:
            encoder = ScreenRecorder.ENCODERS[0]
        port = kwargs.get('port', None)

        print('Using {} encoder'.format(encoder))

        # create encoder bin
        enc = Gst.Bin.new('encoder')

        # build encoding pipelines
        src = None
        sink = None
        if encoder == 'vaapi':
            # scale, convert and encode with hardware acceleration
            scaler = Gst.ElementFactory.make('vaapipostproc')
            scaler.set_property('width', scale_width)
            scaler.set_property('height', scale_height)
            scaler.set_property('scale-method', 2)
            enc.add(scaler)

            video_encoder = Gst.ElementFactory.make('vaapih264enc')
            enc.add(video_encoder)

            scaler.link(video_encoder)
            src = scaler
            sink = video_encoder
        elif encoder == 'x264':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            enc.add(convert)

            scaler = Gst.ElementFactory.make('videoscale')
            enc.add(scaler)
            cap_string = 'video/x-raw,width={},height={}'.format(
                scale_width, scale_height
            )
            caps = Gst.Caps.from_string(cap_string)
            filter = Gst.ElementFactory.make('capsfilter')
            filter.set_property('caps', caps)
            enc.add(filter)

            video_encoder = Gst.ElementFactory.make('x264enc')
            video_encoder.set_property('speed-preset', 'veryfast')
            #video_encoder.set_property('tune', 4)  # zero latency
            enc.add(video_encoder)

            convert.link(scaler)
            scaler.link(filter)
            filter.link(video_encoder)

            src = convert
            sink = video_encoder
        elif encoding_method == 'openh264':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            enc.add(convert)

            scaler = Gst.ElementFactory.make('videoscale')
            enc.add(scaler)
            cap_string = 'video/x-raw,width={},height={}'.format(
                scale_width, scale_height
            )
            caps = Gst.Caps.from_string(cap_string)
            filter = Gst.ElementFactory.make('capsfilter')
            filter.set_property('caps', caps)
            enc.add(filter)

            video_encoder = Gst.ElementFactory.make('openh264enc')
            video_encoder.set_property('complexity', 0)

            enc.add(video_encoder)

            convert.link(scaler)
            scaler.link(filter)
            filter.link(video_encoder)

            src = convert
            sink = video_encoder
        elif encoding_method == 'vtenc_h264' or encoding_method == 'vtenc_h264_hw':
            # scale, convert and encode with software encoders

            convert = Gst.ElementFactory.make('autovideoconvert')
            enc.add(convert)

            scaler = Gst.ElementFactory.make('videoscale')
            enc.add(scaler)
            cap_string = 'video/x-raw,width={},height={}'.format(
                scale_width, scale_height
            )
            caps = Gst.Caps.from_string(cap_string)
            filter = Gst.ElementFactory.make('capsfilter')
            filter.set_property('caps', caps)
            enc.add(filter)

            video_encoder = Gst.ElementFactory.make(encoding_method)

            enc.add(video_encoder)

            convert.link(scaler)
            scaler.link(filter)
            filter.link(video_encoder)

            src = convert
            sink = video_encoder

        # output part of pipeline
        out_queue = Gst.ElementFactory.make('queue')
        enc.add(out_queue)
        sink.link(out_queue)

        parser = Gst.ElementFactory.make('h264parse')
        enc.add(parser)
        out_queue.link(parser)

        filesink = None
        if port:
            rtp_payload = Gst.ElementFactory.make('rtph264pay')
            rtp_payload.set_property('config-interval', -1)  # send sps and pps with every keyframe
            enc.add(rtp_payload)

            udpsink = Gst.ElementFactory.make('udpsink')
            udpsink.set_property('sync', True)
            udpsink.set_property('host', '127.0.0.1')
            udpsink.set_property('port', port)
            enc.add(udpsink)

            parser.link(rtp_payload)
            rtp_payload.link(udpsink)
        else:
            muxer = Gst.ElementFactory.make('matroskamux')
            enc.add(muxer)
            parser.link(muxer)
            filesink = Gst.ElementFactory.make('filesink')
            enc.add(filesink)
            muxer.link(filesink)

        ghost_sink = Gst.GhostPad.new('sink', src.get_static_pad('sink'))
        enc.add_pad(ghost_sink)

        return enc, filesink

# def build_nvenc_pipeline(self, src):
#     # scale and convert with software encoders, send rtp stream to ffmpeg for encoding
#     convert = Gst.ElementFactory.make('autovideoconvert')
#     self.pipeline.add(convert)
#     src.link(convert)

#     self.sink = Gst.ElementFactory.make('fdsink')

#     encoder = Gst.ElementFactory.make('y4menc')

#     if self.scale_width and self.scale_height:
#         scaler = Gst.ElementFactory.make('videoscale')
#         cap_string = 'video/x-raw,width={},height={}'.format(
#             self.scale_width, self.scale_height
#         )
#         caps = Gst.Caps.from_string(cap_string)
#         filter = Gst.ElementFactory.make('capsfilter')
#         filter.set_property('caps', caps)

#         self.pipeline.add(scaler)
#         self.pipeline.add(filter)
#         self.pipeline.add(encoder)
#         convert.link(scaler)
#         scaler.link(filter)
#         filter.link(encoder)
#     else:
#         self.pipeline.add(encoder)
#         convert.link(encoder)

#     # add sink
#     self.pipeline.add(self.sink)

#     # link encoder to sink
#     encoder.link(self.sink)

#     self.create_bus()



class ScreenRecorder:

    ENCODERS = available_encoders
    ENCODER_DELAY = {
        'x264': 1150,
        'vaapi': 240,
        'nvenc': 1000/25,
        'vtenc_h264': 0,
        'vtenc_h264_hw': 0,
        'openh264': 0
    }

    def __init__(self, **kwargs):
        from ScreenRec.model.configfile import config

        self.scale_width = kwargs.get('scale_width', config.rec_settings.scale_width)
        self.scale_height = kwargs.get('scale_height', config.rec_settings.scale_height)
        self.width = kwargs.get('width', config.rec_settings.width)
        self.height = kwargs.get('height', config.rec_settings.height)
        self.encoder = kwargs.get('encoder', config.rec_settings.encoder)
        if not self.encoder:
            self.encoder = ScreenRecorder.ENCODERS[0]
        self.display = kwargs.get('display', config.rec_settings.screen)
        self.port = kwargs.get('port', None)
        
        self.build_gst_pipeline(self.encoder)
        # self.rfd = None
        # self.wfd = None

    def build_gst_pipeline(self, encoding_method):
        # display src
        src = None

        if platform.system() == 'Linux':
            src = Gst.ElementFactory.make('ximagesrc', 'source')
            src.set_property('display-name', ':0.{}'.format(self.display))
            src.set_property('use-damage', 0)
            src.set_property('startx', 0)
            src.set_property('starty', 0)
            src.set_property('endx', self.width - 1)
            src.set_property('endy', self.height - 1)
        elif platform.system() == 'Darwin':
            src = Gst.ElementFactory.make('avfvideosrc', 'source')
            src.set_property('capture-screen', True)
            src.set_property('capture-screen-cursor', True)
            src.set_property('device-index', self.display)
        elif platform.system() == 'Windows':
            src = Gst.ElementFactory.make('dx9screencapsrc', 'source')
            src.set_property('x', 0)
            src.set_property('y', 0)
            src.set_property('width', self.width - 1)
            src.set_property('height', self.height - 1)
            src.set_property('monitor', self.display)
        src.set_property('do-timestamp', True)

        queue = Gst.ElementFactory.make('queue')

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.use_clock(Gst.SystemClock.obtain())

        self.pipeline.add(src)
        self.pipeline.add(queue)
        src.link(queue)

        sink, self.sink = get_recording_sink(
            scale_width=self.scale_width if self.scale_width else self.width,
            scale_height=self.scale_height if self.scale_height else self.height,
            encoder=self.encoder,
            port=self.port
        )

        self.pipeline.add(sink)
        queue.link(sink)

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
            # path = os.path.expanduser(path)
            # if self.encoder == 'nvenc':
            #     # nvenc uses external ffmpeg process
            #     (self.rfd, self.wfd) = os.pipe()
            #     cmd = [
            #         'ffmpeg',
            #         '-y',
            #         '-f', 'yuv4mpegpipe',
            #         '-i', 'pipe:0',
            #         '-vf', 'scale',
            #         '-pix_fmt', 'yuv420p',
            #         '-codec:v', 'h264_nvenc',
            #         '-f', 'matroska',
            #         path
            #     ]
            #     self.subproc = subprocess.Popen(cmd, stdin=self.rfd)
            #     self.sink.set_property('fd', self.wfd)
            # else:

            # most encoders are gstreamer internal
            self.sink.set_property('location', path)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipeline.set_state(Gst.State.READY)
        self.pipeline.set_state(Gst.State.NULL)
        # if self.rfd:
        #     os.close(self.rfd)
        # if self.wfd:
        #     os.close(self.wfd)


def main(**kwargs):
    if 'filename' not in kwargs and 'port' not in kwargs:
        raise AttributeError('you have to set filename or port')

    from ScreenRec.model.configfile import config
    display = kwargs.get('display', config.rec_settings.screen)
    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - ScreenCapture for display {}'.format(display))

    # Initialize Gstreamer
    GObject.threads_init()
    mainloop = GObject.MainLoop()
    Gst.init(None)

    # Start screen recorder
    if 'filename' in kwargs:
        recorder = ScreenRecorder(**kwargs)
        recorder.start(path=kwargs['filename'])
    else:
        recorder = ScreenRecorder(**kwargs)
        recorder.start()

    # run the main loop
    try:
        mainloop.run()
    except:
        recorder.stop()
        mainloop.quit()


# if run as script start recording
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Record the screen')
    parser.add_argument(
        '-d', '--display',
        type=int,
        nargs=1,
        default=0,
        dest='display',
        help='display index to capture'
    )
    parser.add_argument(
        '-x', '--width',
        type=int,
        nargs=1,
        default=1920,
        dest='width',
        help='width of the screen area to capture'
    )
    parser.add_argument(
        '-y', '--height',
        type=int,
        nargs=1,
        default=1080,
        dest='height',
        help='height of the screen area to capture'
    )
    parser.add_argument(
        '--scaled-width',
        type=int,
        nargs=1,
        default=None,
        dest='scaled_width',
        help='width of the recorded video file'
    )
    parser.add_argument(
        '--scaled-height',
        type=int,
        nargs=1,
        default=None,
        dest='scaled_height',
        help='height of the recorded video file'
    )
    parser.add_argument(
        '-e', '--encoder',
        type=str,
        nargs=1,
        dest='encoder',
        default=ScreenRecorder.ENCODERS[0],
        choices=ScreenRecorder.ENCODERS,
        help='encoder to use'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        nargs=1,
        dest='port',
        default=7655,
        help='do not save to file but stream to port'
    )
    parser.add_argument(
        'filename',
        nargs="*",
        type=str,
        help='output file'
    )
    args = parser.parse_args()

    if args.filename:
        main(
            filename=args.filename[0],
            width=args.width,
            height=args.height,
            scale_width=args.scaled_width,
            scale_height=args.scaled_height,
            encoder=args.encoder,
            display=args.display
        )
    else:
        main(
            port=args.port[0],
            width=args.width,
            height=args.height,
            scale_width=args.scaled_width,
            scale_height=args.scaled_height,
            encoder=args.encoder,
            display=args.display
        )
