import gi
import re
from html import escape

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Pango, GLib, Gdk

class MarkdownRenderer:
    """A class to render Markdown text as Pango markup for GTK widgets"""
    
    @staticmethod
    def markdown_to_pango(text):
        """Convert markdown text to Pango markup"""
        if not text:
            return ""
            
        # Escape HTML entities first (but preserve existing markup)
        text = escape(text, quote=False)
        
        # Process code blocks with syntax highlighting
        text = MarkdownRenderer._process_code_blocks(text)
        
        # Process inline code - use #f0f0f0 instead of rgba()
        # Make sure to process inline code BEFORE other formatting to avoid conflicts
        text = re.sub(r'`([^`]+)`', r'<span background="#f0f0f0" font_family="monospace">\1</span>', text)
        
        # Process bold text
        text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'__([^_]+)__', r'<b>\1</b>', text)
        
        # Process italic text - make sure it doesn't conflict with already processed elements
        # Use non-greedy matching and exclude already processed tags
        text = re.sub(r'\*([^*<>]+?)\*', r'<i>\1</i>', text)
        text = re.sub(r'_([^_<>]+?)_', r'<i>\1</i>', text)
        
        # Process headers
        text = re.sub(r'^# (.+)$', r'<span size="xx-large"><b>\1</b></span>', text, flags=re.MULTILINE)
        text = re.sub(r'^## (.+)$', r'<span size="x-large"><b>\1</b></span>', text, flags=re.MULTILINE)
        text = re.sub(r'^### (.+)$', r'<span size="large"><b>\1</b></span>', text, flags=re.MULTILINE)
        
        # Process bullet lists - use Unicode bullet character directly
        text = re.sub(r'^- (.+)$', r'• \1', text, flags=re.MULTILINE)
        text = re.sub(r'^\* (.+)$', r'• \1', text, flags=re.MULTILINE)
        
        # Process numbered lists
        # This is a simple implementation that doesn't handle nested lists
        text = re.sub(r'^(\d+)\. (.+)$', r'\1. \2', text, flags=re.MULTILINE)
        
        # Process links
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
        
        return text
    
    @staticmethod
    def _process_code_blocks(text):
        """Process markdown code blocks with language specification"""
        def replace_code_block(match):
            code = match.group(2)
            lang = match.group(1) or ""
            
            # Escape any Pango markup in the code
            code = escape(code)
            
            # Return formatted code block - use monospace and background color
            # Use span instead of div (div is not supported in Pango markup)
            return f'<span background="#f0f0f0" font_family="monospace">\n{code}\n</span>'
        
        # Replace ```language\ncode``` blocks
        pattern = r'```([a-zA-Z0-9_]*)\n(.*?)```'
        return re.sub(pattern, replace_code_block, text, flags=re.DOTALL)
    
    @staticmethod
    def apply_markdown_to_label(label, text):
        """Apply markdown formatting to a GTK Label"""
        markup = MarkdownRenderer.markdown_to_pango(text)
        label.set_markup(markup)
        
        # Enable link clicking if there are links
        if "<a href=" in markup:
            label.connect("activate-link", MarkdownRenderer._on_activate_link)
    
    @staticmethod
    def _on_activate_link(label, uri):
        """Handle link activation in labels"""
        # Open the URI with the default application
        Gtk.show_uri(None, uri, GLib.get_current_time())
        return True  # Return True to prevent default handling

class MarkdownLabel(Gtk.Label):
    """A GTK Label that renders Markdown text"""
    
    def __init__(self):
        super().__init__()
        self.set_wrap(True)
        self.set_selectable(True)
        self.set_xalign(0)
        self.set_use_markup(True)
        
        # Enable link clicking
        self.connect("activate-link", MarkdownRenderer._on_activate_link)
    
    def set_markdown(self, text):
        """Set the label's text as markdown"""
        markup = MarkdownRenderer.markdown_to_pango(text)
        self.set_markup(markup) 