import gi

# we need GStreamer 1.0 and Gtk 3.0
gi.require_version('Gst', '1.0')
gi.require_version('Gtk', '3.0')

# import everything we need for a Gtk Window
from gi.repository import Gtk, Gio, Gdk


def on_spinner_changed(spinner, config):
    setattr(config, spinner.get_name(), spinner.get_value())


def on_textbox_changed(textbox, config):
    setattr(config, textbox.get_name(), textbox.get_text())


def on_switch_changed(switch, param, config):
    setattr(config, switch.get_name(), switch.get_active())


def on_combobox_changed(combo, config):
    index = combo.get_active()
    if index is not None:
        model = combo.get_model()
        entry = list(model[index])
        setattr(config, combo.get_name(), entry[-1])


def make_settings_page(container, config, layout, size_groups=None):
    container.set_row_spacing(10)
    container.set_column_spacing(10)
    container.set_border_width(10)

    last_item = None
    for setting, (setting_type, default) in layout.items():
        label = Gtk.Label(setting.replace("_", " ").title())
        label.set_halign(Gtk.Align.END)
        label.set_xalign(0)
        label.set_vexpand(False)
        label.set_justify(Gtk.Justification.LEFT)
        container.attach_next_to(label, last_item, Gtk.PositionType.BOTTOM, 1, 1)
        if size_groups and size_groups[0]:
            size_groups[0].add_widget(label)

        if isinstance(setting_type, list):
            # combobox

            # create appropriate list store
            types = []
            if isinstance(setting_type[0], tuple):
                for item in setting_type[0]:
                    types.append(type(item))
            else:
                types = [type(setting_type[0])]

            list_store = Gtk.ListStore(*types)
            combobox = Gtk.ComboBox.new_with_model(list_store)
            renderer_text = Gtk.CellRendererText()
            combobox.pack_start(renderer_text, True)
            combobox.add_attribute(renderer_text, "text", 0)

            for item in setting_type:
                if isinstance(item, tuple):
                    list_store.append(item)
                else:
                    list_store.append([item])

            try:
                i = 0
                for item in setting_type:
                    if isinstance(item, tuple):
                        if item[-1] == default:
                            combobox.set_active(i)
                    else:
                        if item == default:
                            combobox.set_active(i)
                    i += 1
            except ValueError:
                combobox.set_active(0)
            combobox.set_name(setting)
            combobox.set_hexpand(True)
            combobox.connect('changed', on_combobox_changed, config)
            container.attach_next_to(combobox, label, Gtk.PositionType.RIGHT, 1, 1)
            if size_groups and size_groups[1]:
                size_groups[1].add_widget(combobox)
        elif setting_type == 'int':
            # spinner
            adjustment = Gtk.Adjustment(default[0], default[1], default[2], 1, 100, 0)
            spinner = Gtk.SpinButton.new(adjustment, 100, 0)
            spinner.set_value(default[0])
            spinner.set_name(setting)
            spinner.set_hexpand(True)
            spinner.connect('value-changed', on_spinner_changed, config)
            container.attach_next_to(spinner, label, Gtk.PositionType.RIGHT, 1, 1)
            if size_groups and size_groups[1]:
                size_groups[1].add_widget(spinner)
        elif setting_type == 'float':
            # spinner with decimal
            adjustment = Gtk.Adjustment(default[0], default[1], default[2], 1, 100, 0)
            spinner = Gtk.SpinButton.new(adjustment, 100, 2)
            spinner.set_value(default[0])
            spinner.set_name(setting)
            spinner.set_hexpand(True)
            spinner.connect('value-changed', on_spinner_changed, config)
            container.attach_next_to(spinner, label, Gtk.PositionType.RIGHT, 1, 1)
            if size_groups and size_groups[1]:
                size_groups[1].add_widget(spinner)
        elif setting_type == 'bool':
            switch = Gtk.Switch()
            switch.set_active(default)
            switch.set_name(setting)
            switch.connect('notify::active', on_switch_changed, config)
            container.attach_next_to(switch, label, Gtk.PositionType.RIGHT, 1, 1)
            if size_groups and size_groups[1]:
                size_groups[1].add_widget(switch)
        elif setting_type == 'string':
            # textbox
            textbox = Gtk.Entry()
            textbox.set_text(default)
            textbox.set_name(setting)
            textbox.set_hexpand(True)
            textbox.connect('changed', on_textbox_changed, config)
            container.attach_next_to(textbox, label, Gtk.PositionType.RIGHT, 1, 1)
            if size_groups and size_groups[1]:
                size_groups[1].add_widget(textbox)
        elif setting_type == 'filepicker':
            # file picker box
            picker = Gtk.Entry.new()
            picker.set_text(default)
            picker.set_name(setting)
            picker.set_hexpand(True)
            picker.connect('changed', on_textbox_changed, config)
            container.attach_next_to(picker, label, Gtk.PositionType.RIGHT, 1, 1)
            if size_groups and size_groups[1]:
                size_groups[1].add_widget(picker)
