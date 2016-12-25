# gi is GObject instrospection
import signal

import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, GObject

from ScreenRec.gui.GtkMainWindow import ControlWindow


if __name__ == "__main__":
    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - Main Window')

    signal.signal(signal.SIGINT, signal.SIG_DFL)  # Allow quitting by SIGINT/Ctrl+C
    try:
        GObject.threads_init()
        ControlWindow()
        Gtk.main()
    except KeyboardInterrupt:
        Gtk.main_quit()
