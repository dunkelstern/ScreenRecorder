# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, GObject

from ScreenRec.GtkMainWindow import ControlWindow

if __name__ == "__main__":
	GObject.threads_init()
	ControlWindow()
	Gtk.main()