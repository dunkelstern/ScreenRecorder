import os, sys, subprocess

# gi is GObject instrospection
import gi

# we need GStreamer 1.0
gi.require_version('Gst', '1.0')

# Import GStreamer
from gi.repository import Gst, GObject


class ScreenRecorder():

    ENCODERS = [
        'vaapi', # Intel CPU driver (only when running Xorg on Intel or Glamour drivers
        'nvenc', # NVidia encoder, needs GTX680 or higher (GK104/Keppler or higher) and ffmpeg with support compiled in
        'software' # Uses libx264 'veryfast' preset, needs much CPU power
        # TODO: What about AMD graphics card acceleration?
    ]

    def __init__(self, width=1920, height=1080, scale_width=None, scale_height=None, encoder='software'):
        if not encoder in ScreenRecorder.ENCODERS:
            raise NotImplementedError("Encoder '{}' not implemented".format(encoder))

        self.scale_width = scale_width
        self.scale_height = scale_height
        self.width = width
        self.height = height
        self.encoder = encoder
        self.build_gst_pipeline(encoder)

    def build_gst_pipeline(self, encoding_method):
        # display src
        src = Gst.ElementFactory.make('ximagesrc', 'source')
        src.set_property('display-name', ':0')
        src.set_property('use-damage', 0)
        src.set_property('startx', 0)
        src.set_property('starty', 0)
        src.set_property('endx', self.width - 1)
        src.set_property('endy', self.height - 1)

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')

        self.pipeline.add(src)

        print('Using {} encoder'.format(encoding_method))

        # nvenc is special as we run ffmpeg as a sub process
        if encoding_method == 'nvenc':
            return self.build_nvenc_pipeline(src)

        # output part of pipeline
        parser = Gst.ElementFactory.make('h264parse')
        muxer = Gst.ElementFactory.make('matroskamux')
        self.sink = Gst.ElementFactory.make('filesink')

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

            src.link(scaler)
            scaler.link(encoder)
        elif encoding_method == 'software':
            # scale, convert and encode with software encoders
            convert = Gst.ElementFactory.make('autovideoconvert')
            self.pipeline.add(convert)
            src.link(convert)

            encoder = Gst.ElementFactory.make('x264enc')
            encoder.set_property('speed-preset', 'veryfast')

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

        # add remaining parts
        self.pipeline.add(parser)
        self.pipeline.add(muxer)
        self.pipeline.add(self.sink)

        # link remaining parts
        encoder.link(parser)
        parser.link(muxer)
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

    def start(self, path='~/output.mkv'):
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
            # vaapi and software encoders are gstreamer internal
            self.sink.set_property('location', path)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        self.pipeline.set_state(Gst.State.READY)
        self.pipeline.set_state(Gst.State.NULL)
        if self.rfd:
            os.close(self.rfd)
        if self.wfd:
            os.close(self.wfd)

def main(filename='~/capture.mkv', width=1920, height=1080, scale_width=None, scale_height=None, encoder='software'):
    # Initialize Gstreamer
    GObject.threads_init()
    mainloop = GObject.MainLoop()
    Gst.init(None)

    # Start screen recorder
    recorder = ScreenRecorder(width=width, height=height, scale_height=scale_height, scale_width=scale_width, encoder=encoder)
    recorder.start(path=filename)

    # run the main loop
    try:
        mainloop.run()
    except:
        recorder.stop()
        mainloop.quit()


# if run as script start recording
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: {} <filename>'.format(sys.argv[0]))
        exit(1)

    main(filename=sys.argv[1])
