import sys

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# Import GStreamer
from gi.repository import Gst, GObject, Gtk

# Used for reparenting output window
gi.require_version('GstVideo', '1.0')
from gi.repository import GdkX11, GstVideo

from .GtkPlaybackWindow import PlaybackWindow


# This one is a Webcam window
class V4L2Window(PlaybackWindow):
    # Initialize window
    def __init__(self, device='/dev/video0', title="Webcam", mime="image/jpeg", width=1280, height=720, framerate=20):
        self.mime = mime
        self.width = width
        self.height = height
        self.framerate = framerate

        # Build window
        super().__init__(data=device, title=title)

        # No additional window elements, just show the window with fixed width and height
        self.show(width=int(width/2), height=int(height/2), fixed=True)
        self.zoomed = False

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, device):

        # v4l src
        src = Gst.ElementFactory.make('v4l2src', 'source')
        src.set_property('device', device)

        # get stream
        caps = Gst.Caps.from_string(
            '{mime},width={width},height={height},framerate={framerate}/1'.format(
                mime=self.mime,
                width=self.width,
                height=self.height,
                framerate=self.framerate
            )
        )
        filter = Gst.ElementFactory.make('capsfilter')
        filter.set_property('caps', caps)

        # parse, decode and scale with hardware acceleration
        parse = Gst.ElementFactory.make('jpegparse')
        decoder = Gst.ElementFactory.make('vaapijpegdec')
        self.scaler = Gst.ElementFactory.make('vaapipostproc')
        self.scaler.set_property('width', int(self.width / 2))
        self.scaler.set_property('height', int(self.height / 2))
        self.scaler.set_property('scale-method', 2)

        # output is vaapi because the image is already in VRAM
        sink = Gst.ElementFactory.make('vaapisink')
        sink.set_property('sync', 'false')

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(src)
        self.pipeline.add(filter)
        self.pipeline.add(parse)
        self.pipeline.add(decoder)
        self.pipeline.add(self.scaler)
        self.pipeline.add(sink)
        src.link(filter)
        filter.link(parse)
        parse.link(decoder)
        decoder.link(self.scaler)
        self.scaler.link(sink)

    def on_zoom(self, src):
        width = int(self.width / 2)
        height = int(self.height / 2)
        if self.zoomed:
            self.zoomed = False
        else:
            self.zoomed = True
            width = self.width
            height = self.height

        if self.pipeline:
            self.pipeline.set_state(Gst.State.READY)
        self.scaler.set_property('width', width)
        self.scaler.set_property('height', height)
        self.resize(width, height)
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)

def main(device='/dev/video0', title="Webcam", mime="image/jpeg", width=1280, height=720, framerate=20):
    print('v4l2 main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = V4L2Window(
            device=device,
            title=title,
            mime=mime,
            width=width,
            height=height,
            framerate=framerate
        )
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('v4l2 quitting', e, tb)
        if window:
            window.quit(None)

# if run as script just display the window
if __name__ == "__main__":
    main()
