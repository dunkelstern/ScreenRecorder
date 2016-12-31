import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk, Gst


from ScreenRec.VideoEncoder import get_recording_sink
from ScreenRec.IPC import IPCWatcher

class Watcher(IPCWatcher):

    def __init__(self, queues, main):
        super().__init__(queues, main)
        self.tee_pad = None

    def run_command(self, command):
        if 'quit' in command and command['quit'] == True:
            print('resetting comm')
            self.main.comm = None
            self.main.quit(None, None)

        if 'raise' in command:
            self.main.present()

        if 'record' in command:
            # add encoder to pipeline
            self.main.pipeline.add(self.main.encoder)

            # get a tee pad and hook it up
            self.tee_pad = self.main.tee.get_request_pad('src_%u')
            Gst.Element.link_pads(self.main.tee, self.tee_pad.get_name(), self.main.encoder, 'sink')

            # run encoder
            self.main.encoder.set_state(Gst.State.PLAYING)
        if 'stop' in command:
            if self.main.excl_button.get_active():
                self.main.excl_button.disconnect(self.main.excl_button_signal)
                context = button.get_style_context()
                self.main.excl_button.set_active(False)
                context.remove_class('destructive-action')
                self.main.excl_button_signal = self.main.excl_button.connect('toggled', on_excl, self)

            # unlink encoder from tee and destroy pad
            Gst.Element.unlink_pads(self.main.tee, self.tee_pad.get_name(), self.main.encoder, 'sink')
            self.main.tee.release_request_pad(self.tee_pad)
            self.tee_pad = None
            
            # send end of stream to encoder
            eos = Gst.Event.new_eos()
            self.main.encoder.send_event(eos)
            self.main.encoder.set_state(Gst.State.NULL)

            # remove from pipeline again
            self.main.pipeline.remove(self.main.encoder)

def on_excl(button, self):
    context = button.get_style_context()
    if button.get_active():
        context.add_class('destructive-action')
        self.comm.outQueue.put({ 'exclusive': self.id })
    else:
        context.remove_class('destructive-action')
        self.comm.outQueue.put({ 'cooperative': self.id })  

def make_excl_button(self):
    self.excl_button = Gtk.ToggleButton('Exclusive')
    self.excl_button_signal = self.excl_button.connect('toggled', on_excl, self)
    self.header.pack_end(self.excl_button)


