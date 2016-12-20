# gi is GObject instrospection
import gi

# we need GStreamer 1.0
gi.require_version('Gst', '1.0')

# Import GStreamer
from gi.repository import Gst, GObject


def dump_pipeline(pipeline):
    iterator = pipeline.iterate_sorted()
    item = iterator.next()
    while item[0] != Gst.IteratorResult.DONE:
        element = item[1]
        print("{} ({}):".format(type(element).__name__, element.name))

        sub_iterator = element.iterate_src_pads()
        src = sub_iterator.next()
        while src[0] != Gst.IteratorResult.DONE:
            try:
                print(' - src connected to', src[1].peer.get_parent_element().name)
            except AttributeError:
                print(' - src UNCONNECTED')
            src = sub_iterator.next()

        sub_iterator = element.iterate_sink_pads()
        sink = sub_iterator.next()
        while sink[0] != Gst.IteratorResult.DONE:
            try:
                print(' - sink connected to', sink[1].peer.get_parent_element().name)
            except AttributeError:
                print(' - sink UNCONNECTED')
            sink = sub_iterator.next()

        item = iterator.next()
