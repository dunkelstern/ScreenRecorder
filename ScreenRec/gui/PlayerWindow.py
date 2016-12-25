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
class PlayerWindow(PlaybackWindow):
    HW_ACCELS = available_hwaccels

    # Initialize window
    def __init__(self, filename='~/Movies/video.mp4', title="Movie Player", max_width=1920, max_height=1080, hwaccel='opengl'):
        self.max_width = max_width
        self.max_height = max_height

        # Build window
        super().__init__(data=filename, title=title, hwaccel=hwaccel)

        # TODO: user interface elements
        # 'seek_bar',

        self.show(width=int(max_width / 2), height=int(max_height / 2), fixed=True)
        self.lastBuffer = None
        self.zoomed = False

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, filename):
        path = os.path.expanduser(filename)

        # stream src src
        src = Gst.ElementFactory.make('playbin', 'source')
        src.set_property('uri', 'file://' + path)

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
        # TODO: behaviour

        # 'auto_play',
        # 'restart_on_deactivate',

        super().on_play(switch, gparam)
        if switch.get_active():
            GObject.timeout_add(1000, self.on_timeout, None)

    def on_timeout(self, data):
        # TODO: remove timer
        if self.lastBuffer and self.lastBuffer + timedelta(seconds=2) < datetime.now():
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            self.switch.set_active(False)

            return False  # disable timer
        return True  # call again

def main(filename='~/Movies/video.mp4', title="Movie Player", max_width=1920, max_height=1080):
    print('player main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = PlayerWindow(
            filename=filename,
            title=title,
            max_width=max_width,
            max_height=max_height
        )
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('player quitting', e, tb)
        if window:
            window.quit(None)

# if run as script just display the window
if __name__ == "__main__":
    main()
