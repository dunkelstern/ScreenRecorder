import signal

# gi is GObject instrospection
import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, GObject, GLib

from ScreenRec.gui.GtkMainWindow import ControlWindow

# Signal handler to allow HUP, INT and TERM signal handling
def InitSignal(gui):
    def signal_action(signal):
        if signal is 1:
            print("Caught signal SIGHUP(1)")
            return
        elif signal is 2:
            print("Caught signal SIGINT(2)")
        elif signal is 15:
            print("Caught signal SIGTERM(15)")
        gui.quit(None, None)

    def idle_handler(*args):
        GLib.idle_add(signal_action, priority=GLib.PRIORITY_HIGH)

    def handler(*args):
        signal_action(args[0])

    def install_glib_handler(sig):
        unix_signal_add = None

        if hasattr(GLib, "unix_signal_add"):
            unix_signal_add = GLib.unix_signal_add
        elif hasattr(GLib, "unix_signal_add_full"):
            unix_signal_add = GLib.unix_signal_add_full

        if unix_signal_add:
            unix_signal_add(GLib.PRIORITY_HIGH, sig, handler, sig)
        else:
            print("Can't install GLib signal handler, too old gi.")

    SIGS = [getattr(signal, s, None) for s in "SIGINT SIGTERM SIGHUP".split()]
    for sig in filter(None, SIGS):
        signal.signal(sig, idle_handler)
        GLib.idle_add(install_glib_handler, sig, priority=GLib.PRIORITY_HIGH)


if __name__ == "__main__":
    from setproctitle import setproctitle
    setproctitle('ScreenRecorder - Main Window')

    GObject.threads_init()
    InitSignal(ControlWindow())
    Gtk.main()
