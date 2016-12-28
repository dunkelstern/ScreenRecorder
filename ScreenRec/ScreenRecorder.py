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

    def __init__(self, width=1920, height=1080, scale_width=None, scale_height=None, encoder=None, display=0, port=None):
        if not encoder in ScreenRecorder.ENCODERS:
            raise NotImplementedError("Encoder '{}' not implemented".format(encoder))

        self.scale_width = scale_width
        self.scale_height = scale_height
        self.width = width
        self.height = height
        self.encoder = encoder if encoder else ScreenRecorder.ENCODERS[0]
        self.display = display
        self.port = port
        self.build_gst_pipeline(encoder)
        self.rfd = None
        self.wfd = None

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

        print('Using {} encoder'.format(encoding_method))

        # nvenc is special as we run ffmpeg as a sub process
        if encoding_method == 'nvenc':
            return self.build_nvenc_pipeline(queue)

        # build encoding pipelines
        encoder = None
        if encoding_method == 'vaapi':
            # scale, convert and encode with hardware acceleration
            scaler = Gst.ElementFactory.make('vaapipostproc')
            if self.scale_width and self.scale_height:
                scaler.set_property('width', self.scale_width)
                scaler.set_property('height', self.scale_height)
                scaler.set_property('scale-method', 2)
            encoder = Gst.ElementFactory.make('vaapih264enc')

            self.pipeline.add(scaler)
            self.pipeline.add(encoder)

            queue.link(scaler)
            scaler.link(encoder)
        elif encoding_method == 'x264':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            self.pipeline.add(convert)
            queue.link(convert)

            encoder = Gst.ElementFactory.make('x264enc')
            encoder.set_property('speed-preset', 'veryfast')
            #encoder.set_property('tune', 4)  # zero latency

            if self.scale_width and self.scale_height:
                scaler = Gst.ElementFactory.make('videoscale')
                cap_string = 'video/x-raw,width={},height={}'.format(
                    self.scale_width, self.scale_height
                )
                caps = Gst.Caps.from_string(cap_string)
                filter = Gst.ElementFactory.make('capsfilter')
                filter.set_property('caps', caps)

                self.pipeline.add(scaler)
                self.pipeline.add(filter)
                self.pipeline.add(encoder)
                convert.link(scaler)
                scaler.link(filter)
                filter.link(encoder)
            else:
                self.pipeline.add(encoder)
                convert.link(encoder)
        elif encoding_method == 'openh264':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            self.pipeline.add(convert)
            queue.link(convert)

            encoder = Gst.ElementFactory.make('openh264enc')
            encoder.set_property('complexity', 0)

            if self.scale_width and self.scale_height:
                scaler = Gst.ElementFactory.make('videoscale')
                cap_string = 'video/x-raw,width={},height={}'.format(
                    self.scale_width, self.scale_height
                )
                caps = Gst.Caps.from_string(cap_string)
                filter = Gst.ElementFactory.make('capsfilter')
                filter.set_property('caps', caps)

                self.pipeline.add(scaler)
                self.pipeline.add(filter)
                self.pipeline.add(encoder)
                convert.link(scaler)
                scaler.link(filter)
                filter.link(encoder)
            else:
                self.pipeline.add(encoder)
                convert.link(encoder)
        elif encoding_method == 'vtenc_h264' or encoding_method == 'vtenc_h264_hw':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            self.pipeline.add(convert)
            queue.link(convert)

            encoder = Gst.ElementFactory.make(encoding_method)

            if self.scale_width and self.scale_height:
                scaler = Gst.ElementFactory.make('videoscale')
                cap_string = 'video/x-raw,width={},height={}'.format(
                    self.scale_width, self.scale_height
                )
                caps = Gst.Caps.from_string(cap_string)
                filter = Gst.ElementFactory.make('capsfilter')
                filter.set_property('caps', caps)

                self.pipeline.add(scaler)
                self.pipeline.add(filter)
                self.pipeline.add(encoder)
                convert.link(scaler)
                scaler.link(filter)
                filter.link(encoder)
            else:
                self.pipeline.add(encoder)
                convert.link(encoder)

        # output part of pipeline
        out_queue = Gst.ElementFactory.make('queue')
        self.pipeline.add(out_queue)
        encoder.link(out_queue)

        parser = Gst.ElementFactory.make('h264parse')
        self.pipeline.add(parser)
        out_queue.link(parser)

        if self.port:
            rtp_payload = Gst.ElementFactory.make('rtph264pay')
            rtp_payload.set_property('config-interval', -1)  # send sps and pps with every keyframe
            self.pipeline.add(rtp_payload)
            #timestamper = Gst.ElementFactory.make('rtponviftimestamp')
            #self.pipeline.add(timestamper)

            self.sink = Gst.ElementFactory.make('udpsink')
            self.sink.set_property('sync', True)
            self.sink.set_property('host', '127.0.0.1')
            self.sink.set_property('port', self.port)
            self.pipeline.add(self.sink)

            parser.link(rtp_payload)
            #rtp_payload.link(timestamper)
            #timestamper.link(self.sink)
            rtp_payload.link(self.sink)
        else:
            muxer = Gst.ElementFactory.make('matroskamux')
            self.pipeline.add(muxer)
            parser.link(muxer)
            self.sink = Gst.ElementFactory.make('filesink')
            self.pipeline.add(self.sink)
            muxer.link(self.sink)

        self.create_bus()

    def build_nvenc_pipeline(self, src):
        # scale and convert with software encoders, send rtp stream to ffmpeg for encoding
        convert = Gst.ElementFactory.make('autovideoconvert')
        self.pipeline.add(convert)
        src.link(convert)

        self.sink = Gst.ElementFactory.make('fdsink')

        encoder = Gst.ElementFactory.make('y4menc')

        if self.scale_width and self.scale_height:
            scaler = Gst.ElementFactory.make('videoscale')
            cap_string = 'video/x-raw,width={},height={}'.format(
                self.scale_width, self.scale_height
            )
            caps = Gst.Caps.from_string(cap_string)
            filter = Gst.ElementFactory.make('capsfilter')
            filter.set_property('caps', caps)

            self.pipeline.add(scaler)
            self.pipeline.add(filter)
            self.pipeline.add(encoder)
            convert.link(scaler)
            scaler.link(filter)
            filter.link(encoder)
        else:
            self.pipeline.add(encoder)
            convert.link(encoder)

        # add sink
        self.pipeline.add(self.sink)

        # link encoder to sink
        encoder.link(self.sink)

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
            if self.encoder == 'nvenc':
                # nvenc uses external ffmpeg process
                (self.rfd, self.wfd) = os.pipe()
                cmd = [
                    'ffmpeg',
                    '-y',
                    '-f', 'yuv4mpegpipe',
                    '-i', 'pipe:0',
                    '-vf', 'scale',
                    '-pix_fmt', 'yuv420p',
                    '-codec:v', 'h264_nvenc',
                    '-f', 'matroska',
                    path
                ]
                self.subproc = subprocess.Popen(cmd, stdin=self.rfd)
                self.sink.set_property('fd', self.wfd)
            else:
                # most encoders are gstreamer internal
                self.sink.set_property('location', path)
        self.pipeline.set_state(Gst.State.PLAYING)

        clock = self.pipeline.get_pipeline_clock().get_time()
        print('clock', clock)
        print('latency', self.pipeline.get_latency())
        print('delay', self.pipeline.get_delay())

    def stop(self):
        self.pipeline.set_state(Gst.State.READY)
        self.pipeline.set_state(Gst.State.NULL)
        if self.rfd:
            os.close(self.rfd)
        if self.wfd:
            os.close(self.wfd)


def main(
        filename=None,
        port=None,
        width=1920,
        height=1080,
        scale_width=None,
        scale_height=None,
        encoder=None,
        display=0):

    if not filename and not port:
        raise AttributeError('you have to set filename or port')

    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - ScreenCapture for display {}'.format(display))

    # Initialize Gstreamer
    GObject.threads_init()
    mainloop = GObject.MainLoop()
    Gst.init(None)

    # Start screen recorder
    if filename:
        recorder = ScreenRecorder(width=width,
                                  height=height,
                                  scale_height=scale_height,
                                  scale_width=scale_width,
                                  encoder=encoder,
                                  display=display)
        recorder.start(path=filename)
    else:
        recorder = ScreenRecorder(port=port,
                                  width=width,
                                  height=height,
                                  scale_height=scale_height,
                                  scale_width=scale_width,
                                  encoder=encoder,
                                  display=display)
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
