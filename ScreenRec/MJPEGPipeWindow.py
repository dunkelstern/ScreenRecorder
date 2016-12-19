import os, shlex, subprocess, sys

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# Import GStreamer
from gi.repository import Gst, Gtk, GObject

# Used for reparenting output window
gi.require_version('GstVideo', '1.0')
from gi.repository import GdkX11, GstVideo

from .GtkPlaybackWindow import PlaybackWindow


# This one is a External MJPEG pipe window (camera liveviews, etc.)
class MJPEPPipeWindow(PlaybackWindow):

    # Initialize window
    def __init__(self, command='gphoto2 --stdout --capture-movie', title='Camera Liveview'):
        self.command = shlex.split(command)
        self.subproc = None
        self.wfd = None
        self.rfd = None
        self.zoomed = False

        # Build window
        super().__init__(title=title)
        # No additional window elements, just show the window with fixed width and height
        self.show(width=1056/2, height=704/2, fixed=True)

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, device):

        # v4l src
        self.src = Gst.ElementFactory.make('fdsrc', 'source')

        # get 720p mjpeg stream
        caps = Gst.Caps.from_string('image/jpeg,framerate=0/1')
        filter = Gst.ElementFactory.make('capsfilter')
        filter.set_property('caps', caps)

        # parse, decode and scale with hardware acceleration
        parse = Gst.ElementFactory.make('jpegparse')
        decoder = Gst.ElementFactory.make('vaapijpegdec')
        self.scaler = Gst.ElementFactory.make('vaapipostproc')
        self.scaler.set_property('width', int(1056/2))
        self.scaler.set_property('height', int(704/2))
        self.scaler.set_property('scale-method', 2)

        # output is vaapi because the image is already in VRAM
        sink = Gst.ElementFactory.make('vaapisink')
        sink.set_property('sync', 'false')

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(self.src)
        self.pipeline.add(filter)
        self.pipeline.add(parse)
        self.pipeline.add(decoder)
        self.pipeline.add(self.scaler)
        self.pipeline.add(sink)
        self.src.link(filter)
        filter.link(parse)
        parse.link(decoder)
        decoder.link(self.scaler)
        self.scaler.link(sink)

    def on_play(self, switch, gparam):
        if switch.get_active():
            self.start()
        else:
            self.stop()

    def start(self):
        if self.wfd:
            os.close(self.wfd)
        if self.rfd:
            os.close(self.rfd)

        # create capture pipe to connect to external command
        (self.rfd, self.wfd) = os.pipe()
        self.subproc = subprocess.Popen(self.command, stdout=self.wfd)
        self.src.set_property('fd', self.rfd)

        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        if self.subproc:
            self.subproc.terminate()
            self.subproc = None
        if self.pipeline:
            self.pipeline.set_state(Gst.State.READY)

    def on_zoom(self, src):
        width = int(1056 / 2)
        height = int(704 / 2)
        if self.zoomed:
            self.zoomed = False
        else:
            self.zoomed = True
            width = 1056
            height = 704

        self.stop()
        self.scaler.set_property('width', width)
        self.scaler.set_property('height', height)
        self.resize(width, height)
        self.start()

    def quit(self, sender):
        if self.subproc:
            self.subproc.terminate()
        super().quit(sender)


def main(command='gphoto2 --stdout --capture-movie', title="Webcam"):
    print('MJPEG main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = MJPEPPipeWindow(
            command=command,
            title=title
        )
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('MJPEG quitting', e, tb)
        if window:
            window.quit(None)

# if run as script just display the window
if __name__ == "__main__":
    main()