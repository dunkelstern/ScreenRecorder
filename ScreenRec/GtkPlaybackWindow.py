# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, GObject, Gdk, GLib

# Import GStreamer
from gi.repository import Gst

# Used for reparenting output window
gi.require_version('GstVideo', '1.0')
from gi.repository import GdkX11, GstVideo  # Needed even if pycharm does not know why!


# Base class for a playback window
class PlaybackWindow(Gtk.Window):
    def __init__(self, data=None, title="Video Out"):
        # initialize window
        Gtk.Window.__init__(self, title=title)

        # allocate video area
        self.video_area = Gtk.DrawingArea()
        self.video_area.override_background_color(0, Gdk.RGBA.from_color(Gdk.color_parse("black")))
        # self.video_area.set_property('force-aspect-ratio', True)
        self.add(self.video_area)

        # add header bar
        self.header = Gtk.HeaderBar()
        self.header.set_show_close_button(True)
        self.header.props.title = title
        self.set_titlebar(self.header)

        # add enable switch
        self.switch = Gtk.Switch()
        self.switch.connect("notify::active", self.on_play)
        self.switch.set_active(False)
        self.header.pack_start(self.switch)


        # add zoom button
        self.zoom_button = Gtk.Button()
        icon = Gio.ThemedIcon(name="zoom-fit-symbolic")
        image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
        self.zoom_button.set_image(image)
        self.zoom_button.connect('clicked', self.on_zoom)
        self.header.pack_end(self.zoom_button)

        # no border
        self.set_border_width(0)
        self.set_keep_above(True)

        # build GStreamer pipeline, will be overridden by subclass
        self.build_gst_pipeline(data)

        # on quit run callback to stop pipeline
        self.connect("delete-event", self.quit)


    def show(self, width=640, height=480, fixed=False):
        # show all window elements
        self.show_all()
        self.xid = self.video_area.get_property('window').get_xid()

        # resize the window and disable resizing by user if needed
        self.set_default_size(width, height)
        if fixed:
            self.set_resizable(False)

        # start the pipeline
        self.run_bus()

        # on quit run callback to stop pipeline
        self.connect("delete-event", self.quit)

    def quit(self, sender, param):
        # on quit stop pipeline to avoid core dump
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()

    def on_zoom(self, src):
        # overridden by subclasses
        pass

    def build_gst_pipeline(self, data):
        # overridden by subclasses
        self.pipeline = None

    def run_bus(self):
        # create a bus
        self.bus = self.pipeline.get_bus()

        # we want signal watchers and message emission
        self.bus.add_signal_watch()
        self.bus.enable_sync_message_emission()

        # on message print errors
        self.bus.connect('message', self.on_message)

        # connect sync message to reparent output window
        self.bus.connect("sync-message::element", self.on_sync_message)

        self.switch.set_active(True)

    def on_message(self, bus, message):
        def set_switch(active):
            self.switch.set_active(active)

        t = message.type

        if t == Gst.MessageType.EOS:
            # end of stream, just disable the switch and stop processing
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            GLib.idle_add(set_switch, False)
        if t == Gst.MessageType.ERROR:
            # some error occured, log and stop
            print('ERROR: ', message.parse_error())
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            GLib.idle_add(set_switch, False)

    def on_play(self, switch, gparam):
        if switch.get_active():
            # user turned on the switch, start the pipeline
            if self.pipeline:
                self.pipeline.set_state(Gst.State.PLAYING)
        else:
            # user turned off the switch, reset pipeline
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)

    def on_sync_message(self, bus, message):
        # on preparing the window handle reparent
        if message.get_structure().get_name() == 'prepare-window-handle':
            imagesink = message.src
            imagesink.set_window_handle(self.xid)