#!/usr/bin/env python3

import sys
import gi
import os

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, Gdk

from window import LmTermWindow

class LmTermApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.lmstudio.lmterm',
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        
    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = LmTermWindow(application=self)
        
        # Load CSS
        self.load_css()
        
        win.present()
    
    def load_css(self):
        """Load CSS from style.css file"""
        css_provider = Gtk.CssProvider()
        
        # Try to find the CSS file in different locations
        css_file = None
        possible_paths = [
            # Current directory
            "style.css",
            # Same directory as the script
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css"),
            # Data directory
            os.path.join(sys.prefix, "share", "lmterm", "style.css"),
            # User config directory
            os.path.join(os.path.expanduser("~"), ".config", "lmterm", "style.css")
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                css_file = path
                break
        
        if css_file:
            print(f"Loading CSS from: {css_file}")
            css_provider.load_from_path(css_file)
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        else:
            print("Warning: style.css file not found")

def main():
    app = LmTermApplication()
    return app.run(sys.argv)

if __name__ == '__main__':
    sys.exit(main()) 