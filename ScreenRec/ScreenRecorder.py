import os, sys

# gi is GObject instrospection
import gi

# we need GStreamer 1.0
gi.require_version('Gst', '1.0')

# Import GStreamer
from gi.repository import Gst, GObject


class ScreenRecorder():

    def __init__(self, width=1920, height=1080, scale_width=None, scale_height=None):
        self.scale_width = scale_width
        self.scale_height = scale_height
        self.width = width
        self.height = height
        self.build_gst_pipeline()

    def build_gst_pipeline(self):
        # display src
        src = Gst.ElementFactory.make('ximagesrc', 'source')
        src.set_property('display-name', ':0')
        src.set_property('use-damage', 0)
        src.set_property('startx', 0)
        src.set_property('starty', 0)
        src.set_property('endx', self.width - 1)
        src.set_property('endy', self.height - 1)

        # get 720p mjpeg stream
        # caps = Gst.Caps.from_string('image/jpeg,width=1280,height=720,framerate=20/1')
        # filter = Gst.ElementFactory.make('capsfilter')
        # filter.set_property('caps', caps)

        # parse, decode and scale with hardware acceleration
        self.scaler = Gst.ElementFactory.make('vaapipostproc')
        if self.scale_width and self.scale_height:
            self.scaler.set_property('width', self.scale_width)
            self.scaler.set_property('height', self.scale_height)
            self.scaler.set_property('scale-method', 2)

        encoder = Gst.ElementFactory.make('vaapih264enc')
        parser = Gst.ElementFactory.make('h264parse')
        muxer = Gst.ElementFactory.make('matroskamux')

        # output is vaapi because the image is already in VRAM
        self.sink = Gst.ElementFactory.make('filesink')

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(src)
        self.pipeline.add(self.scaler)
        self.pipeline.add(encoder)
        self.pipeline.add(parser)
        self.pipeline.add(muxer)
        self.pipeline.add(self.sink)

        src.link(self.scaler)
        self.scaler.link(encoder)
        encoder.link(parser)
        parser.link(muxer)
        muxer.link(self.sink)

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

def main(filename='~/capture.mkv', width=1920, height=1080, scale_width=None, scale_height=None):
    # Initialize Gstreamer
    GObject.threads_init()
    mainloop = GObject.MainLoop()
    Gst.init(None)

    # Start screen recorder
    recorder = ScreenRecorder(width=width, height=height, scale_height=scale_height, scale_width=scale_width)
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
