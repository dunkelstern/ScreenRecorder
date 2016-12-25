import sys

import gi

# we need GStreamer 1.0 and Gtk 3.0

gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# Import GStreamer
from gi.repository import Gst, GObject, Gtk

from ScreenRec.gui.GtkPlaybackWindow import PlaybackWindow, available_hwaccels


# This one is a Webcam window
class V4L2Window(PlaybackWindow):

    HW_ACCELS = available_hwaccels

    # Initialize window
    def __init__(self, device='/dev/video0', title="Webcam", format="image/jpeg", width=1280, height=720, framerate=20, hwaccel='opengl'):
        self.format = format
        self.width = width
        self.height = height
        self.framerate = framerate

        # Build window
        super().__init__(data=device, title=title, hwaccel=hwaccel)

        # No additional window elements, just show the window with fixed width and height
        self.show(width=int(width/2), height=int(height/2), fixed=True)
        self.zoomed = False

    # build GStreamer pipeline for this window
    def build_gst_pipeline(self, device):

        # v4l src
        v4lsrc = Gst.ElementFactory.make('v4l2src', 'source')
        v4lsrc.set_property('device', device)

        src = Gst.Bin.new('src')
        src.add(v4lsrc)

        # get stream
        cap_string = '{format},width={width},height={height},framerate={framerate}/1'.format(
            format=self.format,
            width=self.width,
            height=self.height,
            framerate=self.framerate
        )
        caps = Gst.Caps.from_string(cap_string)
        filter = Gst.ElementFactory.make('capsfilter', 'sink')
        filter.set_property('caps', caps)
        src.add(filter)
        v4lsrc.link(filter)

        if self.format == 'image/jpeg':
            # parse, decode and scale with hardware acceleration
            parse = Gst.ElementFactory.make('jpegparse')
            src.add(parse)
            v4lsrc.link(parse)

            decoder = None
            if self.hwaccel == 'opengl' or self.hwaccel == 'xvideo':
                decoder = Gst.ElementFactory.make('jpegdec')
            elif self.hwaccel == 'vaapi':
                decoder = Gst.ElementFactory.make('vaapijpegdec')

            src.add(decoder)
            filter.link(parse)
            parse.link(decoder)

            ghost_src = Gst.GhostPad.new('src', decoder.get_static_pad('src'))
            src.add_pad(ghost_src)
        else:
            ghost_src = Gst.GhostPad.new('src', filter.get_static_pad('src'))
            src.add_pad(ghost_src)

        scaler = Gst.Bin.new('scaler')
        if self.hwaccel == 'vaapi':
            self.scalerObject = Gst.ElementFactory.make('vaapipostproc')
            self.scalerObject.set_property('width', int(self.width / 2))
            self.scalerObject.set_property('height', int(self.height / 2))
            self.scalerObject.set_property('scale-method', 2)
            scaler.add(self.scalerObject)

            ghost_sink = Gst.GhostPad.new('sink', self.scalerObject.get_static_pad('sink'))
            ghost_src = Gst.GhostPad.new('src', self.scalerObject.get_static_pad('src'))
            scaler.add_pad(ghost_sink)
            scaler.add_pad(ghost_src)
        else:
            videoscale = Gst.ElementFactory.make('videoscale')
            scaler.add(videoscale)

            cap_string = 'video/x-raw,width={},height={}'.format(int(self.width / 2), int(self.height / 2))
            caps = Gst.Caps.from_string(cap_string)
            self.scalerObject = Gst.ElementFactory.make('capsfilter')
            self.scalerObject.set_property('caps', caps)
            scaler.add(self.scalerObject)

            videoscale.link(self.scalerObject)

            ghost_sink = Gst.GhostPad.new('sink', videoscale.get_static_pad('sink'))
            ghost_src = Gst.GhostPad.new('src', self.scalerObject.get_static_pad('src'))
            scaler.add_pad(ghost_sink)
            scaler.add_pad(ghost_src)

        sink = self.make_sink()

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.add(src)
        self.pipeline.add(scaler)
        self.pipeline.add(sink)
        src.link(scaler)
        scaler.link(sink)

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
        if self.pipeline:
            self.pipeline.set_state(Gst.State.PLAYING)

    def on_message(self, bus, message):
        call_super = True
        t = message.type
        if t == Gst.MessageType.ERROR:
            # some error occured, log and stop
            e, _ = message.parse_error()

            if e.domain == 'gst-resource-error-quark' and e.code == 3:
                print("Video source not found")

                if self.pipeline:
                    self.pipeline.set_state(Gst.State.NULL)
                    v4lsrc = Gst.ElementFactory.make('videotestsrc', 'source')

                    src = Gst.Bin.new('src')
                    src.add(v4lsrc)

                    # get stream
                    cap_string = 'video/x-raw,format=NV12,width={width},height={height},framerate={framerate}/1'.format(
                        width=self.width,
                        height=self.height,
                        framerate=self.framerate
                    )
                    caps = Gst.Caps.from_string(cap_string)
                    filter = Gst.ElementFactory.make('capsfilter', 'sink')
                    filter.set_property('caps', caps)
                    src.add(filter)
                    v4lsrc.link(filter)

                    ghost_src = Gst.GhostPad.new('src', filter.get_static_pad('src'))
                    src.add_pad(ghost_src)

                    original_src = self.pipeline.get_by_name('src')
                    self.pipeline.remove(original_src)
                    self.pipeline.add(src)
                    src.link(self.pipeline.get_by_name('scaler'))

                    self.pipeline.set_state(Gst.State.PLAYING)
                call_super = False
        if call_super:
            super().on_message(bus, message)

def main(device='/dev/video0', title="Webcam", format="image/jpeg", width=1280, height=720, framerate=20, hwaccel='opengl'):
    print('v4l2 main called')
    window = None
    try:
        GObject.threads_init()
        Gst.init(None)
        window = V4L2Window(
            device=device,
            title=title,
            format=format,
            width=width,
            height=height,
            framerate=framerate,
            hwaccel=hwaccel
        )
        Gtk.main()
    except Exception as e:
        tb = sys.exc_info()[2]
        print('v4l2 quitting', e)
        if window:
            window.quit(None)
        raise e

# if run as script just display the window
if __name__ == "__main__":
    main()
