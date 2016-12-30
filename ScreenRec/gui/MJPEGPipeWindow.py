import os, shlex, subprocess, sys

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# Import GStreamer
from gi.repository import Gst, Gtk, GObject

from .GtkPlaybackWindow import PlaybackWindow, available_hwaccels
from ScreenRec.VideoEncoder import get_recording_sink
from ScreenRec.gui.ExclusiveRecording import Watcher, make_excl_button


# This one is a External MJPEG pipe window (camera liveviews, etc.)
class MJPEGPipeWindow(PlaybackWindow):
    HW_ACCELS = available_hwaccels

    # Initialize window
    def __init__(
        self,
        command='gphoto2 --stdout --capture-movie',
        title='Camera Liveview',
        width=1056,
        height=704,
        hwaccel='opengl',
        id='mjpegstream',
        **kwargs
    ):
        self.id = id
        self.command = shlex.split(command)
        self.subproc = None
        self.wfd = None
        self.rfd = None
        self.zoomed = False
        self.width = width
        self.height = height
        self.port = 7655  # FIXME: dynamic

        if 'comm_queues' in kwargs:
            self.comm = Watcher(kwargs['comm_queues'], self)
            self.comm.start()

        # Build window
        super().__init__(title=title, hwaccel=hwaccel)

        if 'comm_queues' in kwargs:
            make_excl_button(self)

        self.show(width=self.width/2, height=self.height/2, fixed=True)

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, device):

        # v4l src
        self.src = Gst.ElementFactory.make('fdsrc', 'source')

        # get mjpeg stream
        caps = Gst.Caps.from_string('image/jpeg,framerate=0/1')
        filter = Gst.ElementFactory.make('capsfilter')
        filter.set_property('caps', caps)

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(self.src)
        self.pipeline.add(filter)

        parse = Gst.ElementFactory.make('jpegparse')
        self.pipeline.add(parse)

        self.tee = Gst.ElementFactory.make('tee')
        self.pipeline.add(self.tee)

        # decode and scale with hardware acceleration
        decoder = None
        if self.hwaccel == 'vaapi':
            decoder = Gst.ElementFactory.make('vaapijpegdec')
            self.scalerObject = Gst.ElementFactory.make('vaapipostproc')
            self.scalerObject.set_property('width', int(self.width/2))
            self.scalerObject.set_property('height', int(self.height/2))
            self.scalerObject.set_property('scale-method', 2)
            self.pipeline.add(decoder)
            self.pipeline.add(self.scalerObject)
            decoder.link(self.tee)
            self.tee.link(self.scalerObject)
        else:
            decoder = Gst.ElementFactory.make('jpegdec')
            scaler = Gst.ElementFactory.make('videoscale')
            cap_string = 'video/x-raw,width={},height={}'.format(int(self.width / 2), int(self.height / 2))
            caps = Gst.Caps.from_string(cap_string)
            self.scalerObject = Gst.ElementFactory.make('capsfilter')
            self.scalerObject.set_property('caps', caps)
            self.pipeline.add(decoder)
            self.pipeline.add(self.scalerObject)
            self.pipeline.add(scaler)
            decoder.link(self.tee)
            self.tee.link(scaler)
            scaler.link(self.scalerObject)

        sink = self.make_sink()

        self.pipeline.add(sink)
        self.src.link(filter)
        filter.link(parse)
        parse.link(decoder)
        self.scalerObject.link(sink)

        # connect encoder but do not start
        self.encoder, _ = get_recording_sink(port=self.port)

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
        width = int(self.width / 2)
        height = int(self.height / 2)
        if self.zoomed:
            self.zoomed = False
        else:
            self.zoomed = True
            width = self.width
            height = self.height

        self.stop()
        if self.hwaccel == 'vaapi':
            self.scalerObject.set_property('width', width)
            self.scalerObject.set_property('height', height)
        else:
            cap_string = 'video/x-raw,width={},height={}'.format(width, height)
            caps = Gst.Caps.from_string(cap_string)
            self.scalerObject.set_property('caps', caps)
        self.video_area.set_size_request(width, height)
        self.set_size_request(width, height)
        self.resize(width, height)
        self.start()

    def quit(self, sender, param):
        if self.subproc:
            self.subproc.terminate()
        super().quit(sender, param)


def main(**kwargs):

    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - MJPEGPipeWindow: {}'.format(kwargs.get('title', 'Unknown')))

    print('MJPEG main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = MJPEGPipeWindow(**kwargs)
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('MJPEG quitting', e, tb)
        if window:
            window.quit(None)
        raise e

# if run as script just display the window
if __name__ == "__main__":
    main()
