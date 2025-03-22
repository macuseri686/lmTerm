#!/usr/bin/env python3

import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio

from window import LmTermWindow

class LmTermApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.lmstudio.lmterm',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        
    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LmTermWindow(application=self)
        win.present()

def main():
    app = LmTermApplication()
    return app.run(sys.argv)

if __name__ == '__main__':
    sys.exit(main()) 