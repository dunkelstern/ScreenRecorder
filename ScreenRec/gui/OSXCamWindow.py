import sys

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# Import GStreamer
from gi.repository import Gst, GObject, Gtk

from .GtkPlaybackWindow import PlaybackWindow
from ScreenRec.VideoEncoder import get_recording_sink
from ScreenRec.gui.ExclusiveRecording import Watcher, make_excl_button


# This one is a Webcam window
class OSXCamWindow(PlaybackWindow):
    # Initialize window
    def __init__(
        self,
        device=0,
        title="Webcam",
        width=1280,
        height=720,
        framerate=20,
        id='osxcam',
        **kwargs
    ):
        self.id = id
        self.width = width
        self.height = height
        self.framerate = framerate
        self.port = 7655  # FIXME: dynamic

        if 'comm_queues' in kwargs:
            self.comm = Watcher(kwargs['comm_queues'], self)
            self.comm.start()

        # Build window
        super().__init__(data=device, title=title)

        if 'comm_queues' in kwargs:
            make_excl_button(self)

        # No additional window elements, just show the window with fixed width and height
        self.show(width=int(width/2), height=int(height/2), fixed=True)
        self.zoomed = False

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, device):

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')

        # video src
        src = Gst.ElementFactory.make('avfvideosrc', 'source')
        src.set_property('device-index', device)
        self.pipeline.add(src)

        # get stream
        caps = Gst.Caps.from_string(
            'video/x-raw,width={width},height={height},framerate={framerate}/1'.format(
                width=self.width,
                height=self.height,
                framerate=self.framerate
            )
        )
        filter = Gst.ElementFactory.make('capsfilter')
        filter.set_property('caps', caps)
        self.pipeline.add(filter)
        src.link(filter)

        self.tee = Gst.ElementFactory.make('tee')
        self.pipeline.add(tee)
        filter.link(self.tee)

        # scale
        scaler = Gst.ElementFactory.make('videoscale')
        self.pipeline.add(scaler)
        tee.link(scaler)

        self.scalecaps = Gst.Caps.from_string(
            'video/x-raw,width={width},height={height}'.format(
                width=int(self.width / 2),
                height=int(self.height / 2)
            )
        )
        self.scaler = Gst.ElementFactory.make('capsfilter')
        self.scaler.set_property('caps', self.scalecaps)
        self.pipeline.add(self.scaler)
        scaler.link(self.scaler)

        self.sink = Gst.ElementFactory.make('gtksink')
        self.sink.set_property('sync', 'false')

        self.pipeline.add(self.sink)
        self.scaler.link(self.sink)

        # connect encoder but do not start
        self.encoder, _ = get_recording_sink(port=self.port)

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
            self.pipeline.set_state(Gst.State.NULL)

        self.scalecaps = Gst.Caps.from_string(
			'video/x-raw,width={width},height={height}'.format(
				width=width,
				height=height
			)
		)
        self.scaler.set_property('caps', self.scalecaps)

        self.resize(width, height)
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)

def main(**kwargs):
    
    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - OSXCamWindow: {}'.format(kwargs.get('title', 'Unknown')))

    print('osxcam main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = OSXCamWindow(**kwargs)
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('osxcam quitting', e, tb)
        if window:
            window.quit(None)

# if run as script just display the window
if __name__ == "__main__":
    main()
