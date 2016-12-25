import sys
from datetime import datetime, timedelta

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import GObject, Gtk

# Import GStreamer
from gi.repository import Gst

from .GtkPlaybackWindow import PlaybackWindow, available_hwaccels


# This one is a RTMP stream window
class RTMPWindow(PlaybackWindow):
    HW_ACCELS = available_hwaccels

    # Initialize window
    def __init__(self, url='rtmp://localhost:1935/live/stream1', title="RTMP Stream", max_width=1920, max_height=1080, hwaccel='opengl'):
        self.max_width = max_width
        self.max_height = max_height

        # Build window
        super().__init__(data=url, title=title, hwaccel=hwaccel)
        # No additional window elements, just show the window with fixed width and height
        self.show(width=int(max_width / 2), height=int(max_height / 2), fixed=True)
        self.lastBuffer = None
        self.zoomed = False

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, stream):

        # stream src src
        src = Gst.ElementFactory.make('playbin', 'source')
        src.set_property('uri', stream)
        src.set_property('mute', True)

        sink = self.make_sink(sync=True)
        src.set_property('video-sink', sink)

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(src)

    def on_message(self, bus, message):
        super().on_message(bus, message)

        t = message.type
        if t == Gst.MessageType.BUFFERING:
            self.lastBuffer = datetime.now()

    def on_zoom(self, src):
        width = int(self.max_width / 2)
        height = int(self.max_height / 2)
        if self.zoomed:
            self.zoomed = False
        else:
            self.zoomed = True
            width = self.max_width
            height = self.max_height

        if self.pipeline:
            self.pipeline.set_state(Gst.State.PAUSED)
        self.resize(width, height)
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)

    def on_play(self, switch, gparam):
        super().on_play(switch, gparam)
        if switch.get_active():
            GObject.timeout_add(1000, self.on_timeout, None)

    def on_timeout(self, data):
        if self.lastBuffer and self.lastBuffer + timedelta(seconds=2) < datetime.now():
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            self.switch.set_active(False)

            return False  # disable timer
        return True  # call again

def main(url='rtmp://127.0.0.1:1935/live/stream1', title="RTMP Stream", max_width=1920, max_height=1080, hwaccel='opengl'):
    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - RTMPWindow: {}'.format(title))

    print('rtmp main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = RTMPWindow(
            url=url,
            title=title,
            max_width=max_width,
            max_height=max_height,
            hwaccel=hwaccel
        )
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('rtmp quitting', e, tb)
        if window:
            window.quit(None)

# if run as script just display the window
if __name__ == "__main__":
    main()
