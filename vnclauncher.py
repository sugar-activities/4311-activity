# Copyright (C) 2007, Eduardo Silva <edsiper@gmail.com>.
# Copyright (C) 2008, One Laptop Per Child
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os

import logging
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Vte
from gi.repository import Pango
import dbus

from sugar3.activity import activity
from sugar3 import env
import ConfigParser
import os.path
import platform
from jarabe.model import network
import struct
import socket


class VncLauncherActivity(activity.Activity):

    def _ipaddr_(self, button):
        self.ipbutton = button
        button.set_label('Please Click to find current IP address \n\n' +
                         'Error!! check connection')
        bus = dbus.SystemBus()
        obj = bus.get_object(network.NM_SERVICE, network.NM_PATH)
        netmgr = dbus.Interface(obj, network.NM_IFACE)
        netmgr.GetDevices(reply_handler=self.__get_devices_reply_cb,
                          error_handler=self.__get_devices_error_cb)

    def __get_devices_reply_cb(self, devices):
        bus = dbus.SystemBus()
        for device_op in devices:
            device = bus.get_object(network.NM_SERVICE, device_op)
            device_props = dbus.Interface(device, dbus.PROPERTIES_IFACE)
            ip_address = device_props.Get(
                network.NM_DEVICE_IFACE, 'Ip4Address')
            ipaddr = socket.inet_ntoa(struct.pack('I', ip_address))
            if ipaddr != "0.0.0.0" and ipaddr != "127.0.0.1":
                self.ipbutton.set_label(
                    'Please Click to find current IP address \n\nIP=' + ipaddr)

    def __get_devices_error_cb(self, err):
        pass

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        logging.debug('Starting the X11 VNC activity')

        self.set_title(_('X11 VNC Server Activity'))
        self.connect('key-press-event', self.__key_press_cb)
        args = "Please Click to find current IP address"
        box = Gtk.HBox(False, 10)
        table = Gtk.Table(4, 1, True)
        button = Gtk.Button(args)
        button.connect("clicked", self._ipaddr_)
        table.attach(button, 0, 1, 0, 1,
                     Gtk.AttachOptions.FILL | Gtk.AttachOptions.EXPAND,
                     Gtk.AttachOptions.EXPAND | Gtk.AttachOptions.FILL, 25, 25)
        button.show()
        button = Gtk.Button("Start X11 VNC Server")
        button.connect("clicked", self.connectVNC)
        table.attach(button, 0, 1, 1, 2,
                     Gtk.AttachOptions.FILL | Gtk.AttachOptions.EXPAND,
                     Gtk.AttachOptions.FILL | Gtk.AttachOptions.EXPAND, 25, 25)
        button.show()

        button = Gtk.Button("Stop X11 VNC Server")
        button.connect("clicked", self.stopVNC)
        table.attach(button, 0, 1, 2, 3, Gtk.AttachOptions.FILL,
                     Gtk.AttachOptions.FILL, 25, 25)
        button.show()

        button = Gtk.Button("Exit VncLauncherActivity")
        button.connect("clicked", lambda w: Gtk.main_quit())
        table.attach(button, 0, 1, 3, 4, Gtk.AttachOptions.FILL,
                     Gtk.AttachOptions.FILL, 25, 25)
        button.show()
        table.show()

        self._vte = VTE()
        self._vte.show()

        box.pack_start(self._vte, True, True, 0)
        box.pack_start(table, False, False, 0)

        self.set_canvas(box)
        box.show()

    def stopVNC(self, button):

        cmd = "\x03"  # Ctrl+C
        self._vte.feed_child(cmd, -1)

    def connectVNC(self, button):
        self._vte.grab_focus()
        # check if x11vnc is installed
        cmd = '/usr/bin/x11vnc'
        if os.path.isfile(cmd) and os.access(cmd, os.X_OK):
            logging.error('Using x11vnc installed in the system')
        else:
            # check platform
            if platform.machine().startswith('arm'):
                path = os.path.join(activity.get_bundle_path(), 'bin/arm')
            else:
                if platform.architecture()[0] == '64bit':
                    path = os.path.join(activity.get_bundle_path(),
                                        'bin/x86-64')
                else:
                    path = os.path.join(activity.get_bundle_path(), 'bin/x86')
            self._vte.feed_child(
                "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:%s/lib\n" % path, -1)
            cmd = os.path.join(path, 'x11vnc') + "\n"
            logging.error('Using %s', cmd)
        self._vte.feed_child(cmd, -1)

    def __key_press_cb(self, window, event):
        return False


