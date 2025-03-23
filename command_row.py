import gi
import traceback
import os

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Pango, GLib

class CommandRow(Adw.ExpanderRow):
    def __init__(self):
        super().__init__()
        self.set_title("")
        self.set_expanded(True)
        
        # Main content box
        self.content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.content_box.set_margin_top(8)
        self.content_box.set_margin_bottom(8)
        self.content_box.set_margin_start(16)
        self.content_box.set_margin_end(16)
        
        # Add a signal handler for when the content box is mapped to the screen
        self.content_box.connect("map", self._on_content_mapped)
        
        # User prompt box (speech bubble style)
        self.user_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.user_box.set_halign(Gtk.Align.START)
        self.user_box.add_css_class("card")
        self.user_box.add_css_class("user-bubble")
        self.user_box.set_margin_end(48)
        
        self.user_label = Gtk.Label()
        self.user_label.set_selectable(True)
        self.user_label.set_wrap(True)
        self.user_label.set_xalign(0)
        self.user_label.set_margin_start(12)
        self.user_label.set_margin_end(12)
        self.user_label.set_margin_top(8)
        self.user_label.set_margin_bottom(8)
        self.user_box.append(self.user_label)
        
        # Command row and run button
        self.command_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.command_label = Gtk.Label()
        self.command_label.set_selectable(True)
        self.command_label.set_wrap(True)
        self.command_label.set_wrap_mode(Pango.WrapMode.CHAR)
        self.command_label.set_xalign(0)
        self.command_label.add_css_class("monospace")
        self.command_label.add_css_class("command-text")
        
        # Put command in a frame
        command_frame = Gtk.Frame()
        command_frame.set_child(self.command_label)
        command_frame.add_css_class("command-frame")
        command_frame.set_hexpand(True)
        self.command_box.append(command_frame)
        
        # Output box with monospace text
        self.output_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.output_box.add_css_class("terminal-output")
        
        self.output_label = Gtk.Label()
        self.output_label.set_selectable(True)
        self.output_label.set_wrap(True)
        self.output_label.set_wrap_mode(Pango.WrapMode.CHAR)
        self.output_label.set_xalign(0)
        self.output_label.add_css_class("monospace")
        
        self.output_scroll = Gtk.ScrolledWindow()
        self.output_scroll.add_css_class("terminal-scrolled")
        self.output_scroll.set_min_content_height(100)
        self.output_scroll.set_max_content_height(400)
        self.output_scroll.set_child(self.output_label)
        self.output_box.append(self.output_scroll)
        
        # AI response box (speech bubble style)
        self.ai_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.ai_box.set_halign(Gtk.Align.END)
        self.ai_box.add_css_class("card")
        self.ai_box.add_css_class("ai-bubble")
        self.ai_box.set_margin_start(48)
        
        self.ai_response_label = None
        self.ai_response_box = self.ai_box
        
        # Add all elements to the content box
        self.content_box.append(self.user_box)
        self.content_box.append(self.command_box)
        self.content_box.append(self.output_box)
        self.content_box.append(self.ai_box)
        
        self.add_row(self.content_box)
        
        # Initially hide some elements
        self.user_box.set_visible(False)
        self.command_box.set_visible(False)
        self.output_box.set_visible(False)
        self.ai_box.set_visible(False)
        
        # Store command text
        self._command_text = ""
        
        # Initialize chat history
        self.chat_history = {"messages": []}
    
    def _on_content_mapped(self, widget):
        """Scroll to this row when it's mapped to the screen"""
        # Find the ScrolledWindow parent
        self._scroll_to_bottom()
    
    def _scroll_to_bottom(self):
        """Helper method to scroll to the bottom of the conversation"""
        # Find the ScrolledWindow parent
        parent = self.get_parent()
        while parent and not isinstance(parent, Gtk.ScrolledWindow):
            parent = parent.get_parent()
        
        if parent and isinstance(parent, Gtk.ScrolledWindow):
            # Get the adjustment and scroll to the bottom
            vadj = parent.get_vadjustment()
            if vadj:
                GLib.idle_add(lambda: vadj.set_value(vadj.get_upper() - vadj.get_page_size()))
    
    def set_user_prompt(self, text):
        """Set the user prompt text"""
        self.user_label.set_text(text)
        self.user_box.set_visible(True)
        self.set_title(f"{text[:40]}...")
        
        # Add to chat history
        self.chat_history["messages"].append({"role": "user", "content": text})
        
        # Scroll to bottom after setting user prompt
        self._scroll_to_bottom()
    
    def set_command(self, command):
        """Set the command to execute"""
        self._command_text = command
        self.command_label.set_text(command)
        self.command_box.set_visible(True)
        self.set_title(f"Command: {command}")
        
        # Debug print to check command box
        print(f"DEBUG: Command box children: {[type(child) for child in self.command_box.observe_children()]}")
        
        # Remove any existing confirmation buttons first
        for child in list(self.command_box.observe_children()):
            if isinstance(child, Gtk.Box) and child != command_frame:
                self.command_box.remove(child)
        
        # Don't add confirmation buttons for direct commands
        # The command will be executed immediately by the caller
    
    def set_suggested_command(self, command):
        """Set a command suggested by the AI"""
        self._command_text = command
        self.command_label.set_text(command)
        self.command_box.set_visible(True)
        
        # Remove any existing confirmation buttons first
        for child in list(self.command_box.observe_children()):
            if isinstance(child, Gtk.Box):
                self.command_box.remove(child)
        
        # Create a box for the confirmation buttons
        confirmation_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        
        # Add run button
        run_button = Gtk.Button(label="Run")
        run_button.add_css_class("suggested-action")  # Gives it a highlighted appearance
        run_button.connect("clicked", self._on_run_command)
        confirmation_box.append(run_button)
        
        # Add cancel button
        cancel_button = Gtk.Button(label="Cancel")
        cancel_button.connect("clicked", self._on_cancel_command)
        confirmation_box.append(cancel_button)
        
        # Add the confirmation box to the command box
        self.command_box.append(confirmation_box)
    
    def set_command_output(self, output):
        """Set the command output text"""
        self.output_label.set_text(output)
        self.output_box.set_visible(True)
        
        # Scroll to bottom after setting output
        self._scroll_to_bottom()
    
    def set_ai_response(self, response):
        """Set the AI response text"""
        print(f"Setting AI response: {response[:50]}...")
        
        # Process the response to extract the actual content
        processed_response = self._process_response(response)
        
        # Clear any existing response
        if self.ai_response_label:
            self.ai_response_label.set_text("")
        
        # Create a new label if needed
        if not self.ai_response_label:
            # Use MarkdownLabel instead of regular Gtk.Label
            from markdown_renderer import MarkdownLabel
            self.ai_response_label = MarkdownLabel()
            self.ai_response_label.set_margin_start(10)
            self.ai_response_label.set_margin_end(10)
            self.ai_response_label.set_margin_top(5)
            self.ai_response_label.set_margin_bottom(5)
            
            # Add the label to the AI response box
            self.ai_response_box.append(self.ai_response_label)
        
        # Set the response text using markdown
        self.ai_response_label.set_markdown(processed_response)
        
        # Make sure the AI response box is visible
        self.ai_response_box.set_visible(True)
        
        # Add thinking expander if we have thinking content
        if hasattr(self, '_thinking_content') and self._thinking_content:
            # Create a vertical box if needed to hold both the expander and the response
            if not hasattr(self, 'ai_response_vbox'):
                self.ai_response_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                
                # If the label is already in the AI box, move it to the vbox
                if self.ai_response_label.get_parent() == self.ai_response_box:
                    self.ai_response_box.remove(self.ai_response_label)
                    self.ai_response_vbox.append(self.ai_response_label)
                
                # Add the vbox to the AI box
                self.ai_response_box.append(self.ai_response_vbox)
            
            # Add the thinking expander to the vbox
            self._add_thinking_expander(self._thinking_content, self.ai_response_vbox)
            
            # Clear the thinking content
            self._thinking_content = None
    
    def add_ai_response(self, response):
        """Add a new AI response bubble"""
        print(f"ADD_AI_RESPONSE called with: {response[:50]}...")
        
        # Check if this response contains thinking tags
        has_thinking = "<think>" in response and "</think>" in response
        thinking_content = None
        
        if has_thinking:
            # Extract thinking content
            thinking_start = response.find("<think>")
            thinking_end = response.find("</think>") + len("</think>")
            thinking_content = response[thinking_start + len("<think>"):thinking_end - len("</think>")].strip()
            
            # Extract the actual response (after the thinking part)
            processed_response = response[thinking_end:].strip()
        else:
            # Process the response normally
            processed_response = self._process_response(response)
        
        print(f"Processed response: {processed_response[:50]}...")
        
        # Create a new AI response box
        new_ai_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        new_ai_box.set_halign(Gtk.Align.END)
        new_ai_box.add_css_class("card")
        new_ai_box.add_css_class("ai-bubble")
        new_ai_box.set_margin_start(48)
        print("Created new AI box with classes: card, ai-bubble")
        
        # If we have thinking content, create a vertical box to hold both the thinking expander and the response
        if thinking_content:
            ai_content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            new_ai_box.append(ai_content_box)
            
            # Create the thinking expander
            thinking_expander = Adw.ExpanderRow()
            thinking_expander.set_title("AI's Thinking Process")
            thinking_expander.set_expanded(False)
            
            # Create a MarkdownLabel for the thinking content
            from markdown_renderer import MarkdownLabel
            thinking_label = MarkdownLabel()
            thinking_label.set_margin_start(10)
            thinking_label.set_margin_end(10)
            thinking_label.set_margin_top(5)
            thinking_label.set_margin_bottom(5)
            thinking_label.set_markdown(thinking_content)
            
            # Add the label to the expander
            thinking_expander.add_row(thinking_label)
            
            # Add the expander to the content box
            ai_content_box.append(thinking_expander)
            
            # Create a MarkdownLabel for the response
            response_label = MarkdownLabel()
            response_label.set_margin_start(10)
            response_label.set_margin_end(10)
            response_label.set_margin_top(5)
            response_label.set_margin_bottom(5)
            response_label.set_markdown(processed_response)
            
            # Add the response label to the content box
            ai_content_box.append(response_label)
            
            # Set the new label as the current one
            new_label = response_label
        else:
            # Create a new MarkdownLabel for the response (no thinking content)
            from markdown_renderer import MarkdownLabel
            new_label = MarkdownLabel()
            new_label.set_margin_start(10)
            new_label.set_margin_end(10)
            new_label.set_margin_top(5)
            new_label.set_margin_bottom(5)
            new_label.set_markdown(processed_response)
            
            # Add the label to the new AI box
            new_ai_box.append(new_label)
        
        print(f"Created new MarkdownLabel with text: {processed_response[:50]}...")
        print("Added label to new AI box")
        
        # Add the new AI box to the content box
        print(f"Adding new AI box to content box (content_box children count before: {len(list(self.content_box.observe_children()))})")
        self.content_box.append(new_ai_box)
        print(f"Content box children count after: {len(list(self.content_box.observe_children()))}")
        
        # Make sure the new AI box is visible
        new_ai_box.set_visible(True)
        print(f"New AI box visible: {new_ai_box.get_visible()}, realized: {new_ai_box.get_realized()}")
        
        # Check if the new box is actually in the widget hierarchy
        print(f"New AI box parent: {new_ai_box.get_parent()}")
        
        # Add to chat history
        self.chat_history["messages"].append({"role": "assistant", "content": processed_response})
        print("Added response to chat history")
        
        # Scroll to bottom after adding response
        self._scroll_to_bottom()
        
        # Return the new AI box and label
        return new_ai_box, new_label
    
    def update_ai_response(self, response):
        """Update the AI response text (append or replace)"""
        print(f"Updating AI response: {response[:50]}...")
        
        # Process the response to extract the actual content
        processed_response = self._process_response(response)
        
        # If this is a JSON string with tool calls, parse it and extract the relevant parts
        try:
            import json
            parsed = json.loads(response)
            
            # Check if this is a tool call response
            if 'tool_calls' in parsed:
                # This is a tool call, so we'll just show a message about it
                tool_calls = parsed['tool_calls']
                if tool_calls and len(tool_calls) > 0:
                    tool_call = tool_calls[0]
                    if tool_call['function']['name'] == 'terminal_execute':
                        arguments = json.loads(tool_call['function']['arguments'])
                        command = arguments.get('command', '')
                        
                        # Set a message about the tool call
                        self.set_ai_response(f"I'll run the command: {command}")
                        return
        except:
            # If we can't parse it as JSON, just use the response as is
            pass
        
        # Set the response text
        self.set_ai_response(processed_response)
    
    def _on_run_command(self, button):
        """Handle running a suggested command"""
        from terminal import confirm_command, PENDING_COMMANDS, stream_command
        
        # Disable both buttons while running
        parent = button.get_parent()
        for child in parent.observe_children():
            child.set_sensitive(False)
        
        def run_in_thread():
            try:
                # Use the command ID if available, otherwise fall back to direct execution
                if hasattr(self, '_command_id'):
                    command_id = self._command_id
                    print(f"DEBUG - Running command with ID: {command_id}")
                    print(f"DEBUG - Available command IDs: {list(PENDING_COMMANDS.keys())}")
                    print(f"DEBUG - Command ID in PENDING_COMMANDS: {command_id in PENDING_COMMANDS}")
                    
                    # Check if the command ID exists in PENDING_COMMANDS
                    if command_id not in PENDING_COMMANDS:
                        # The command ID doesn't exist, so we need to get it from the LM Studio manager
                        window = self.get_root()
                        if window and hasattr(window, 'lm_manager'):
                            lm_manager = window.lm_manager
                            if hasattr(lm_manager, 'pending_tool_calls') and command_id in lm_manager.pending_tool_calls:
                                tool_info = lm_manager.pending_tool_calls[command_id]
                                command = tool_info.get("command", "")
                                
                                # Import stream_command here to ensure it's available
                                from terminal import stream_command
                                
                                # Stream the command execution
                                result = stream_command(command, parent_widget=self, command_row=self)
                                
                                # Update the prompt if the command was a cd command
                                if command.strip().startswith("cd "):
                                    window = self.get_root()
                                    if window and hasattr(window, 'update_prompt'):
                                        GLib.idle_add(window.update_prompt)
                                
                                # Process the next tool call if available
                                GLib.idle_add(self._process_next_tool_call, result)
                                
                                # Remove the confirmation buttons after execution
                                GLib.idle_add(self._remove_confirmation_buttons, parent)
                                return
                
                    # If we get here, try to confirm the command using the standard flow
                    result = confirm_command(command_id, parent_widget=self, stream=True, command_row=self)
                    
                    # Update the prompt if the command was a cd command
                    command = PENDING_COMMANDS.get(command_id, {}).get("command", "")
                    if command and command.strip().startswith("cd "):
                        window = self.get_root()
                        if window and hasattr(window, 'update_prompt'):
                            GLib.idle_add(window.update_prompt)
                    
                    # Process the next tool call if available
                    GLib.idle_add(self._process_next_tool_call, result)
                else:
                    # Import stream_command here to ensure it's available
                    from terminal import stream_command
                    result = stream_command(self._command_text, parent_widget=self, command_row=self)
                    
                    # Update the prompt if the command was a cd command
                    if self._command_text.strip().startswith("cd "):
                        window = self.get_root()
                        if window and hasattr(window, 'update_prompt'):
                            GLib.idle_add(window.update_prompt)
                    
                    # Process the next tool call if available
                    GLib.idle_add(self._process_next_tool_call, result)
            except Exception as e:
                GLib.idle_add(self._update_output, f"Error: {str(e)}")
                import traceback
                traceback.print_exc()
            finally:
                # Remove the confirmation buttons after execution
                GLib.idle_add(self._remove_confirmation_buttons, parent)
        
        import threading
        threading.Thread(target=run_in_thread).start()
    
    def _process_next_tool_call(self, previous_result):
        """Process the next tool call in the queue"""
        # Check if we have pending tool calls
        if hasattr(self, '_pending_tool_calls') and self._pending_tool_calls:
            # Remove the current tool call
            self._pending_tool_calls.pop(0)
            
            # If we have more tool calls, process the next one
            if self._pending_tool_calls:
                next_call = self._pending_tool_calls[0]
                self.set_suggested_command(next_call["command"])
                self._command_id = next_call["id"]
                self.pending_command_id = next_call["id"]
                print(f"Processing next command: {next_call['command']} with ID: {next_call['id']}")
                return
        
        # If we've processed all tool calls or there are none, send the result back to the AI
        if hasattr(self, 'pending_command_id'):
            # Get the LMStudioManager instance from the window
            window = self.get_root()
            if window and hasattr(window, 'lm_manager'):
                lm_manager = window.lm_manager
                
                # Send the tool result back to the AI
                tool_id = self.pending_command_id
                print(f"DEBUG - Sending tool result for ID: {tool_id}")
                success = lm_manager.send_tool_result(tool_id, previous_result)
                if not success:
                    print("Failed to send tool result to AI")
            else:
                print("Could not access LM Studio manager from window")
            
            # Clear the pending command ID
            self.pending_command_id = None
    
    def _on_cancel_command(self, button):
        """Handle canceling a suggested command"""
        # Remove the confirmation buttons
        parent = button.get_parent()
        self._remove_confirmation_buttons(parent)
        
        # Cancel the command if it has an ID
        if hasattr(self, '_command_id'):
            from terminal import cancel_command
            cancel_result = cancel_command(self._command_id)
            
            # If we're in an AI agent conversation, we need to send the cancellation back to the AI
            if hasattr(self, 'pending_command_id') and self.pending_command_id == self._command_id:
                # Get the LMStudioManager instance from the window
                window = self.get_root()
                if window and hasattr(window, 'lm_manager'):
                    lm_manager = window.lm_manager
                    
                    # Send the cancellation result back to the AI
                    lm_manager.send_tool_result(self.pending_command_id, "Command was canceled by the user.")
                
                # Clear the pending command ID
                self.pending_command_id = None
        
        # Add a note that the command was canceled
        self.set_command_output("Command execution canceled by user.")
    
    def _remove_confirmation_buttons(self, button_box):
        """Remove the confirmation buttons from the command box"""
        if button_box and button_box in self.command_box:
            self.command_box.remove(button_box)
    
    def _update_output(self, text):
        """Update the command output"""
        self.set_command_output(text)
        
        # No need to update prompt here anymore as it's handled in the window
    
    def _process_response(self, response):
        """Process the response to extract the actual text content"""
        processed_response = response
        
        # Check if the response contains thinking tags
        if "<think>" in response and "</think>" in response:
            # Extract thinking content
            thinking_start = response.find("<think>")
            thinking_end = response.find("</think>") + len("</think>")
            thinking_content = response[thinking_start + len("<think>"):thinking_end - len("</think>")].strip()
            
            # Store the thinking content for later use
            self._thinking_content = thinking_content
            
            # Extract the actual response (after the thinking part)
            processed_response = response[thinking_end:].strip()
            
            # If we already have an AI response label, add the thinking expander
            if self.ai_response_label and self.ai_response_label.get_parent():
                self._add_thinking_expander(thinking_content)
        
        # Check if the response is in the ChatMessageDataAssistant format
        elif isinstance(response, str) and "ChatMessageDataAssistant.from_dict" in response:
            try:
                # Extract the dictionary part from the string
                dict_start = response.find('{')
                dict_end = response.rfind('}') + 1
                if dict_start >= 0 and dict_end > dict_start:
                    json_str = response[dict_start:dict_end]
                    
                    import json
                    # Try to parse as JSON
                    print("DEBUG - Attempting to parse JSON from ChatMessageDataAssistant")
                    parsed = json.loads(json_str)
                    print(f"DEBUG - Parsed JSON: {type(parsed)}")
                    
                    if isinstance(parsed, dict) and 'content' in parsed:
                        print("DEBUG - Found 'content' key")
                        content_list = parsed['content']
                        for item in content_list:
                            if item.get('type') == 'text':
                                processed_response = item.get('text', '')
                                print(f"DEBUG - Extracted text: {processed_response[:50]}...")
                                break
            except Exception as e:
                print(f"Error parsing ChatMessageDataAssistant response: {e}")
                traceback.print_exc()
        
        # Handle tool requests
        if "[TOOL_REQUEST]" in processed_response and "[END_TOOL_REQUEST]" in processed_response:
            # Extract the tool request
            tool_start = processed_response.find("[TOOL_REQUEST]")
            tool_end = processed_response.find("[END_TOOL_REQUEST]") + len("[END_TOOL_REQUEST]")
            tool_content = processed_response[tool_start + len("[TOOL_REQUEST]"):tool_end - len("[END_TOOL_REQUEST]")].strip()
            
            # Process the tool request
            GLib.idle_add(self._process_tool_request, tool_content)
            
            # Return a message about the tool request
            return "I'm executing a command to help answer your question..."
        
        # Handle JSON responses with tool_calls
        try:
            import json
            if isinstance(response, str) and (response.startswith('{') or '"tool_calls"' in response):
                parsed = json.loads(response)
                
                # Check if this is a tool call response
                if 'tool_calls' in parsed:
                    # This is a tool call, extract all tool calls
                    tool_calls = parsed['tool_calls']
                    if tool_calls and len(tool_calls) > 0:
                        # Store all tool calls for sequential processing
                        self._pending_tool_calls = []
                        
                        # Track unique commands to avoid duplicates
                        unique_commands = set()
                        
                        for tool_call in tool_calls:
                            if tool_call['function']['name'] == 'terminal_execute':
                                try:
                                    arguments = json.loads(tool_call['function']['arguments'])
                                    command = arguments.get('command', '')
                                    if command:
                                        # Only add this command if we haven't seen it before
                                        if command not in unique_commands:
                                            unique_commands.add(command)
                                            self._pending_tool_calls.append({
                                                "id": tool_call['id'],
                                                "command": command
                                            })
                                        else:
                                            print(f"Skipping duplicate command: {command}")
                                except Exception as e:
                                    print(f"Error parsing tool call arguments: {e}")
                        
                        # Process the first tool call
                        if self._pending_tool_calls:
                            first_call = self._pending_tool_calls[0]
                            GLib.idle_add(self.set_suggested_command, first_call["command"])
                            self._command_id = first_call["id"]
                            self.pending_command_id = first_call["id"]
                            
                            # Return a message about the first command
                            return f"I'll run the command: {first_call['command']}"
        except Exception as e:
            print(f"Error processing JSON response: {e}")
            traceback.print_exc()
        
        return processed_response
    
    def _process_tool_request(self, tool_content):
        """Process a tool request from the AI"""
        try:
            import json
            
            # Check if tool_content is empty or not valid JSON
            if not tool_content or tool_content.isspace():
                print("Warning: Empty tool content received")
                return
            
            # Print the tool content for debugging
            print(f"Tool content to parse: '{tool_content}'")
            
            # Parse the tool request
            tool_json = json.loads(tool_content.strip())
            
            # Check if this is a single tool call or multiple tool calls
            if isinstance(tool_json, dict) and "tool_calls" in tool_json:
                # Multiple tool calls from the API response
                tool_calls = tool_json["tool_calls"]
                if tool_calls and len(tool_calls) > 0:
                    # Store all tool calls for sequential processing
                    self._pending_tool_calls = []
                    
                    # Track unique commands to avoid duplicates
                    unique_commands = set()
                    
                    # Add all tool calls to the queue
                    for tool_call in tool_calls:
                        if tool_call["function"]["name"] == "terminal_execute":
                            try:
                                arguments = json.loads(tool_call["function"]["arguments"])
                                command = arguments.get("command", "")
                                if command:
                                    # Only add this command if we haven't seen it before
                                    if command not in unique_commands:
                                        unique_commands.add(command)
                                        self._pending_tool_calls.append({
                                            "id": tool_call["id"],
                                            "command": command
                                        })
                                    else:
                                        print(f"Skipping duplicate command: {command}")
                            except Exception as e:
                                print(f"Error parsing tool call arguments: {e}")
                    
                    # Process the first tool call
                    if self._pending_tool_calls:
                        first_call = self._pending_tool_calls[0]
                        self.set_suggested_command(first_call["command"])
                        self._command_id = first_call["id"]
                        self.pending_command_id = first_call["id"]
                        print(f"Set first command: {first_call['command']} with ID: {first_call['id']}")
            
            # Handle single tool call (legacy format)
            elif isinstance(tool_json, dict) and tool_json.get("name") == "terminal_execute":
                # Single tool call
                command = tool_json.get("arguments", {}).get("command", "")
                if command:
                    # Set the command in the UI
                    self.set_suggested_command(command)
                    
                    # Store the tool ID for later reference
                    if "id" in tool_json:
                        self._command_id = tool_json["id"]
                        
                        # Store the pending command ID for the AI conversation
                        self.pending_command_id = tool_json["id"]
                    else:
                        # If no ID is provided, generate one
                        import random
                        self._command_id = str(random.randint(1000000, 9999999))
                        self.pending_command_id = self._command_id
        except json.JSONDecodeError as e:
            print(f"Error parsing tool request JSON: {e}")
            print(f"Invalid JSON content: '{tool_content}'")
            traceback.print_exc()
        except Exception as e:
            print(f"Error processing tool request: {e}")
            traceback.print_exc()
    
    def _add_thinking_expander(self, thinking_content, parent_box=None):
        """Add an expander for the AI's thinking process"""
        # Create an expander row for the thinking content
        thinking_expander = Adw.ExpanderRow()
        thinking_expander.set_title("AI's Thinking Process")
        thinking_expander.set_expanded(False)
        
        # Create a MarkdownLabel for the thinking content
        from markdown_renderer import MarkdownLabel
        thinking_label = MarkdownLabel()
        thinking_label.set_margin_start(10)
        thinking_label.set_margin_end(10)
        thinking_label.set_margin_top(5)
        thinking_label.set_margin_bottom(5)
        thinking_label.set_markdown(thinking_content)
        
        # Add the label to the expander
        thinking_expander.add_row(thinking_label)
        
        # Add the expander to the specified parent box or the AI response box
        if parent_box:
            # Add the expander at the beginning of the box
            parent_box.prepend(thinking_expander)
        elif self.ai_response_box:
            # If there's already content in the AI box, we need to reorganize
            if self.ai_response_label:
                # Create a vertical box to hold both the expander and the response
                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                
                # Add the expander to the box
                vbox.append(thinking_expander)
                
                # Move the existing label to the box
                if self.ai_response_label.get_parent() == self.ai_response_box:
                    self.ai_response_box.remove(self.ai_response_label)
                    vbox.append(self.ai_response_label)
                
                # Add the box to the AI response box
                self.ai_response_box.append(vbox)
            else:
                # Just add the expander
                self.ai_response_box.append(thinking_expander)
    
    def get_chat_history(self):
        """Return the chat history in a format compatible with LM Studio"""
        return self.chat_history

    # Add new methods for streaming responses
    def start_ai_response(self):
        """Initialize an AI response with a throbber to indicate loading"""
        # Make sure the AI box is visible
        self.ai_box.set_visible(True)
        
        # Create a new label if needed
        if not self.ai_response_label:
            # Use MarkdownLabel instead of regular Gtk.Label
            from markdown_renderer import MarkdownLabel
            self.ai_response_label = MarkdownLabel()
            self.ai_response_label.set_margin_start(10)
            self.ai_response_label.set_margin_end(10)
            self.ai_response_label.set_margin_top(5)
            self.ai_response_label.set_margin_bottom(5)
            
            # Add the label to the AI response box
            self.ai_response_box.append(self.ai_response_label)
        
        # Create a spinner (throbber)
        self.ai_spinner = Gtk.Spinner()
        self.ai_spinner.set_spinning(True)
        self.ai_spinner.set_size_request(20, 20)
        self.ai_spinner.set_margin_start(10)
        self.ai_spinner.set_margin_end(10)
        self.ai_spinner.set_margin_top(5)
        self.ai_spinner.set_margin_bottom(5)
        
        # Add the spinner to the AI box
        self.ai_response_box.append(self.ai_spinner)
        
        # Set initial text
        self.ai_response_label.set_markdown("_Thinking..._")
        
        # Store the current response text
        self._current_response_text = ""
        
        # Add to chat history (will be updated with final response)
        self.chat_history["messages"].append({"role": "assistant", "content": ""})

    def update_streaming_response(self, chunk):
        """Update the AI response with a new chunk of text"""
        if not hasattr(self, '_current_response_text'):
            self._current_response_text = ""
            self._thinking_processed = False  # Flag to track if we've already processed thinking tags
        
        # Append the new chunk to the current text
        self._current_response_text += chunk
        
        # Process the response to extract the actual content
        # Only process thinking tags once
        if not hasattr(self, '_thinking_processed') or not self._thinking_processed:
            if "<think>" in self._current_response_text and "</think>" in self._current_response_text:
                # Extract thinking content
                thinking_start = self._current_response_text.find("<think>")
                thinking_end = self._current_response_text.find("</think>") + len("</think>")
                thinking_content = self._current_response_text[thinking_start + len("<think>"):thinking_end - len("</think>")].strip()
                
                # Store the thinking content for later use
                self._thinking_content = thinking_content
                
                # Extract the actual response (after the thinking part)
                processed_response = self._current_response_text[thinking_end:].strip()
                
                # If we already have an AI response label, add the thinking expander
                if self.ai_response_label and self.ai_response_label.get_parent():
                    self._add_thinking_expander(thinking_content)
                
                # Mark that we've processed thinking tags
                self._thinking_processed = True
            else:
                # No complete thinking section yet, just use the current content
                processed_response = self._current_response_text
        else:
            # We've already processed thinking tags, just update with content after the thinking section
            thinking_end = self._current_response_text.find("</think>") + len("</think>")
            if thinking_end > 0:
                processed_response = self._current_response_text[thinking_end:].strip()
            else:
                processed_response = self._current_response_text
        
        # Update the label with the current text
        if self.ai_response_label:
            self.ai_response_label.set_markdown(processed_response)
        
        # Update the chat history
        if self.chat_history["messages"] and self.chat_history["messages"][-1]["role"] == "assistant":
            self.chat_history["messages"][-1]["content"] = processed_response
        
        # Scroll to bottom as content is updated
        self._scroll_to_bottom()

    def finish_streaming_response(self):
        """Finalize the streaming response by removing the spinner"""
        # Remove the spinner if it exists
        if hasattr(self, 'ai_spinner') and self.ai_spinner:
            parent = self.ai_spinner.get_parent()
            if parent:
                parent.remove(self.ai_spinner)
            self.ai_spinner = None
        
        # Reset the thinking processed flag
        if hasattr(self, '_thinking_processed'):
            self._thinking_processed = False

    def start_new_ai_response(self):
        """Start a new AI response bubble with a spinner"""
        # Create a new AI response box
        new_ai_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        new_ai_box.set_halign(Gtk.Align.END)
        new_ai_box.add_css_class("card")
        new_ai_box.add_css_class("ai-bubble")
        new_ai_box.set_margin_start(48)
        
        # Create a new MarkdownLabel for the response
        from markdown_renderer import MarkdownLabel
        new_label = MarkdownLabel()
        new_label.set_margin_start(10)
        new_label.set_margin_end(10)
        new_label.set_margin_top(5)
        new_label.set_margin_bottom(5)
        new_label.set_markdown("_Thinking..._")
        
        # Create a spinner (throbber)
        spinner = Gtk.Spinner()
        spinner.set_spinning(True)
        spinner.set_size_request(20, 20)
        spinner.set_margin_start(5)
        spinner.set_margin_end(10)
        
        # Create a box to hold the label and spinner
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        content_box.append(new_label)
        content_box.append(spinner)
        
        # Add the content box to the new AI box
        new_ai_box.append(content_box)
        
        # Add the new AI box to the content box
        self.content_box.append(new_ai_box)
        
        # Make sure the new AI box is visible
        new_ai_box.set_visible(True)
        
        # Add placeholder to chat history (will be updated with final response)
        self.chat_history["messages"].append({"role": "assistant", "content": ""})
        
        # Store references for later updates
        self._streaming_ai_box = new_ai_box
        self._streaming_label = new_label
        self._streaming_spinner = spinner
        self._streaming_content = ""
        
        # Return the new AI box and label
        return new_ai_box, new_label

    def update_streaming_ai_response(self, chunk):
        """Update the streaming AI response with a new chunk of text"""
        if not hasattr(self, '_streaming_content'):
            self._streaming_content = ""
        
        # Append the new chunk to the current text
        self._streaming_content += chunk
        
        # Check if we have a complete thinking section
        if "<think>" in self._streaming_content and "</think>" in self._streaming_content:
            # Extract thinking content
            thinking_start = self._streaming_content.find("<think>")
            thinking_end = self._streaming_content.find("</think>") + len("</think>")
            thinking_content = self._streaming_content[thinking_start + len("<think>"):thinking_end - len("</think>")].strip()
            
            # Store the thinking content
            self._thinking_content = thinking_content
            
            # Extract the actual response (after the thinking part)
            processed_response = self._streaming_content[thinking_end:].strip()
            
            # If we have a streaming label, update it with just the response part
            if hasattr(self, '_streaming_label') and self._streaming_label:
                self._streaming_label.set_markdown(processed_response)
                
                # If we don't already have a thinking expander, add one
                if not hasattr(self, '_thinking_expander_added') or not self._thinking_expander_added:
                    # Get the parent of the streaming label
                    parent = self._streaming_label.get_parent()
                    
                    # If the parent is a horizontal box (for label and spinner), get its parent
                    if isinstance(parent, Gtk.Box) and parent.get_orientation() == Gtk.Orientation.HORIZONTAL:
                        parent = parent.get_parent()
                    
                    # Create a vertical box to hold both the thinking expander and the response
                    if not isinstance(parent, Gtk.Box) or parent.get_orientation() != Gtk.Orientation.VERTICAL:
                        # Create a new vertical box
                        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
                        
                        # Replace the streaming label with the vbox in its parent
                        old_parent = self._streaming_label.get_parent()
                        if old_parent:
                            # If the parent is a horizontal box with the spinner, we need to handle differently
                            if isinstance(old_parent, Gtk.Box) and old_parent.get_orientation() == Gtk.Orientation.HORIZONTAL:
                                # Get the grandparent
                                grandparent = old_parent.get_parent()
                                if grandparent:
                                    # Remove the horizontal box from its parent
                                    grandparent.remove(old_parent)
                                    
                                    # Add the vbox to the grandparent
                                    grandparent.append(vbox)
                                    
                                    # Create a new horizontal box for the label and spinner
                                    hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
                                    
                                    # Add the label to the horizontal box
                                    old_parent.remove(self._streaming_label)
                                    hbox.append(self._streaming_label)
                                    
                                    # Add the spinner to the horizontal box if it exists
                                    if hasattr(self, '_streaming_spinner') and self._streaming_spinner:
                                        old_parent.remove(self._streaming_spinner)
                                        hbox.append(self._streaming_spinner)
                                    
                                    # Add the horizontal box to the vbox
                                    vbox.append(hbox)
                            else:
                                # Standard case - just replace the label with the vbox
                                old_parent.remove(self._streaming_label)
                                old_parent.append(vbox)
                                vbox.append(self._streaming_label)
                        
                        # Add the thinking expander to the vbox
                        self._add_thinking_expander(thinking_content, vbox)
                    else:
                        # Parent is already a vertical box, just add the thinking expander
                        self._add_thinking_expander(thinking_content, parent)
                    
                    # Mark that we've added the thinking expander
                    self._thinking_expander_added = True
            
            # Update the chat history
            if self.chat_history["messages"] and self.chat_history["messages"][-1]["role"] == "assistant":
                self.chat_history["messages"][-1]["content"] = processed_response
        else:
            # No complete thinking section yet, just update with the current content
            processed_response = self._process_response(self._streaming_content)
            
            # Update the label with the current text
            if hasattr(self, '_streaming_label') and self._streaming_label:
                self._streaming_label.set_markdown(processed_response)
            
            # Update the chat history
            if self.chat_history["messages"] and self.chat_history["messages"][-1]["role"] == "assistant":
                self.chat_history["messages"][-1]["content"] = processed_response
        
        # Scroll to bottom as content is updated
        self._scroll_to_bottom()

    def finish_streaming_ai_response(self):
        """Finalize the streaming AI response by removing the spinner"""
        # Remove the spinner if it exists
        if hasattr(self, '_streaming_spinner') and self._streaming_spinner:
            parent = self._streaming_spinner.get_parent()
            if parent:
                parent.remove(self._streaming_spinner)
            self._streaming_spinner = None
            
        # Reset the streaming flags
        self._streaming_content = ""
        if hasattr(self, '_thinking_expander_added'):
            self._thinking_expander_added = False