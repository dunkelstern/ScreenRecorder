import argparse
import os, subprocess
import platform
import threading

# gi is GObject instrospection
import gi

# we need GStreamer 1.0
gi.require_version('Gst', '1.0')
gi.require_version('GstNet', '1.0')
gi.require_version('GstRtsp', '1.0')

# Import GStreamer
from gi.repository import Gst, GObject, GstNet, GstRtsp, GLib

from ScreenRec.IPC import IPCWatcher
from ScreenRec.VideoEncoder import available_encoders, encoder_delay, get_recording_sink

class ScreenRecorder:

    ENCODERS = available_encoders
    ENCODER_DELAY = encoder_delay

    def __init__(self, mainloop=None, **kwargs):
        self.id = 'screen_recorder'
        self.mainloop = mainloop
        from ScreenRec.model.configfile import config

        if 'comm_queues' in kwargs:
            self.comm = IPCWatcher(kwargs['comm_queues'], self)
            self.comm.start()

        self.scale_width = kwargs.get('scale_width', config.rec_settings.scale_width)
        self.scale_height = kwargs.get('scale_height', config.rec_settings.scale_height)
        self.width = kwargs.get('width', config.rec_settings.width)
        self.height = kwargs.get('height', config.rec_settings.height)
        self.fps = kwargs.get('fps', config.rec_settings.fps)
        self.encoder = kwargs.get('encoder', config.rec_settings.encoder)
        if not self.encoder:
            self.encoder = ScreenRecorder.ENCODERS[0]
        self.display = kwargs.get('display', config.rec_settings.screen)
        self.port = kwargs.get('port', None)

        self.build_gst_pipeline(self.encoder)

    def build_gst_pipeline(self, encoding_method):
        # display src
        src = None

        if platform.system() == 'Linux':
            src = Gst.ElementFactory.make('ximagesrc', 'source')
            src.set_property('display-name', ':0.{}'.format(self.display))
            src.set_property('use-damage', 0)
            src.set_property('startx', 0)
            src.set_property('starty', 0)
            src.set_property('endx', self.width - 1)
            src.set_property('endy', self.height - 1)
        elif platform.system() == 'Darwin':
            src = Gst.ElementFactory.make('avfvideosrc', 'source')
            src.set_property('capture-screen', True)
            src.set_property('capture-screen-cursor', True)
            src.set_property('device-index', self.display)
        elif platform.system() == 'Windows':
            src = Gst.ElementFactory.make('dx9screencapsrc', 'source')
            src.set_property('x', 0)
            src.set_property('y', 0)
            src.set_property('width', self.width - 1)
            src.set_property('height', self.height - 1)
            src.set_property('monitor', self.display)
        src.set_property('do-timestamp', True)

        queue = Gst.ElementFactory.make('queue')

        # assemble pipeline
        self.pipeline = Gst.Pipeline.new('playback')
        self.pipeline.use_clock(Gst.SystemClock.obtain())

        self.pipeline.add(src)
        self.pipeline.add(queue)
        src.link(queue)

        sink, self.sink = get_recording_sink(
            scale_width=self.scale_width if self.scale_width else self.width,
            scale_height=self.scale_height if self.scale_height else self.height,
            fps=self.fps,
            encoder=self.encoder,
            port=self.port
        )

        self.pipeline.add(sink)
        queue.link(sink)

        self.create_bus()

    def create_bus(self):
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

    def start(self, path=None):
        if path:
            self.sink.set_property('location', path)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self):
        if self.pipeline:
            eos = Gst.Event.new_eos()
            self.pipeline.send_event(eos)
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = None
        if self.mainloop:
            self.mainloop.quit()
            self.comm.join()


def main(**kwargs):
    if 'filename' not in kwargs and 'port' not in kwargs:
        raise AttributeError('you have to set filename or port')

    from ScreenRec.model.configfile import config
    display = kwargs.get('display', config.rec_settings.screen)
    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - ScreenCapture for display {}'.format(display))

    # Initialize Gstreamer
    GObject.threads_init()
    mainloop = GObject.MainLoop()
    Gst.init(None)

    # Start screen recorder
    if 'filename' in kwargs:
        recorder = ScreenRecorder(mainloop=mainloop, **kwargs)
        recorder.start(path=kwargs['filename'])
    else:
        recorder = ScreenRecorder(mainloop=mainloop, **kwargs)
        recorder.start()

    # run the main loop
    try:
        mainloop.run()
    except:
        recorder.stop()
        mainloop.quit()

# if run as script start recording
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Record the screen')
    parser.add_argument(
        '-d', '--display',
        type=int,
        nargs=1,
        default=0,
        dest='display',
        help='display index to capture'
    )
    parser.add_argument(
        '-x', '--width',
        type=int,
        nargs=1,
        default=1920,
        dest='width',
        help='width of the screen area to capture'
    )
    parser.add_argument(
        '-y', '--height',
        type=int,
        nargs=1,
        default=1080,
        dest='height',
        help='height of the screen area to capture'
    )
    parser.add_argument(
        '--scaled-width',
        type=int,
        nargs=1,
        default=None,
        dest='scaled_width',
        help='width of the recorded video file'
    )
    parser.add_argument(
        '--scaled-height',
        type=int,
        nargs=1,
        default=None,
        dest='scaled_height',
        help='height of the recorded video file'
    )
    parser.add_argument(
        '-e', '--encoder',
        type=str,
        nargs=1,
        dest='encoder',
        default=ScreenRecorder.ENCODERS[0],
        choices=ScreenRecorder.ENCODERS,
        help='encoder to use'
    )
    parser.add_argument(
        '-p', '--port',
        type=int,
        nargs=1,
        dest='port',
        default=7655,
        help='do not save to file but stream to port'
    )
    parser.add_argument(
        'filename',
        nargs="*",
        type=str,
        help='output file'
    )
    args = parser.parse_args()

    if args.filename:
        main(
            filename=args.filename[0],
            width=args.width,
            height=args.height,
            scale_width=args.scaled_width,
            scale_height=args.scaled_height,
            encoder=args.encoder,
            display=args.display
        )
    else:
        main(
            port=args.port[0],
            width=args.width,
            height=args.height,
            scale_width=args.scaled_width,
            scale_height=args.scaled_height,
            encoder=args.encoder,
            display=args.display
        )