class VTE(Vte.Terminal):

    def __init__(self):
        Vte.Terminal.__init__(self)
        self._configure_vte()
        if hasattr(Vte.Terminal, "spawn_sync"):
            self.connect("child-exited", lambda term: term.spawn_sync(
                Vte.PtyFlags.DEFAULT, os.environ["HOME"], ["/bin/bash"], [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD, None, None))
        else:
            self.connect("child-exited", lambda term: term.fork_full_command(
                Vte.PtyFlags.DEFAULT, os.environ["HOME"], ["/bin/bash"], [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD, None, None))

        os.chdir(os.environ["HOME"])
        if hasattr(Vte.Terminal, "spawn_sync"):
            self.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                os.environ["HOME"],
                ["/bin/bash"],
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None)
        else:
            self.fork_command_full(
                Vte.PtyFlags.DEFAULT,
                os.environ["HOME"],
                ["/bin/bash"],
                [],
                GLib.SpawnFlags.DO_NOT_REAP_CHILD,
                None,
                None)

    def _configure_vte(self):
        conf = ConfigParser.ConfigParser()
        conf_file = os.path.join(env.get_profile_path(), 'terminalrc')

        if os.path.isfile(conf_file):
            f = open(conf_file, 'r')
            conf.readfp(f)
            f.close()
        else:
            conf.add_section('terminal')

        if conf.has_option('terminal', 'font'):
            font = conf.get('terminal', 'font')
        else:
            font = 'Monospace 8'
            conf.set('terminal', 'font', font)
        self.set_font(Pango.FontDescription(font))

        if conf.has_option('terminal', 'fg_color'):
            fg_color = conf.get('terminal', 'fg_color')
        else:
            fg_color = '#000000'
            conf.set('terminal', 'fg_color', fg_color)
        if conf.has_option('terminal', 'bg_color'):
            bg_color = conf.get('terminal', 'bg_color')
        else:
            bg_color = '#FFFFFF'
            conf.set('terminal', 'bg_color', bg_color)
        self.set_colors(Gdk.color_parse(fg_color),
                        Gdk.color_parse(bg_color),
                        [])

        if conf.has_option('terminal', 'cursor_blink'):
            blink = conf.getboolean('terminal', 'cursor_blink')
        else:
            blink = False
            conf.set('terminal', 'cursor_blink', blink)

        self.set_cursor_blink_mode(blink)

        if conf.has_option('terminal', 'bell'):
            bell = conf.getboolean('terminal', 'bell')
        else:
            bell = False
            conf.set('terminal', 'bell', bell)
        self.set_audible_bell(bell)

        if conf.has_option('terminal', 'scrollback_lines'):
            scrollback_lines = conf.getint('terminal', 'scrollback_lines')
        else:
            scrollback_lines = 1000
            conf.set('terminal', 'scrollback_lines', scrollback_lines)

        self.set_scrollback_lines(scrollback_lines)
        self.set_allow_bold(True)

        if conf.has_option('terminal', 'scroll_on_keystroke'):
            scroll_key = conf.getboolean('terminal', 'scroll_on_keystroke')
        else:
            scroll_key = False
            conf.set('terminal', 'scroll_on_keystroke', scroll_key)
        self.set_scroll_on_keystroke(scroll_key)

        if conf.has_option('terminal', 'scroll_on_output'):
            scroll_output = conf.getboolean('terminal', 'scroll_on_output')
        else:
            scroll_output = False
            conf.set('terminal', 'scroll_on_output', scroll_output)
        self.set_scroll_on_output(scroll_output)

        if conf.has_option('terminal', 'emulation'):
            emulation = conf.get('terminal', 'emulation')
        else:
            emulation = 'xterm'
            conf.set('terminal', 'emulation', emulation)
        self.set_emulation(emulation)

        if conf.has_option('terminal', 'visible_bell'):
            visible_bell = conf.getboolean('terminal', 'visible_bell')
        else:
            visible_bell = False
            conf.set('terminal', 'visible_bell', visible_bell)
        self.set_visible_bell(visible_bell)
        conf.write(open(conf_file, 'w'))

    def on_gconf_notification(self, client, cnxn_id, entry, what):
        self.reconfigure_vte()

    def on_vte_button_press(self, term, event):
        if event.button == 3:
            self.do_popup(event)
            return True

    def on_vte_popup_menu(self, term):
        pass
