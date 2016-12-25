from collections import OrderedDict
import gi

# we need GStreamer 1.0 and Gtk 3.0
from ScreenRec.model.button import ButtonConfig

gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk

from .tools import make_settings_page
from .button import make_button_settings_page

current_item_index = None

def child_by_name(container, name):
    for item in container.get_children():
        if item.get_name() == name:
            return item
    return None


def get_current_item(config):
    global current_item_index

    if current_item_index:
        return config.buttons[current_item_index]
    return ButtonConfig()


def set_current_item(config, new):
    global current_item_index

    if current_item_index:
        config.buttons[current_item_index] = new


def remove_current_item(config, listview):
    current_item = get_current_item(config)
    if current_item:
        config.remove_button(current_item.id)


def reload_listview(config, listview):
    global current_item_index

    list_view_store = listview.get_model()
    list_view_store.clear()
    for button in config.buttons:
        list_view_store.append([button.title, button.id])
    if current_item_index:
        listview.set_cursor(current_item_index)


def on_add_button(sender, context):
    global current_item_index

    config, listview = context
    button = ButtonConfig()
    config.add_button(button)
    current_item_index = len(config.buttons) - 1
    reload_listview(config, listview)


def on_remove_button(sender, context):
    global current_item_index

    if current_item_index is None:
        return

    config, listview = context
    remove_current_item(config, listview)
    if len(config.buttons) == 0:
        current_item_index = None
    reload_listview(config, listview)


def on_type_changed(combobox, context):
    right_column, config = context
    current_item = get_current_item(config)

    index = combobox.get_active()
    if index is not None:
        model = combobox.get_model()
        entry = list(model[index])
        data = current_item.serialize()
        del data['button_type']
        current_item = ButtonConfig(button_type=entry[-1]).deserialize(data)
        set_current_item(config, current_item)

    box = child_by_name(right_column, 'settings')
    if box:
        right_column.remove(box)
    page = make_button_settings_page(current_item)
    page.set_name('settings')
    page.set_hexpand(True)
    page.set_vexpand(True)
    page.set_valign(Gtk.Align.FILL)
    right_column.pack_start(page, True, True, 0)
    page.show_all()


def on_listview_change(sender, context):
    global current_item_index

    config, right_column, config_type_combobox = context

    cursor = sender.get_cursor()
    if cursor.path is not None:
        if current_item_index:
            current_item = get_current_item(config)
            sender.get_model()[current_item_index][0] = current_item.title

        current_item_index = int(str(cursor.path))
        current_item = get_current_item(config)


        # select correct item in type box
        model = list(config_type_combobox.get_model())
        i = 0
        for item in model:
            if item[-1] == current_item.button_type:
                config_type_combobox.set_active(i)
                break
            i += 1
        #on_type_changed(config_type_combobox, (right_column, config))


def build_stack_page(config, size_groups):
    columns = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    columns.set_homogeneous(False)

    # left column, listview with defined buttons
    left_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    left_column.set_homogeneous(False)
    columns.pack_start(left_column, True, True, 0)

    # listview
    list_view_store = Gtk.ListStore(str, str)
    list_view = Gtk.TreeView.new_with_model(list_view_store)
    list_view.set_size_request(150, 300)
    left_column.pack_start(list_view, True, True, 0)

    renderer_text = Gtk.CellRendererText()
    column = Gtk.TreeViewColumn(title='Button')
    column.pack_start(renderer_text, True)
    column.add_attribute(renderer_text, "text", 0)
    list_view.append_column(column)

    reload_listview(config, list_view)

    size_groups[0].add_widget(list_view)

    # add / delete buttons
    list_view_buttons = Gtk.ActionBar()
    left_column.pack_start(list_view_buttons, True, True, 0)
    size_groups[0].add_widget(list_view_buttons)

    remove_button = Gtk.Button()
    icon = Gio.ThemedIcon(name="gtk-remove")
    image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
    remove_button.set_image(image)
    # remove_button.set_sensitive(len(config.buttons) > 0)
    remove_button.connect('clicked', on_remove_button, (config, list_view))
    list_view_buttons.pack_start(remove_button)

    add_button = Gtk.Button()
    icon = Gio.ThemedIcon(name="gtk-add")
    image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.BUTTON)
    add_button.set_image(image)
    add_button.connect('clicked', on_add_button, (config, list_view))
    list_view_buttons.pack_start(add_button)

    # config column
    type_store = Gtk.ListStore(str, str)

    right_column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    right_column.set_homogeneous(False)
    columns.pack_start(right_column, True, True, 0)

    # type combobox
    config_header = Gtk.HeaderBar()
    config_header.set_vexpand(False)
    config_header.set_valign(Gtk.Align.START)
    right_column.pack_start(config_header, True, True, 0)
    config_type_combobox = Gtk.ComboBox.new_with_model(type_store)
    renderer_text = Gtk.CellRendererText()
    config_type_combobox.pack_start(renderer_text, True)
    config_type_combobox.add_attribute(renderer_text, "text", 0)
    config_type_combobox.connect('changed', on_type_changed, (right_column, config))
    config_type_combobox.set_vexpand(False)
    config_header.set_custom_title(config_type_combobox)
    size_groups[1].add_widget(config_type_combobox)

    for item in ButtonConfig.VALID_SOURCES:
        type_store.append(item)

    list_view.connect('cursor-changed', on_listview_change, (config, right_column, config_type_combobox))

    return columns
