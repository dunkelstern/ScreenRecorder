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
                print(' - {} connected to {}'.format(src[1].get_name(), src[1].peer.get_parent_element().name))
                print('   caps: {}'.format(src[1].props.caps))
            except AttributeError:
                print(' - {} UNCONNECTED'.format(src[1].get_name()))
                print('   caps: {}'.format(src[1].props.caps))
            src = sub_iterator.next()

        sub_iterator = element.iterate_sink_pads()
        sink = sub_iterator.next()
        while sink[0] != Gst.IteratorResult.DONE:
            try:
                print(' - {} connected to {}'.format(sink[1].get_name(), sink[1].peer.get_parent_element().name))
                print('   caps: {}'.format(sink[1].props.caps))
            except AttributeError:
                print(' - {} UNCONNECTED'.format(sink[1].get_name()))
                print('   caps: {}'.format(sink[1].props.caps))
            sink = sub_iterator.next()

        item = iterator.next()
