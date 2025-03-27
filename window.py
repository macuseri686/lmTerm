import gi
import lmstudio as lms
import subprocess
import threading
import json
import os

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib, Pango, Gdk, Gio

from command_row import CommandRow
from terminal import execute_command, stream_command
from lmstudio_manager import LMStudioManager

class ScrollableRow(Gtk.ListBoxRow):
    """
    A ListBoxRow that can scroll itself into view within its parent ListBox.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._scroll_handler_id_value = None

    def scroll_to_bottom(self):
        """Scroll this row to the bottom of the visible area"""
        list_box = self.get_parent()
        if not list_box:
            return False
            
        # Get the parent of the list box - could be a Viewport or ScrolledWindow
        parent = list_box.get_parent()
        
        # Find the ScrolledWindow - it might be the parent of the Viewport
        scrolled_parent = None
        if isinstance(parent, Gtk.ScrolledWindow):
            scrolled_parent = parent
        elif isinstance(parent, Gtk.Viewport):
            viewport_parent = parent.get_parent()
            if isinstance(viewport_parent, Gtk.ScrolledWindow):
                scrolled_parent = viewport_parent
        
        if not scrolled_parent:
            return False
            
        # Get the adjustment
        vadj = scrolled_parent.get_vadjustment()
        if not vadj:
            return False
            
        # Print adjustment values for debugging
        print(f"DEBUG: vadj values - value: {vadj.get_value()}, upper: {vadj.get_upper()}, page_size: {vadj.get_page_size()}")
            
        # Schedule the scroll to happen after the UI has updated
        def do_scroll():
            new_value = vadj.get_upper() - vadj.get_page_size()
            print(f"DEBUG: Setting vadj value to {new_value}")
            vadj.set_value(new_value)
            return False  # Don't call again
            
        GLib.idle_add(do_scroll)
        return True

class LmTermWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(900, 700)
        self.set_title("LM Term")
        
        # Initialize command history
        self.command_history = []
        self.history_index = -1
        self.history_file = os.path.join(os.path.expanduser("~"), ".config", "lmterm", "history.json")
        self.load_command_history()
        
        # Initialize LM Studio and available models
        self.lm_manager = LMStudioManager()
        self.available_models = self.lm_manager.available_models
        
        # Keep track of command rows
        self.command_rows = []
        
        # Main layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Create menu for the header bar
        menu = Gio.Menu.new()
        menu.append("About", "app.about")

        
        # Create menu button
        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(menu)
        
        # Get the header bar and add the menu button
        # For AdwApplicationWindow, we need to use different methods
        headerbar = Adw.HeaderBar()
        
        # Add new conversation button to the left side
        new_conversation_button = Gtk.Button()
        new_conversation_button.set_icon_name("document-new-symbolic")
        new_conversation_button.set_tooltip_text("New Conversation")
        new_conversation_button.connect("clicked", self.on_new_conversation)
        headerbar.pack_start(new_conversation_button)
        
        headerbar.pack_end(menu_button)
        self.main_box.append(headerbar)
        
        # --- Content Area Setup ---
        # Create a Stack to switch between welcome screen and command history
        self.content_stack = Gtk.Stack()
        self.content_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.content_stack.set_vexpand(True)
        self.main_box.append(self.content_stack)
        self.content_stack.add_css_class("content_stack")

        # 1. Welcome Screen
        welcome_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        welcome_box.set_halign(Gtk.Align.CENTER)
        welcome_box.set_valign(Gtk.Align.CENTER)
        welcome_box.set_hexpand(True)
        welcome_box.set_vexpand(True)

        welcome_icon = Gtk.Image.new_from_file("lmTerm.png") # Load the icon
        welcome_icon.set_opacity(0.1) # Set opacity to 70%
        welcome_icon.set_pixel_size(256) # Optional: Set a size for the icon
        welcome_icon.add_css_class("welcome-icon")

        welcome_box.append(welcome_icon)
        # You could add a label here too if desired
        # welcome_label = Gtk.Label(label="Enter a command or AI prompt below")
        # welcome_box.append(welcome_label)

        self.content_stack.add_named(welcome_box, "welcome")

        # 2. Command History Area
        scrolled = Gtk.ScrolledWindow()
        # scrolled.set_vexpand(True) # Vexpand is now on the stack

        # Command history container (vertical box for accordion items)
        self.command_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        scrolled.set_child(self.command_container)

        self.content_stack.add_named(scrolled, "history")

        # Start by showing the welcome screen
        self.content_stack.set_visible_child_name("welcome")
        # --- End Content Area Setup ---
        
        # Input area at the bottom
        input_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        input_area.add_css_class("toolbar")
        self.main_box.append(input_area)
        
        # Controls row (toggles and dropdown)
        controls_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        controls_box.set_margin_start(12)
        controls_box.set_margin_end(12)
        controls_box.set_margin_top(6)
        controls_box.set_margin_bottom(6)
        input_area.append(controls_box)
        
        # AI/Direct toggle
        self.mode_switch = Gtk.Switch()
        self.mode_switch.set_active(True)  # Set AI mode as default
        mode_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        mode_label = Gtk.Label(label="Command")
        mode_box.append(mode_label)
        mode_box.append(self.mode_switch)
        ai_label = Gtk.Label(label="AI")
        mode_box.append(ai_label)
        controls_box.append(mode_box)
        
        # Human in loop toggle
        self.human_switch = Gtk.Switch()
        human_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        human_label = Gtk.Label(label="Human in Loop")
        human_box.append(human_label)
        human_box.append(self.human_switch)
        agent_label = Gtk.Label(label="AI Agent")
        human_box.append(agent_label)
        controls_box.append(human_box)
        # hide this for now
        human_box.set_visible(False)
        agent_label.set_visible(False)
        
        # Add a spacer to push the model selection to the right
        spacer = Gtk.Box()
        spacer.set_hexpand(True)
        controls_box.append(spacer)
        
        # Model selection dropdown
        model_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        model_label = Gtk.Label(label="Model:")
        model_box.append(model_label)
        
        self.model_dropdown = Gtk.DropDown()
        model_box.append(self.model_dropdown)
        controls_box.append(model_box)
        self.populate_model_dropdown()
        
        # Command input
        input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        input_box.set_margin_start(12)
        input_box.set_margin_end(12)
        input_box.set_margin_top(6)
        input_box.set_margin_bottom(12)
        
        # Create a box to contain the entry and the history popover
        self.entry_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.entry_container.set_hexpand(True)
        
        # Create a box to position the prompt over the entry
        entry_overlay_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        entry_overlay_box.set_hexpand(True)
        
        self.command_entry = Gtk.Entry()
        self.command_entry.set_hexpand(True)
        # self.command_entry.set_margin_start(80)  # Add left margin to make room for the prompt
        self.command_entry.set_placeholder_text("Enter command or AI prompt...")
        self.command_entry.connect("activate", self.on_command_submitted)
        self.command_entry.add_css_class("command-input")  # Add CSS class
        
        # Set up key event controller for history navigation
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_key_pressed)
        self.command_entry.add_controller(key_controller)
        
        # Add shell prompt indicator that will overlay the entry
        self.prompt_frame = Gtk.Frame()
        self.prompt_frame.add_css_class("shell-prompt")
        self.prompt_frame.set_hexpand(False)
        self.prompt_frame.set_halign(Gtk.Align.START)
        self.prompt_frame.set_valign(Gtk.Align.CENTER)
        
        self.prompt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.prompt_box.set_margin_start(4)
        self.prompt_box.set_margin_end(4)
        self.prompt_box.set_margin_top(4)
        self.prompt_box.set_margin_bottom(4)
        
        # Get current directory for the prompt
        current_dir = os.path.basename(os.getcwd())
        self.prompt_label = Gtk.Label(label=f"{os.getenv('USER')}@{os.getenv('HOSTNAME', 'localhost')}:{current_dir}$")
        self.prompt_label.add_css_class("monospace")
        self.prompt_box.append(self.prompt_label)
        
        # Set the prompt box as the child of the frame
        self.prompt_frame.set_child(self.prompt_box)
        
        # Position the prompt frame over the entry
        entry_overlay = Gtk.Overlay()
        entry_overlay.set_child(self.command_entry)
        entry_overlay.add_overlay(self.prompt_frame)
        
        # Add the overlay to the entry container
        self.entry_container.append(entry_overlay)
        
        # Create history popover
        self.history_popover = Gtk.Popover()
        self.history_popover.set_position(Gtk.PositionType.TOP)
        self.history_popover.set_parent(self.command_entry)
        
        # Create a scrolled window for the history list
        history_scroll = Gtk.ScrolledWindow()
        history_scroll.set_min_content_height(200)
        history_scroll.set_max_content_height(400)
        history_scroll.set_min_content_width(400)
        
        # Create a list box for history items
        self.history_list = Gtk.ListBox()
        self.history_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.history_list.connect("row-activated", self.on_history_item_activated)
        history_scroll.set_child(self.history_list)
        
        self.history_popover.set_child(history_scroll)
        
        input_box.append(self.entry_container)
        
        run_button = Gtk.Button(label="Run")
        run_button.add_css_class("suggested-action")
        run_button.connect("clicked", self.on_command_submitted)
        input_box.append(run_button)
        
        input_area.append(input_box)
        
        # Set the main content
        self.set_content(self.main_box)
        
        # Update the prompt with colors
        self.update_prompt()
        
        # Connect to the map event to set focus on the command entry when window is shown
        self.connect("map", self.on_window_mapped)
    
    def on_window_mapped(self, widget):
        """Set focus on the command entry when the window is mapped"""
        self.command_entry.grab_focus()
        
        # Update the entry padding when the window is first shown
        # Use a longer timeout for the initial update to ensure widgets are fully allocated
        GLib.timeout_add(300, self.update_entry_padding)
    
    def load_command_history(self):
        """Load command history from file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    self.command_history = json.load(f)
                    # Limit history size to 100 items
                    if len(self.command_history) > 100:
                        self.command_history = self.command_history[-100:]
        except Exception as e:
            self.command_history = []
    
    def save_command_history(self):
        """Save command history to file"""
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            
            with open(self.history_file, 'w') as f:
                json.dump(self.command_history, f)
        except Exception as e:
            print(f"Error saving command history: {e}")
    
    def add_to_history(self, command):
        """Add a command to history, avoiding duplicates"""
        # Remove the command if it already exists to avoid duplicates
        if command in self.command_history:
            self.command_history.remove(command)
        
        # Add the command to the end of the list
        self.command_history.append(command)
        
        # Limit history size to 100 items
        if len(self.command_history) > 100:
            self.command_history = self.command_history[-100:]
        
        # Save the updated history
        self.save_command_history()
    
    def populate_history_list(self):
        """Populate the history list with items"""
        # Clear existing items
        while True:
            row = self.history_list.get_first_child()
            if row is None:
                break
            self.history_list.remove(row)
        
        # Add history items in order (oldest first)
        # This will make the most recent items appear at the bottom
        for cmd in self.command_history:
            label = Gtk.Label(label=cmd)
            label.set_halign(Gtk.Align.START)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            label.set_max_width_chars(60)
            label.set_margin_start(5)
            label.set_margin_end(5)
            label.set_margin_top(5)
            label.set_margin_bottom(5)
            
            row = ScrollableRow()
            row.set_child(label)
            self.history_list.append(row)
        
        # Add key controller to the history list
        key_controller = Gtk.EventControllerKey.new()
        key_controller.connect("key-pressed", self.on_history_key_pressed)
        self.history_list.add_controller(key_controller)
    
    def on_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events for command entry navigation"""
        # Check for Up arrow key
        if keyval == Gdk.KEY_Up:
            # If popover is not visible, show it and populate
            if not self.history_popover.get_visible():
                self.populate_history_list()
                
                # Set the popover width to match the entry width
                entry_width = self.command_entry.get_allocated_width()
                self.history_popover.set_size_request(entry_width, -1)
                
                self.history_popover.popup()
                
                # Select the last (most recent) item in the history list
                if len(self.command_history) > 0:
                    last_index = len(self.command_history) - 1
                    self.history_index = last_index
                    row = self.history_list.get_row_at_index(last_index)
                    if row:
                        self.history_list.select_row(row)
                        row.grab_focus()
                        # Scroll to the bottom to show the most recent item
                        row.scroll_to_bottom()
                        self.command_entry.set_text(self.command_history[-1])
            
            # Select the previous item in the history list (moving up)
            elif self.history_index > 0:
                self.history_index -= 1
                row = self.history_list.get_row_at_index(self.history_index)
                if row:
                    self.history_list.select_row(row)
                    # Scroll to the selected row
                    row.grab_focus()
                    # Set the text in the entry
                    self.command_entry.set_text(self.command_history[self.history_index])
            
            return True  # Stop event propagation
        
        # Check for Down arrow key
        elif keyval == Gdk.KEY_Down:
            # If we're navigating history
            if self.history_popover.get_visible():
                if self.history_index < len(self.command_history) - 1:
                    self.history_index += 1
                    row = self.history_list.get_row_at_index(self.history_index)
                    if row:
                        self.history_list.select_row(row)
                        # Scroll to the selected row
                        row.grab_focus()
                        # Set the text in the entry
                        self.command_entry.set_text(self.command_history[self.history_index])
                else:
                    # We're at the bottom item, clear the entry and close the popover
                    self.command_entry.set_text("")
                    self.history_popover.popdown()
                    self.history_index = -1
                    # Set focus back to the command entry
                    self.command_entry.grab_focus()
                
                return True  # Stop event propagation
        
        # Check for Escape key to close the popover
        elif keyval == Gdk.KEY_Escape:
            if self.history_popover.get_visible():
                self.history_popover.popdown()
                return True  # Stop event propagation
        
        # Check for Enter key to execute the selected command immediately
        elif keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            if self.history_popover.get_visible():
                # Get the current text from the entry
                command = self.command_entry.get_text()
                if command:
                    # Close the popover
                    self.history_popover.popdown()
                    # Execute the command
                    self.on_command_submitted(None)
                    return True  # Stop event propagation
        
        return False  # Continue event propagation
    
    def on_history_key_pressed(self, controller, keyval, keycode, state):
        """Handle key press events for history list navigation"""
        # Check for Down arrow key
        if keyval == Gdk.KEY_Down:
            if self.history_index < len(self.command_history) - 1:
                self.history_index += 1
                row = self.history_list.get_row_at_index(self.history_index)
                if row:
                    self.history_list.select_row(row)
                    row.grab_focus()
                    self.command_entry.set_text(self.command_history[self.history_index])
            else:
                # We're at the bottom item, clear the entry and close the popover
                self.command_entry.set_text("")
                self.history_popover.popdown()
                self.history_index = -1
                self.command_entry.grab_focus()
            
            return True  # Stop event propagation
        
        # Check for Up arrow key
        elif keyval == Gdk.KEY_Up:
            if self.history_index > 0:
                self.history_index -= 1
                row = self.history_list.get_row_at_index(self.history_index)
                if row:
                    self.history_list.select_row(row)
                    row.grab_focus()
                    self.command_entry.set_text(self.command_history[self.history_index])
            
            return True  # Stop event propagation
        
        # Check for Enter key to execute the selected command immediately
        elif keyval == Gdk.KEY_Return or keyval == Gdk.KEY_KP_Enter:
            # Get the current text from the entry
            command = self.command_entry.get_text()
            if command:
                # Close the popover
                self.history_popover.popdown()
                # Execute the command
                self.on_command_submitted(None)
            
            return True  # Stop event propagation
        
        # Check for Escape key to close the popover
        elif keyval == Gdk.KEY_Escape:
            self.history_popover.popdown()
            return True  # Stop event propagation
        
        return False  # Continue event propagation
    
    def on_history_item_activated(self, list_box, row):
        """Handle history item selection"""
        index = row.get_index()
        if 0 <= index < len(self.command_history):
            # Set the text in the entry
            self.command_entry.set_text(self.command_history[index])
            # Close the popover
            self.history_popover.popdown()
            # Move cursor to the end of the text
            self.command_entry.set_position(-1)
            # Execute the command immediately
            self.on_command_submitted(None)
    
    def populate_model_dropdown(self):
        """Populate the model dropdown with available models"""
        # Clear existing items
        string_list = Gtk.StringList()
        
        # Add models from LM Studio
        for model in self.lm_manager.available_models:
            # Models from REST API are dictionaries, not objects
            # Use the 'id' field instead of model_key
            model_id = model.get('id', '')
            if model_id:
                string_list.append(model_id)
        
        # Set the dropdown model
        self.model_dropdown.set_model(string_list)
        self.model_dropdown.connect("notify::selected", self.on_model_changed)
        
        # Auto-select the first model if available
        if len(self.lm_manager.available_models) > 0:
            self.model_dropdown.set_selected(0)
            self.on_model_changed(self.model_dropdown, None)
    
    def on_model_changed(self, dropdown, _):
        """Handle model selection change"""
        selected = dropdown.get_selected()
        if hasattr(self, 'available_models') and self.available_models and selected < len(self.available_models):
            success = self.lm_manager.set_model(selected)
            if not success:
                print(f"Failed to load model at index: {selected}")
        else:
            # Use the manager's available_models instead
            if self.lm_manager.available_models and selected < len(self.lm_manager.available_models):
                success = self.lm_manager.set_model(selected)
                if success:
                    print(f"Successfully loaded model at index: {selected}")
                else:
                    print(f"Failed to load model at index: {selected}")
            else:
                print(f"Invalid model index: {selected}")
    
    def on_command_submitted(self, widget):
        """Handle command or prompt submission"""
        text = self.command_entry.get_text()
        if not text:
            return
            
        # Switch to history view if it's the first command
        if not self.command_rows:
             self.content_stack.set_visible_child_name("history")

        # Add to history
        self.add_to_history(text)
        self.history_index = -1
            
        # Clear the entry
        self.command_entry.set_text("")
        
        # Create a new command row
        command_row = CommandRow()
        self.command_container.append(command_row)
        
        # Add to command_rows list
        self.command_rows.append(command_row)
        print(f"Added new command row to command_rows list. Total rows: {len(self.command_rows)}")
        
        # Process based on mode
        is_ai_mode = self.mode_switch.get_active()
        is_agent_mode = not self.human_switch.get_active()
        
        if is_ai_mode:
            # AI mode - send to LM Studio
            command_row.set_user_prompt(text)
            threading.Thread(target=self._process_ai_prompt, 
                            args=(command_row, text, is_agent_mode)).start()
        else:
            # Direct command mode
            command_row.set_command(text)
            threading.Thread(target=self._execute_command, 
                            args=(command_row, text)).start()
        
        # Ensure scrolling happens after the UI has updated with the new content
        GLib.idle_add(self._scroll_to_bottom)
    
    def _process_ai_prompt(self, command_row, prompt, is_agent_mode):
        """Process an AI prompt using LM Studio"""
        try:
            if not self.lm_manager.current_model:
                GLib.idle_add(command_row.set_ai_response, 
                             "Error: No model loaded. Please select a model.")
                return
                
            # Initialize the AI response with a spinner
            GLib.idle_add(command_row.start_ai_response)
            
            if is_agent_mode:
                # Define tools the AI can use
                def terminal_execute(command: str) -> str:
                    """Execute a terminal command and return the output."""
                    return f"Command execution requires user confirmation: {command}"
                
                tools = [{
                    "type": "function",
                    "function": {
                        "name": "terminal_execute",
                        "description": "Execute a terminal command and return the output.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "command": {
                                    "type": "string",
                                    "description": "The command to execute"
                                }
                            },
                            "required": ["command"]
                        }
                    }
                }]
                
                # Define callbacks for streaming
                def on_chunk(chunk):
                    GLib.idle_add(command_row.update_streaming_response, chunk)
                
                def on_complete(final_response):
                    GLib.idle_add(command_row.finish_streaming_response)
                    
                    # Process the final response to extract any tool call requests
                    try:
                        parsed_response = json.loads(final_response)
                        if 'tool_calls' in parsed_response:
                            for tool_call in parsed_response['tool_calls']:
                                if tool_call['function']['name'] == 'terminal_execute':
                                    arguments = json.loads(tool_call['function']['arguments'])
                                    command = arguments.get('command', '')
                                    tool_id = tool_call['id']
                                    
                                    # Store the command ID in the command_row for later use
                                    command_row.pending_command_id = tool_id
                                    
                                    # Set the suggested command in the UI
                                    GLib.idle_add(command_row.set_suggested_command, command)
                                    
                                    # Store the command ID for later reference
                                    GLib.idle_add(lambda: setattr(command_row, '_command_id', tool_id))
                    except:
                        # If we can't parse the response as JSON, it's a regular text response
                        pass
                
                # Run the AI agent with streaming
                self.lm_manager.run_streaming_agent(
                    prompt,
                    tools,
                    on_chunk=on_chunk,
                    on_complete=on_complete
                )
            else:
                # Human in loop mode - get a streaming response
                def on_chunk(chunk):
                    GLib.idle_add(command_row.update_streaming_response, chunk)
                
                def on_complete(final_response):
                    GLib.idle_add(command_row.finish_streaming_response)
                    
                    # If the AI suggested a command, extract it
                    if "```" in final_response:
                        command_parts = final_response.split("```")
                        for i, part in enumerate(command_parts):
                            if i % 2 == 1 and not part.startswith("bash"):
                                # Skip code blocks that aren't bash
                                continue
                            if i % 2 == 1:
                                # Extract command from code block
                                cmd = part.replace("bash\n", "").strip()
                                GLib.idle_add(command_row.set_suggested_command, cmd)
                                break
                
                # Get streaming response
                self.lm_manager.get_streaming_response(
                    prompt,
                    on_chunk=on_chunk,
                    on_complete=on_complete
                )
            
        except Exception as e:
            GLib.idle_add(command_row.set_ai_response, f"Error: {str(e)}")
    
    def _execute_command(self, command_row, command):
        """Execute a command and add it to the terminal output"""
        try:
            # Use stream_command instead of execute_command
            result = stream_command(command, parent_widget=self, command_row=command_row)
            
            # Update the prompt if the command was a cd command
            if command.strip().startswith("cd "):
                GLib.idle_add(self.update_prompt)
        except Exception as e:
            import traceback
            traceback.print_exc()
            GLib.idle_add(command_row.set_command_output, f"Error: {str(e)}")
    
    def on_new_conversation(self, button):
        """Handle new conversation button click"""
        # Clear all command rows from the container
        while True:
            child = self.command_container.get_first_child()
            if child is None:
                break
            self.command_container.remove(child)
        
        # Clear the command_rows list
        self.command_rows = []
        
        # Switch back to the welcome screen
        self.content_stack.set_visible_child_name("welcome")
        
        # Reset the command entry
        self.command_entry.set_text("")
        
        # Focus the command entry
        self.command_entry.grab_focus()

    def add_command_row(self, prompt, is_agent_mode=False):
        """Add a new command row to the chat"""
        command_row = CommandRow()
        command_row.set_user_prompt(prompt)
        self.command_history.append(command_row)
        
        # Keep track of this command row
        self.command_rows.append(command_row)
        
        # Process the prompt
        threading.Thread(target=self._process_ai_prompt, 
                        args=(command_row, prompt, is_agent_mode)).start()
        
        return command_row 

    def _scroll_to_bottom(self):
        """Scroll to the bottom of the conversation view"""
        # Find the ScrolledWindow within the stack's visible child
        visible_child = self.content_stack.get_visible_child()
        scrolled = None
        if isinstance(visible_child, Gtk.ScrolledWindow):
             scrolled = visible_child
        # If the visible child is the welcome screen, we don't need to scroll
        elif self.content_stack.get_visible_child_name() == "history":
             # It might take a moment for the stack to switch, find it by name
             child = self.content_stack.get_child_by_name("history")
             if isinstance(child, Gtk.ScrolledWindow):
                 scrolled = child

        if scrolled:
            # Get the adjustment and scroll to the bottom
            vadj = scrolled.get_vadjustment()
            if vadj:
                # Schedule the scroll to happen after the UI has updated
                def do_scroll():
                    # Make sure we get the latest values
                    vadj = scrolled.get_vadjustment()
                    if vadj:
                        new_value = vadj.get_upper() - vadj.get_page_size()
                        vadj.set_value(new_value)
                    return False  # Don't call again
                    
                GLib.idle_add(do_scroll)

    def update_prompt(self):
        """Update the shell prompt with the current directory"""
        current_dir = os.path.basename(os.getcwd())
        
        # Use markup with colored spans
        user_host = f"<span foreground='#4CAF50'>{os.getenv('USER')}@{os.getenv('HOSTNAME', 'localhost')}</span>"
        separator = "<span foreground='black'>:</span>"
        directory = f"<span foreground='#2196F3'>{current_dir}</span>"
        prompt_char = "<span foreground='black'>$</span>"
        
        # Set the markup text
        self.prompt_label.set_markup(f"{user_host}{separator}{directory}{prompt_char}")
        self.prompt_label.set_use_markup(True)
        
        # We need to wait for the label to be allocated its new size
        # Connect a one-time handler to the prompt label's notify::width signal
        def on_prompt_width_changed(label, pspec):
            # Disconnect this handler after it's called once
            label.disconnect(handler_id)
            # Update the padding
            self.update_entry_padding()
            return False
        
        handler_id = self.prompt_label.connect("notify::width", on_prompt_width_changed)
        
        # Also schedule an update after a short delay as a fallback
        GLib.timeout_add(100, self.update_entry_padding)

    def update_entry_padding(self):
        """Update the command entry padding to match the prompt width"""
        # Get the width of the prompt frame
        prompt_width = self.prompt_frame.get_allocated_width()
        
        if prompt_width > 0:
            # Add a small buffer (e.g., 5px) to ensure text doesn't overlap with prompt
            padding = prompt_width + 5
            
            # Set the left margin of the entry to match the prompt width
            css_provider = Gtk.CssProvider()
            css = f"""
            .command-input {{
                padding-left: {padding}px;
            }}
            """
            css_provider.load_from_data(css.encode())
            
            # Apply the CSS to the entry
            style_context = self.command_entry.get_style_context()
            style_context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            
            print(f"Updated command entry padding to {padding}px")
            return False  # Don't call again
        else:
            # If we couldn't get the width yet, try again later
            print("Prompt width not available yet, will try again")
            return True  # Call again 