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
from ScreenRec.VideoEncoder import get_recording_sink
from ScreenRec.gui.ExclusiveRecording import Watcher, make_excl_button


# This one is a RTMP stream window
class RTMPWindow(PlaybackWindow):
    HW_ACCELS = available_hwaccels

    # Initialize window
    def __init__(
        self,
        url='rtmp://localhost:1935/live/stream1',
        title="RTMP Stream",
        max_width=1920,
        max_height=1080,
        hwaccel='opengl',
        id='rtmp',
        **kwargs
    ):
        self.id = id
        self.max_width = max_width
        self.max_height = max_height
        self.port = 7655  # FIXME: dynamic

        if 'comm_queues' in kwargs:
            self.comm = Watcher(kwargs['comm_queues'], self)
            self.comm.start()

        # Build window
        super().__init__(data=url, title=title, hwaccel=hwaccel)

        if 'comm_queues' in kwargs:
            make_excl_button(self)
        self.header.remove(self.switch)

        self.show(width=int(max_width / 2), height=int(max_height / 2), fixed=True)
        self.lastBuffer = None
        self.zoomed = False

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, stream):

        # stream src src
        self.src = Gst.ElementFactory.make('urisourcebin', 'source')
        self.src.set_property('uri', stream)
        self.src.connect('pad_added', self.pad_added)

        self.parser = Gst.ElementFactory.make('parsebin')
        self.parser.connect('pad_added', self.pad_added)
        
        self.decoder = Gst.ElementFactory.make('avdec_h264')
        self.tee = Gst.ElementFactory.make('tee')

        self.sink = self.make_sink(sync=False)
        self.fake_sink = Gst.ElementFactory.make('fakesink')

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(self.src)

        # rest happens in pad_added
        
        # connect encoder but do not start
        self.encoder, _ = get_recording_sink(port=self.port)

    def pad_added(self, src, pad):
        if src == self.src and pad.get_name() == 'src_0':
            self.pipeline.add(self.parser)
            Gst.Element.link_pads(self.src, 'src_0', self.parser, 'sink')
            self.parser.sync_state_with_parent()
        if src == self.parser:
            if str(pad.props.caps)[:5] == 'audio':
                self.pipeline.add(self.fake_sink)
                pad.link(self.fake_sink.get_static_pad('sink'))
                self.fake_sink.set_state(Gst.State.PLAYING)
                return

            if not self.decoder.get_parent():
                self.pipeline.add(self.decoder)
            try:
                pad.link(self.decoder.get_static_pad('sink'))
                self.pipeline.add(self.tee)
                self.decoder.link(self.tee)
                self.pipeline.add(self.sink)
                self.tee.link(self.sink)
                self.decoder.set_state(Gst.State.PLAYING)
                self.tee.set_state(Gst.State.PLAYING)
                self.sink.set_state(Gst.State.PLAYING)
            except Gst.LinkError as e:
                pass

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


def main(**kwargs):

    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - RTMPWindow: {}'.format(kwargs.get('title', 'Unknown')))

    print('rtmp main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = RTMPWindow(**kwargs)
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('rtmp quitting', e, tb)
        if window:
            window.quit(None)

# if run as script just display the window
if __name__ == "__main__":
    main()
