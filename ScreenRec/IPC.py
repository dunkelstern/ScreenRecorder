import threading

# gi is GObject instrospection
import gi
from gi.repository import GObject, GLib

class IPCWatcher(threading.Thread):

    def __init__(self, queues, main):
        self.outQueue, self.inQueue = queues
        self.main = main
        super().__init__()

    def run(self):
        quit = False
        while not quit:
            command = self.inQueue.get()

            print('IPC got {}'.format(command))
            if 'quit' in command:
                quit = True
            GLib.idle_add(self.run_command, command)

    def run_command(self, command):
        if 'quit' in command:
            self.main.stop()