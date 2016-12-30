import sys, os
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
from ScreenRec.VideoEncoder import get_recording_sink
from ScreenRec.gui.ExclusiveRecording import Watcher, make_excl_button


# This one is a RTMP stream window
class PlayerWindow(PlaybackWindow):
    HW_ACCELS = available_hwaccels

    # Initialize window
    def __init__(
        self,
        filename='~/Movies/video.mp4',
        title="Movie Player",
        max_width=1920,
        max_height=1080,
        seek_bar=False,
        restart_on_deactivate=True,
        auto_play=False,
        hwaccel='opengl',
        id='player',
        **kwargs
    ):
        self.id = id
        self.max_width = max_width
        self.max_height = max_height
        self.restart_on_deactivate = restart_on_deactivate
        self.auto_play = auto_play
        self.seek_bar = seek_bar
        self.port = 7655  # FIXME: dynamic

        if 'comm_queues' in kwargs:
            self.comm = Watcher(kwargs['comm_queues'], self)
            self.comm.start()

        # Build window
        super().__init__(data=filename, title=title, hwaccel=hwaccel, auto_start=self.auto_play)

        if 'comm_queues' in kwargs:
            make_excl_button(self)

        if self.seek_bar:
            self.seek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 1.0, 0.001)
            self.seek.set_draw_value(False)
            self.seek.set_hexpand(True)
            self.seek.connect('change-value', self.on_seek)
            self.header.set_custom_title(self.seek)

        self.show(width=int(max_width / 2), height=int(max_height / 2), fixed=True)
        self.lastBuffer = None
        self.zoomed = False
        self.pipeline.set_state(Gst.State.PAUSED)

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, filename):
        path = os.path.expanduser(filename)

        # stream src src
        self.src = Gst.ElementFactory.make('playbin', 'source')
        self.src.set_property('uri', 'file://' + path)

        self.tee = Gst.ElementFactory.make('tee')
        src.set_property('video-sink', self.tee)

        sink = self.make_sink(sync=True)

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(self.src)
        self.pipeline.add(sink)
        self.tee.link(sink)

        # connect encoder but do not start
        self.encoder, _ = get_recording_sink(port=self.port)

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

    def on_seek(self, sender, scroll_type, value):
        _, max = self.pipeline.query_duration(Gst.Format.TIME)
        self.pipeline.seek(1.0, Gst.Format.TIME, Gst.SeekFlags.FLUSH, Gst.SeekType.SET, value, Gst.SeekType.NONE, max)

    def on_play(self, switch, gparam):
        if switch.get_active():
            # user turned on the switch, start the pipeline
            if self.pipeline:
                self.pipeline.set_state(Gst.State.PLAYING)
                if self.seek_bar:
                    GObject.timeout_add(50, self.on_timeout, None)
        else:
            # user turned off the switch, reset pipeline
            if self.pipeline:
                if self.restart_on_deactivate:
                    self.pipeline.set_state(Gst.State.NULL)
                else:
                    self.pipeline.set_state(Gst.State.PAUSED)

    def on_timeout(self, data):
        if self.switch.get_active() is False or self.pipeline.get_state == Gst.State.PAUSED:
            return False

        _, max = self.pipeline.query_duration(Gst.Format.TIME)
        _, current = self.pipeline.query_position(Gst.Format.TIME)
        self.seek.set_range(0, max)
        self.seek.set_value(current)

        return True  # call again


def main(**kwargs):
    
    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - PlayerWindow: {}'.format(kwargs.get('title', 'Unknown')))

    print('player main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = PlayerWindow(**kwargs)
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('player quitting', e, tb)
        if window:
            window.quit(None)

# if run as script just display the window
if __name__ == "__main__":
    main()
