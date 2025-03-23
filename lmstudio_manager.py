import threading
import traceback
import time
import requests
import json
import os
import platform
import datetime

# Load configuration
def load_config():
    """Load LM Studio API configuration from config file"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('lmstudio_api_url', 'http://localhost:1234/v1')
        return 'http://localhost:1234/v1'
    except Exception as e:
        print(f"Error loading config: {e}")
        return 'http://localhost:1234/v1'

# Check if LM Studio is available
LMSTUDIO_AVAILABLE = True
LMSTUDIO_API_URL = load_config()

class LMStudioManager:
    def __init__(self):
        """Initialize the LM Studio Manager"""
        self.available_models = []
        self.current_model = None
        self.server = None
        self.pending_tool_calls = {}
        self.current_chat = []
        
        # Try to get available models
        self.refresh_models()
    
    def refresh_models(self):
        """Refresh the list of available models"""
        try:
            response = requests.get(f"{LMSTUDIO_API_URL}/models")
            if response.status_code == 200:
                self.available_models = response.json().get('data', [])
                return True
            else:
                print(f"Error getting models: {response.status_code}")
                return False
        except Exception as e:
            print(f"Error refreshing models: {e}")
            traceback.print_exc()
            return False
    
    def set_model(self, model_index):
        """Set the current model by index"""
        try:
            if model_index >= len(self.available_models):
                print(f"Error: Invalid model index {model_index}, only {len(self.available_models)} models available")
                return False
                
            # Get the model ID from the available models list
            model_id = self.available_models[model_index].get('id', '')
            if not model_id:
                print(f"Error: Model at index {model_index} has no ID")
                return False
                
            # Store the model ID
            self.current_model = model_id
            print(f"Set current model to: {model_id}")
            return True
        except Exception as e:
            print(f"Error setting model: {e}")
            traceback.print_exc()
            return False
    
    def _create_chat_payload(self, prompt, temperature=0.7, max_tokens=-1, stream=False):
        """Create a standard chat completion request payload"""
        return {
            "model": self.current_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream
        }
    
    def _handle_api_error(self, response, error_prefix="Error"):
        """Handle API error responses"""
        error_msg = f"{error_prefix}: API returned status code {response.status_code}"
        print(f"{error_msg}, response: {response.text}")
        return error_msg
    
    def get_response(self, prompt):
        """Get a response from the current model"""
        if not self.current_model:
            return "Error: No model loaded. Please select a model."
        
        try:
            print(f"Using model: {self.current_model}")
            
            # Create a chat completion request
            payload = self._create_chat_payload(prompt)
            
            # Debug: Print the full request payload
            print(f"DEBUG - API Request: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{LMSTUDIO_API_URL}/chat/completions", 
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                # Debug: Print the response (truncated for readability)
                response_content = result['choices'][0]['message']['content']
                print(f"DEBUG - API Response: {response_content[:100]}...")
                return response_content
            else:
                return self._handle_api_error(response)
        except Exception as e:
            error_msg = f"Error getting response: {e}"
            print(error_msg)
            traceback.print_exc()
            return error_msg
    
    def get_streaming_response(self, prompt, on_chunk=None, on_complete=None):
        """Get a streaming response from the current model"""
        if not self.current_model:
            if on_complete:
                on_complete("Error: No model loaded. Please select a model.")
            return "Error: No model loaded. Please select a model."
        
        try:
            print(f"Using model: {self.current_model}")
            
            # Create a chat completion request with stream=True
            payload = self._create_chat_payload(prompt, stream=True)
            
            # Debug: Print the request payload
            print(f"DEBUG - Streaming API Request: {json.dumps(payload, indent=2)}")
            
            # Make the streaming request
            response = requests.post(
                f"{LMSTUDIO_API_URL}/chat/completions", 
                json=payload,
                stream=True
            )
            
            if response.status_code != 200:
                error_msg = f"Error: API returned status code {response.status_code}"
                print(f"{error_msg}, response: {response.text}")
                if on_complete:
                    on_complete(error_msg)
                return error_msg
            
            # Process the streaming response
            full_response = ""
            for line in response.iter_lines():
                if line:
                    # Remove the "data: " prefix and parse the JSON
                    line_text = line.decode('utf-8')
                    if line_text.startswith("data: "):
                        json_str = line_text[6:]  # Remove "data: " prefix
                        
                        # Skip "[DONE]" message
                        if json_str.strip() == "[DONE]":
                            continue
                        
                        try:
                            chunk_data = json.loads(json_str)
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    content = delta["content"]
                                    full_response += content
                                    
                                    # Call the on_chunk callback if provided
                                    if on_chunk:
                                        on_chunk(content)
                        except json.JSONDecodeError:
                            print(f"Error parsing JSON from chunk: {json_str}")
                        except Exception as e:
                            print(f"Error processing chunk: {e}")
            
            # Call the on_complete callback if provided
            if on_complete:
                on_complete(full_response)
            
            return full_response
        except Exception as e:
            error_msg = f"Error getting streaming response: {e}"
            print(error_msg)
            traceback.print_exc()
            if on_complete:
                on_complete(error_msg)
            return error_msg
    
    def run_agent(self, prompt, tools, on_message=None):
        """Run the model in agent mode with tools"""
        if not LMSTUDIO_AVAILABLE or not self.current_model:
            if on_message:
                on_message("Error: LM Studio not available or no model loaded")
            return "Error: LM Studio not available or no model loaded"
        
        try:
            # Try to import psutil for system specs, but handle case where it's not installed
            try:
                import psutil
                memory_info = f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB total"
                cpu_cores = f"{psutil.cpu_count(logical=True)} logical cores"
            except ImportError:
                memory_info = "Information not available"
                cpu_cores = "Information not available"
            
            # Get system information
            try:
                # Try to get Ubuntu version specifically
                ubuntu_version = "Unknown"
                if platform.system() == "Linux":
                    try:
                        # Try to read from os-release file
                        with open('/etc/os-release', 'r') as f:
                            os_info = {}
                            for line in f:
                                if '=' in line:
                                    key, value = line.rstrip().split('=', 1)
                                    os_info[key] = value.strip('"')
                        
                        if 'VERSION_ID' in os_info and 'NAME' in os_info:
                            ubuntu_version = f"{os_info['NAME']} {os_info['VERSION_ID']}"
                        elif 'PRETTY_NAME' in os_info:
                            ubuntu_version = os_info['PRETTY_NAME']
                    except Exception as e:
                        print(f"Error getting Ubuntu version: {e}")
                
                system_info = f"""
System Information:
- OS: {ubuntu_version} (Kernel: {platform.system()} {platform.release()})
- Python: {platform.python_version()}
- CPU: {platform.processor()} ({cpu_cores})
- Memory: {memory_info}
- Current Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            except Exception as e:
                # Fallback to basic system info if there's an error
                system_info = f"""
System Information:
- OS: {platform.system()} {platform.release()} ({platform.version()})
- Python: {platform.python_version()}
- CPU: {platform.processor()} ({cpu_cores})
- Memory: {memory_info}
- Current Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
                print(f"Error getting detailed system info: {e}")

            print(f"DEBUG - System info: {system_info}")

            # systtem prompt
            system_prompt = """
You are an AI assistant that lives in the terminal on a linux system. 
You can write message responses to the user, and you can execute commands using the tools provided to you. 
You can also use markdown to format your responses. 

Your role is to help the user with their high level tasks by executing commands and writing responses back to the user.

Start the conversation by providing the user a short overview of the task and the commands you will be executing. If the user confirms, you will run the commands. You can go ahead and run the command, if the user confirms in the same message.

DO NOT tell the user what commands to run. You MUST run the commands yourself using tool calls 1 by 1 and report back the output, then run the next command, until the task is complete.

If you are executing a command that will require confirmation from the user, like Y/N, run the command with a flag like "-y" to automatically confirm.

Always err on the side of caution. For instance, instead of running "mv /etc/apt/sources.list /etc/apt/sources.list.bak", run "cp /etc/apt/sources.list /etc/apt/sources.list.bak".

DO NOT run interactive commands like "vim" or "nano".
ONLY run commands that will output to the terminal and return a response, like "ls", "cat", "git status", etc. 
"sudo" is ok to run, since we handle that in the UI.

Always run only one command at a time, and wait for the tool result to come back before running the next command.
"""
            
            # Create a system message with the system info
            system_message = {"role": "system", "content": system_prompt + " " + system_info}
            
            # Create a new conversation or continue existing one
            if not hasattr(self, 'current_chat') or not self.current_chat:
                self.current_chat = [system_message, {"role": "user", "content": prompt}]
            else:
                # Check if we already have a system message
                has_system_message = False
                for msg in self.current_chat:
                    if msg.get("role") == "system":
                        has_system_message = True
                        # Update the system message with current info
                        msg["content"] = system_prompt + " " + system_info
                        break
                
                if not has_system_message:
                    # Insert system message at the beginning
                    self.current_chat.insert(0, system_message)
                
                # Add the user message
                self.current_chat.append({"role": "user", "content": prompt})
            
            # Clean up the conversation history to ensure valid format
            valid_messages = []
            for msg in self.current_chat:
                # Skip invalid messages
                if not isinstance(msg, dict) or "role" not in msg:
                    continue
                
                # Make a copy of the message to avoid modifying the original
                clean_msg = msg.copy()
                
                # Ensure content field exists
                if "content" not in clean_msg:
                    clean_msg["content"] = ""
                
                # Fix tool_calls if they exist
                if "tool_calls" in clean_msg:
                    fixed_tool_calls = []
                    for tool_call in clean_msg["tool_calls"]:
                        # Skip invalid tool calls
                        if not isinstance(tool_call, dict) or "function" not in tool_call:
                            continue
                        
                        # Make a copy of the tool call
                        fixed_tool_call = tool_call.copy()
                        
                        # Ensure function has valid arguments
                        if "function" in fixed_tool_call:
                            if "arguments" not in fixed_tool_call["function"] or not fixed_tool_call["function"]["arguments"]:
                                # Add a default command argument
                                fixed_tool_call["function"]["arguments"] = '{"command": "df -h"}'
                            elif fixed_tool_call["function"]["arguments"] == "{}":
                                # Replace empty arguments with a default command
                                fixed_tool_call["function"]["arguments"] = '{"command": "df -h"}'
                            
                            # Try to parse the arguments to ensure they're valid JSON
                            try:
                                args = json.loads(fixed_tool_call["function"]["arguments"])
                                # If command is missing, add it
                                if "command" not in args:
                                    args["command"] = "df -h"
                                    fixed_tool_call["function"]["arguments"] = json.dumps(args)
                            except json.JSONDecodeError:
                                # If arguments aren't valid JSON, replace with a default
                                fixed_tool_call["function"]["arguments"] = '{"command": "df -h"}'
                        
                        fixed_tool_calls.append(fixed_tool_call)
                    
                    clean_msg["tool_calls"] = fixed_tool_calls
                
                valid_messages.append(clean_msg)

            # Replace the current chat with the cleaned up version
            self.current_chat = valid_messages
            
            # Convert tools to the format expected by the API
            api_tools = []
            for tool in tools:
                if callable(tool):
                    # Convert function to tool definition
                    tool_def = {
                        "type": "function",
                        "function": {
                            "name": tool.__name__,
                            "description": tool.__doc__ or f"Execute {tool.__name__}",
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
                    }
                    api_tools.append(tool_def)
                else:
                    # Assume it's already in the right format
                    api_tools.append(tool)
            
            # Make the API request
            payload = {
                "model": self.current_model,
                "messages": self.current_chat,
                "tools": api_tools,
                "tool_choice": "auto"
            }
            
            # Debug: Print the full request payload
            print(f"DEBUG - Agent API Request: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{LMSTUDIO_API_URL}/chat/completions", 
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"Error: API returned status code {response.status_code}"
                print(f"DEBUG - API Error Response: {response.text}")
                if on_message:
                    on_message(error_msg)
                return error_msg
            
            result = response.json()
            # Debug: Print the response
            print(f"DEBUG - Agent API Response: {json.dumps(result, indent=2)}")
            
            # Check if the response includes tool calls
            assistant_message = result['choices'][0]['message']
            if 'tool_calls' in assistant_message:
                # Store the tool calls for later execution
                tool_calls = assistant_message['tool_calls']
                for tool_call in tool_calls:
                    tool_id = tool_call['id']
                    function_name = tool_call['function']['name']
                    arguments = json.loads(tool_call['function']['arguments'])
                    
                    # Store the pending tool call
                    self.pending_tool_calls[tool_id] = {
                        "command": arguments.get('command', ''),
                        "status": "pending",
                        "id": tool_id,
                        "function_name": function_name
                    }
                
                # Add the assistant message to the conversation
                self.current_chat.append({
                    "role": "assistant",
                    "tool_calls": tool_calls
                })
                
                # Call the on_message callback with the tool call request
                if on_message:
                    on_message(json.dumps(assistant_message))
                
                # Return the tool call request
                return json.dumps(assistant_message)
            else:
                # No tool calls, just a regular response
                content = assistant_message.get('content', '')
                
                # Add the assistant message to the conversation
                self.current_chat.append({
                    "role": "assistant",
                    "content": content
                })
                
                # Call the on_message callback with the response
                if on_message:
                    on_message(content)
                
                return content
        except Exception as e:
            error_msg = f"Error running agent: {e}"
            if on_message:
                on_message(error_msg)
            traceback.print_exc()
            return error_msg
    
    def send_tool_result(self, tool_id, result):
        """Send the result of a tool call back to the AI"""
        try:
            print(f"DEBUG - Starting send_tool_result for ID: {tool_id}")
            
            # Validate and update tool info
            if not self._validate_and_update_tool(tool_id, result):
                return False
            
            # Add tool message to conversation
            self._add_tool_message_to_conversation(tool_id, result)
            
            # Create payload and make API request
            payload = self._create_tool_result_payload()
            if not payload:
                return False
            
            # Debug: Print the request payload
            self._debug_print_payload(payload)
            
            # Make the API request
            return self._make_streaming_api_request(payload)
        except Exception as e:
            error_msg = f"Error sending tool result: {e}"
            print(f"DEBUG - {error_msg}")
            traceback.print_exc()
            return False

    def _validate_and_update_tool(self, tool_id, result):
        """Validate tool ID exists and update tool info with result"""
        if tool_id not in self.pending_tool_calls:
            print(f"DEBUG - Error: Tool ID {tool_id} not found in pending tool calls")
            return False
        
        # Get the tool info
        tool_info = self.pending_tool_calls[tool_id]
        print(f"DEBUG - Found tool info: {tool_info}")
        
        # Update the tool info with the result
        tool_info["result"] = result
        tool_info["status"] = "completed"
        return True

    def _add_tool_message_to_conversation(self, tool_id, result):
        """Add tool message to the conversation history"""
        # Create a new message for the tool result
        tool_message = {
            "role": "tool",
            "content": result,
            "tool_call_id": tool_id
        }
        print(f"DEBUG - Created tool message")
        
        # Add the tool message to the conversation
        if hasattr(self, 'current_chat'):
            self.current_chat.append(tool_message)
            print(f"DEBUG - Added tool message to current_chat")
            self._ensure_valid_conversation_structure()

    def _validate_model_is_set(self):
        """Validate that a model is currently set"""
        if not hasattr(self, 'current_model') or not self.current_model:
            print(f"DEBUG - Error: No current model set")
            return False
        
        print(f"DEBUG - Current model is set: {self.current_model}")
        return True

    def _import_gtk_libraries(self):
        """Import required GTK libraries"""
        try:
            from gi.repository import GLib, Gtk
            print(f"DEBUG - Imported GLib and Gtk")
            return True
        except ImportError as e:
            print(f"DEBUG - Error importing GLib or Gtk: {e}")
            return False

    def _debug_print_payload(self, payload):
        """Print the payload for debugging"""
        try:
            print(f"DEBUG - Tool Result API Request: {json.dumps(payload, indent=2)}")
        except Exception as e:
            print(f"DEBUG - Error printing payload: {e}")

    def _ensure_valid_conversation_structure(self):
        """Ensure the conversation has a proper structure with system and user messages"""
        # Check if we have a system message
        has_system = False
        has_user = False
        for msg in self.current_chat:
            if msg.get("role") == "system":
                has_system = True
            if msg.get("role") == "user":
                has_user = True
        
        # If no system message, add one
        if not has_system:
            system_prompt = """
You are an AI assistant that lives in the terminal on a linux system. 
You can write message responses to the user, and you can execute commands using the tools provided to you. 
You can also use markdown to format your responses.
"""
            self.current_chat.insert(0, {"role": "system", "content": system_prompt})
            print(f"DEBUG - Added system message to current_chat")
        
        # If no user message, add a default one
        if not has_user:
            self.current_chat.insert(1, {"role": "user", "content": "Help me with my Linux system."})
            print(f"DEBUG - Added default user message to current_chat")

    def _create_ui_response_row(self):
        """Create a new UI row for displaying the AI response"""
        try:
            print(f"DEBUG - Inside create_new_response_row")
            # Find all windows
            from gi.repository import Gtk
            windows = Gtk.Window.list_toplevels()
            print(f"DEBUG - Found {len(windows)} top-level windows")
            
            for window in windows:
                # Check if it's our application window
                if hasattr(window, 'command_rows'):
                    print(f"DEBUG - Found window with command_rows")
                    # Create a new command row
                    try:
                        from command_row import CommandRow
                        print(f"DEBUG - Imported CommandRow")
                        new_row = CommandRow()
                        print(f"DEBUG - Created new CommandRow")
                    except Exception as e:
                        print(f"DEBUG - Error creating CommandRow: {e}")
                        traceback.print_exc()
                        return None
                    
                    # Check if the window has the correct container attribute
                    if hasattr(window, 'command_container'):
                        try:
                            window.command_container.append(new_row)
                            window.command_rows.append(new_row)
                            print(f"DEBUG - Added new row to command_container")
                        except Exception as e:
                            print(f"DEBUG - Error adding row to container: {e}")
                            traceback.print_exc()
                            return None
                    else:
                        print("DEBUG - Error: Window has no command_container attribute")
                        return None
                    
                    # Initialize the streaming response UI
                    try:
                        # Use start_new_ai_response instead of start_ai_response
                        new_row.start_new_ai_response()
                        print(f"DEBUG - Started new AI response")
                    except Exception as e:
                        print(f"DEBUG - Error starting new AI response: {e}")
                        traceback.print_exc()
                        return None
                    
                    # Store a reference to the command row for later use
                    self._current_command_row = new_row
                    
                    # Force the window to redraw
                    try:
                        window.queue_draw()
                        print(f"DEBUG - Queued window redraw")
                    except Exception as e:
                        print(f"DEBUG - Error queuing window redraw: {e}")
                    
                    # Scroll to the bottom
                    if hasattr(window, '_scroll_to_bottom'):
                        try:
                            from gi.repository import GLib
                            GLib.idle_add(window._scroll_to_bottom)
                            print(f"DEBUG - Added scroll_to_bottom to idle queue")
                        except Exception as e:
                            print(f"DEBUG - Error adding scroll_to_bottom to idle queue: {e}")
                    
                    return new_row
            
            print(f"DEBUG - No suitable window found")
            return None
        except Exception as e:
            print(f"DEBUG - Unexpected error in create_new_response_row: {e}")
            traceback.print_exc()
            return None

    def _create_tool_result_payload(self):
        """Create the payload for the tool result API request"""
        return {
            "model": self.current_model,
            "messages": self.current_chat,
            "tools": [
                {
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
                }
            ],
            "tool_choice": "auto",
            "stream": True
        }

    def _process_streaming_response(self, response, row_ref, accumulated_tool_calls):
        """Process the streaming response from the API"""
        from gi.repository import GLib
        full_response = ""
        
        # Create a separate thread for processing the streaming response
        def process_stream():
            nonlocal full_response
            try:
                for line in response.iter_lines():
                    if line:
                        line_text = line.decode('utf-8')
                        if line_text.startswith("data: "):
                            json_str = line_text[6:]  # Remove "data: " prefix
                            
                            # Skip "[DONE]" message
                            if json_str.strip() == "[DONE]":
                                print(f"DEBUG - Received [DONE] message")
                                continue
                            
                            try:
                                chunk_data = json.loads(json_str)
                                if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    
                                    # Handle content chunks
                                    if "content" in delta:
                                        content = delta["content"]
                                        full_response += content
                                        print(f"DEBUG - Received content chunk: {content[:20]}...")
                                        
                                        # Update the UI with the new content using idle_add
                                        GLib.idle_add(self._update_ui_with_content, row_ref, content)
                                    
                                    # Handle tool call chunks
                                    if "tool_calls" in delta:
                                        self._process_tool_call_delta(delta["tool_calls"], accumulated_tool_calls)
                            except json.JSONDecodeError:
                                print(f"DEBUG - Error parsing JSON from chunk: {json_str}")
                            except Exception as e:
                                print(f"DEBUG - Error processing chunk: {e}")
                                traceback.print_exc()
            
                # Finalize the streaming UI when done
                GLib.idle_add(self._finish_ui_and_process_tool_calls, row_ref, accumulated_tool_calls)
                
            except Exception as e:
                print(f"DEBUG - Error in streaming thread: {e}")
                traceback.print_exc()
                GLib.idle_add(self._show_error, row_ref, f"Error: {str(e)}")
        
        # Start the processing in a separate thread
        import threading
        stream_thread = threading.Thread(target=process_stream)
        stream_thread.daemon = True
        stream_thread.start()
        
        # Wait for the thread to complete, but with a timeout
        # This allows the main thread to continue processing GTK events
        stream_thread.join(timeout=0.1)
        
        return full_response

    def _send_streaming_request(self, payload):
        """Send the streaming request to the API"""
        try:
            # Use a session for better connection handling
            session = requests.Session()
            
            # Set a reasonable timeout
            response = session.post(
                f"{LMSTUDIO_API_URL}/chat/completions", 
                json=payload,
                stream=True,
                timeout=30  # 30 second timeout
            )
            
            print(f"DEBUG - API request made, status code: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"Error: API returned status code {response.status_code}"
                print(f"{error_msg}, response: {response.text}")
                
                # Update UI with error
                from gi.repository import GLib
                GLib.idle_add(self._show_error, self._current_command_row, error_msg)
                return None
            
            return response
        except Exception as e:
            print(f"DEBUG - Error sending streaming request: {e}")
            traceback.print_exc()
            
            # Update UI with error
            try:
                from gi.repository import GLib
                GLib.idle_add(self._show_error, self._current_command_row, f"Error: {str(e)}")
            except:
                pass
            return None

    def _make_streaming_api_request(self, payload):
        """Make a streaming API request and process the response"""
        try:
            # Import required GTK libraries
            if not self._import_gtk_libraries():
                return False
            
            # Create UI response row
            row_ref = self._create_ui_response_row()
            if not row_ref:
                print(f"DEBUG - Failed to create UI response row")
                return False
            
            print(f"DEBUG - About to make API request")
            response = self._send_streaming_request(payload)
            if not response:
                return False
            
            # Process the streaming response
            print(f"DEBUG - Starting to process streaming response")
            accumulated_tool_calls = {}  # Dictionary to accumulate tool call data by ID
            
            # Process the streaming response in a way that doesn't block the UI
            self._process_streaming_response(response, row_ref, accumulated_tool_calls)
            
            # We'll handle the tool calls after streaming is complete in the streaming thread
            print(f"DEBUG - Tool result processing initiated")
            return True
        except Exception as e:
            error_msg = f"Error in streaming request: {e}"
            print(f"DEBUG - {error_msg}")
            traceback.print_exc()
            
            # Try to update UI with error if possible
            try:
                from gi.repository import GLib
                GLib.idle_add(self._show_error, row_ref, error_msg)
            except:
                pass
            return False

    def _update_ui_with_content(self, row_ref, content_chunk):
        """Update the UI with a new content chunk"""
        try:
            # Use the stored command row reference
            if hasattr(self, '_current_command_row') and self._current_command_row:
                print(f"DEBUG - Updating UI with content chunk using _current_command_row")
                # Use update_streaming_ai_response instead of update_streaming_response
                self._current_command_row.update_streaming_ai_response(content_chunk)
            elif row_ref:
                print(f"DEBUG - Updating UI with content chunk using row_ref")
                # Use update_streaming_ai_response instead of update_streaming_response
                row_ref.update_streaming_ai_response(content_chunk)
            else:
                print(f"DEBUG - No row reference available for UI update")
            return False
        except Exception as e:
            print(f"DEBUG - Error updating UI with content: {e}")
            traceback.print_exc()
            return False

    def _process_tool_call_delta(self, tool_calls_delta, accumulated_tool_calls):
        """Process tool call delta chunks"""
        for tool_call_delta in tool_calls_delta:
            # Get the tool call index
            index = tool_call_delta.get("index", 0)
            
            # Get the tool call ID
            tool_id = tool_call_delta.get("id")
            
            # Create a key for this tool call based on index
            tool_key = f"tool_{index}"
            
            # Initialize this tool call in our accumulator if it doesn't exist
            if tool_key not in accumulated_tool_calls:
                accumulated_tool_calls[tool_key] = {
                    "id": tool_id,
                    "type": tool_call_delta.get("type", "function"),
                    "function": {"name": "", "arguments": ""}
                }
            
            # If we got an ID in this chunk, update it
            if tool_id:
                accumulated_tool_calls[tool_key]["id"] = tool_id
                
            # Update the function name and arguments if present
            if "function" in tool_call_delta:
                if "name" in tool_call_delta["function"] and tool_call_delta["function"]["name"]:
                    accumulated_tool_calls[tool_key]["function"]["name"] = tool_call_delta["function"]["name"]
                
                # Append to arguments if present
                if "arguments" in tool_call_delta["function"]:
                    accumulated_tool_calls[tool_key]["function"]["arguments"] += tool_call_delta["function"]["arguments"]

    def _show_error(self, row_ref, error_msg):
        """Show an error message in the UI"""
        try:
            print(f"DEBUG - Inside show_error")
            if hasattr(self, '_current_command_row') and self._current_command_row:
                print(f"DEBUG - Updating UI with error using _current_command_row")
                self._current_command_row.finish_streaming_ai_response()
                self._current_command_row.update_ai_response(error_msg)
            elif row_ref:
                print(f"DEBUG - Updating UI with error using row_ref")
                row_ref.finish_streaming_ai_response()
                row_ref.update_ai_response(error_msg)
            else:
                print(f"DEBUG - No row reference available for error update")
            return False
        except Exception as e:
            print(f"DEBUG - Error in show_error: {e}")
            traceback.print_exc()
            return False

    def _finish_ui_and_process_tool_calls(self, row_ref, accumulated_tool_calls):
        """Finish the streaming UI and process any tool calls"""
        try:
            print(f"DEBUG - Inside _finish_ui_and_process_tool_calls")
            
            # First finish the streaming UI
            if hasattr(self, '_current_command_row') and self._current_command_row:
                print(f"DEBUG - Finishing streaming using _current_command_row")
                self._current_command_row.finish_streaming_ai_response()
            elif row_ref:
                print(f"DEBUG - Finishing streaming using row_ref")
                row_ref.finish_streaming_ai_response()
            else:
                print(f"DEBUG - No row reference available to finish streaming")
                return False
            
            # Then process any tool calls
            tool_calls_data = list(accumulated_tool_calls.values())
            if tool_calls_data:
                print(f"DEBUG - Processing {len(tool_calls_data)} tool calls")
                
                # Get unique commands and their tool IDs
                unique_commands = {}
                for tool_call in tool_calls_data:
                    # Extract the command from the arguments
                    if "function" in tool_call and "arguments" in tool_call["function"]:
                        try:
                            # Parse the arguments JSON
                            args = json.loads(tool_call["function"]["arguments"])
                            command = args.get("command", "")
                            
                            if command:
                                # Store the command with its tool ID
                                unique_commands[command] = tool_call["id"]
                        except json.JSONDecodeError:
                            print(f"DEBUG - Error parsing arguments JSON: {tool_call['function']['arguments']}")
                        except Exception as e:
                            print(f"DEBUG - Error extracting command: {e}")
                
                # Store only the unique tool calls
                for command, tool_id in unique_commands.items():
                    # Store the pending tool call
                    self.pending_tool_calls[tool_id] = {
                        "command": command,
                        "status": "pending",
                        "id": tool_id,
                        "function_name": "terminal_execute"
                    }
                
                # Create a filtered list of tool calls with only unique commands
                filtered_tool_calls = []
                unique_tool_ids = set(unique_commands.values())
                for tool_call in tool_calls_data:
                    if tool_call["id"] in unique_tool_ids:
                        filtered_tool_calls.append(tool_call)
                
                # Add the assistant message to the conversation with filtered tool calls
                if hasattr(self, 'current_chat'):
                    self.current_chat.append({
                        "role": "assistant",
                        "content": "",  # Add empty content field to satisfy API requirements
                        "tool_calls": filtered_tool_calls
                    })
                
                # Process the tool calls in the UI
                if hasattr(self, '_current_command_row') and self._current_command_row:
                    # Create a JSON response with tool calls for the command row to process
                    tool_calls_json = json.dumps({"tool_calls": filtered_tool_calls})
                    print(f"DEBUG - Sending tool calls to command row: {tool_calls_json[:100]}...")
                    
                    # Update the UI with the tool calls
                    from gi.repository import GLib
                    GLib.idle_add(self._current_command_row._process_response, tool_calls_json)
            
            return False
        except Exception as e:
            print(f"DEBUG - Error in _finish_ui_and_process_tool_calls: {e}")
            traceback.print_exc()
            return False

    def _finish_ui(self, row_ref):
        """Finish the streaming UI by removing the spinner"""
        try:
            print(f"DEBUG - Inside finish_ui")
            if hasattr(self, '_current_command_row') and self._current_command_row:
                print(f"DEBUG - Finishing streaming using _current_command_row")
                self._current_command_row.finish_streaming_ai_response()
            elif row_ref:
                print(f"DEBUG - Finishing streaming using row_ref")
                row_ref.finish_streaming_ai_response()
            else:
                print(f"DEBUG - No row reference available to finish streaming")
            return False
        except Exception as e:
            print(f"DEBUG - Error in finish_ui: {e}")
            traceback.print_exc()
            return False

    def shutdown(self):
        """Shutdown the LM Studio server"""
        if self.server:
            try:
                self.server.close()
                print("LM Studio server shut down")
            except Exception as e:
                print(f"Error shutting down LM Studio server: {e}")
        else:
            print("No LM Studio server instance to shut down")
    
    def execute_pending_tool_call(self, tool_id):
        """Execute a pending tool call that was previously deferred"""
        if tool_id in self.pending_tool_calls:
            from terminal import execute_command
            
            tool_info = self.pending_tool_calls[tool_id]
            command = tool_info["command"]
            
            # Mark as executing
            tool_info["status"] = "executing"
            
            # Execute the command
            result = execute_command(command, require_confirmation=False)
            
            # Update with result
            tool_info["result"] = result
            tool_info["status"] = "completed"
            
            return result
        else:
            return "Error: Tool call not found"
    
    def cancel_command(self, tool_id):
        """Cancel a pending command"""
        if tool_id in self.pending_tool_calls:
            # Mark as canceled
            self.pending_tool_calls[tool_id]["status"] = "canceled"
            return "Command canceled by user."
        else:
            return "Error: Command not found"
    
    def run_streaming_agent(self, prompt, tools, on_chunk=None, on_complete=None):
        """Run the model in agent mode with tools and streaming responses"""
        if not LMSTUDIO_AVAILABLE or not self.current_model:
            if on_complete:
                on_complete("Error: LM Studio not available or no model loaded")
            return "Error: LM Studio not available or no model loaded"
        
        try:
            # Get system information for context
            system_info = self._get_system_info()
            
            # Create system prompt and messages
            messages = self._create_agent_messages(prompt, system_info)
            
            # Convert tools to API format
            api_tools = self._convert_tools_to_api_format(tools)
            
            # Make the API request with stream=True
            payload = {
                "model": self.current_model,
                "messages": messages,
                "tools": api_tools,
                "tool_choice": "auto",
                "stream": True
            }
            
            # Debug: Print the request payload
            print(f"DEBUG - Streaming Agent API Request: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                f"{LMSTUDIO_API_URL}/chat/completions", 
                json=payload,
                stream=True
            )
            
            if response.status_code != 200:
                error_msg = f"Error: API returned status code {response.status_code}"
                print(f"DEBUG - API Error Response: {response.text}")
                if on_complete:
                    on_complete(error_msg)
                return error_msg
            
            # Process the streaming response
            result = self._process_streaming_agent_response(response, on_chunk)
            full_response, accumulated_tool_calls = result
            
            # Process any tool calls after streaming is complete
            return self._finalize_streaming_agent_response(full_response, accumulated_tool_calls, on_complete)
        except Exception as e:
            error_msg = f"Error running streaming agent: {e}"
            if on_complete:
                on_complete(error_msg)
            traceback.print_exc()
            return error_msg

    def _get_system_info(self):
        """Get system information for context"""
        try:
            # Try to import psutil for system specs
            try:
                import psutil
                memory_info = f"{round(psutil.virtual_memory().total / (1024**3), 2)} GB total"
                cpu_cores = f"{psutil.cpu_count(logical=True)} logical cores"
            except ImportError:
                memory_info = "Information not available"
                cpu_cores = "Information not available"
            
            # Try to get Ubuntu version specifically
            ubuntu_version = "Unknown"
            if platform.system() == "Linux":
                try:
                    # Try to read from os-release file
                    with open('/etc/os-release', 'r') as f:
                        os_info = {}
                        for line in f:
                            if '=' in line:
                                key, value = line.rstrip().split('=', 1)
                                os_info[key] = value.strip('"')
                
                    if 'VERSION_ID' in os_info and 'NAME' in os_info:
                        ubuntu_version = f"{os_info['NAME']} {os_info['VERSION_ID']}"
                    elif 'PRETTY_NAME' in os_info:
                        ubuntu_version = os_info['PRETTY_NAME']
                except Exception as e:
                    print(f"Error getting Ubuntu version: {e}")
            
            system_info = f"""
System Information:
- OS: {ubuntu_version} (Kernel: {platform.system()} {platform.release()})
- Python: {platform.python_version()}
- CPU: {platform.processor()} ({cpu_cores})
- Memory: {memory_info}
- Current Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        except Exception as e:
            # Fallback to basic system info if there's an error
            system_info = f"""
System Information:
- OS: {platform.system()} {platform.release()} ({platform.version()})
- Python: {platform.python_version()}
- CPU: {platform.processor()}
- Memory: Information not available
- Current Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            print(f"Error getting detailed system info: {e}")

        print(f"DEBUG - System info: {system_info}")
        return system_info

    def _create_agent_messages(self, prompt, system_info):
        """Create messages for agent with system prompt and history"""
        # System prompt
        system_prompt = """
You are an AI assistant that lives in the terminal on a linux system. 
You can write message responses to the user, and you can execute commands using the tools provided to you. 
You can also use markdown to format your responses. 

Your role is to help the user with their high level tasks by executing commands and writing responses back to the user.

Start the conversation by providing the user a short overview of the task and the commands you will be executing. If the user confirms, you will run the commands. You can go ahead and run the command, if the user confirms in the same message.

DO NOT tell the user what commands to run. You MUST run the commands yourself using tool calls 1 by 1 and report back the output, then run the next command, until the task is complete.

If you are executing a command that will require confirmation from the user, like Y/N, run the command with a flag like "-y" to automatically confirm.

Always err on the side of caution. For instance, instead of running "mv /etc/apt/sources.list /etc/apt/sources.list.bak", run "cp /etc/apt/sources.list /etc/apt/sources.list.bak".

DO NOT run interactive commands like "vim" or "nano".
ONLY run commands that will output to the terminal and return a response, like "ls", "cat", "git status", etc. 

Always run ONLY 1 tool call at a time, and wait for the tool result to come back before running the next terminal command.
"""
        
        # Create a system message with the system info
        system_message = {"role": "system", "content": system_prompt + " " + system_info}
        
        # Create a completely fresh conversation history
        # This avoids any potential issues with malformed messages from previous conversations
        messages = [
            system_message,
            {"role": "user", "content": prompt}
        ]
        
        # If we have a conversation history, add the most recent messages (up to 10)
        # But skip any messages with tool_calls to avoid potential format issues
        if hasattr(self, 'current_chat') and self.current_chat:
            # Get the last 10 messages, excluding the system message
            recent_messages = []
            for msg in self.current_chat:
                if msg.get("role") != "system" and "tool_calls" not in msg:
                    # Create a clean copy with only role and content
                    clean_msg = {
                        "role": msg["role"],
                        "content": msg.get("content", "")
                    }
                    recent_messages.append(clean_msg)
            
            # Take the last 10 messages
            recent_messages = recent_messages[-10:]
            
            # Replace our messages with system message + recent messages + new user message
            messages = [system_message] + recent_messages
            
            # Make sure the last message is the current user prompt
            if messages[-1]["role"] != "user" or messages[-1]["content"] != prompt:
                messages.append({"role": "user", "content": prompt})
        
        return messages

    def _convert_tools_to_api_format(self, tools):
        """Convert tools to the format expected by the API"""
        api_tools = []
        for tool in tools:
            if callable(tool):
                # Convert function to tool definition
                tool_def = {
                    "type": "function",
                    "function": {
                        "name": tool.__name__,
                        "description": tool.__doc__ or f"Execute {tool.__name__}",
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
                }
                api_tools.append(tool_def)
            else:
                # Assume it's already in the right format
                api_tools.append(tool)
        return api_tools

    def _process_streaming_agent_response(self, response, on_chunk=None):
        """Process the streaming response from the API"""
        full_response = ""
        accumulated_tool_calls = {}  # Dictionary to accumulate tool call data by ID
        
        for line in response.iter_lines():
            if line:
                line_text = line.decode('utf-8')
                if line_text.startswith("data: "):
                    json_str = line_text[6:]  # Remove "data: " prefix
                    
                    # Skip "[DONE]" message
                    if json_str.strip() == "[DONE]":
                        continue
                    
                    try:
                        chunk_data = json.loads(json_str)
                        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                            delta = chunk_data["choices"][0].get("delta", {})
                            
                            # Handle content chunks
                            if "content" in delta:
                                content = delta["content"]
                                full_response += content
                                
                                # Call the on_chunk callback if provided
                                if on_chunk:
                                    on_chunk(content)
                            
                            # Handle tool call chunks
                            if "tool_calls" in delta:
                                self._process_tool_call_delta(delta["tool_calls"], accumulated_tool_calls)
                    except json.JSONDecodeError:
                        print(f"Error parsing JSON from chunk: {json_str}")
                    except Exception as e:
                        print(f"Error processing chunk: {e}")
                        traceback.print_exc()
        
        return full_response, accumulated_tool_calls

    def _finalize_streaming_agent_response(self, full_response, accumulated_tool_calls, on_complete=None):
        """Process the final response and tool calls"""
        tool_calls_data = list(accumulated_tool_calls.values())
        if tool_calls_data:
            # Get unique commands and their tool IDs
            unique_commands = self._extract_unique_commands(tool_calls_data)
            
            # Store only the unique tool calls
            for command, tool_id in unique_commands.items():
                # Store the pending tool call
                self.pending_tool_calls[tool_id] = {
                    "command": command,
                    "status": "pending",
                    "id": tool_id,
                    "function_name": "terminal_execute"
                }
            
            # Create a filtered list of tool calls with only unique commands
            filtered_tool_calls = self._filter_tool_calls(tool_calls_data, unique_commands)
            
            # Add the assistant message to the conversation with filtered tool calls
            if hasattr(self, 'current_chat'):
                self.current_chat.append({
                    "role": "assistant",
                    "content": "",  # Add empty content field to satisfy API requirements
                    "tool_calls": filtered_tool_calls
                })
            
            # Call the on_complete callback with the filtered tool call request
            if on_complete:
                on_complete(json.dumps({"tool_calls": filtered_tool_calls}))
            
            return json.dumps({"tool_calls": filtered_tool_calls})
        else:
            # No tool calls, just a regular response
            # Add the assistant message to the conversation
            if hasattr(self, 'current_chat'):
                self.current_chat.append({
                    "role": "assistant",
                    "content": full_response
                })
            
            # Call the on_complete callback with the response
            if on_complete:
                on_complete(full_response)
            
            return full_response

    def _extract_unique_commands(self, tool_calls_data):
        """Extract unique commands from tool calls data"""
        unique_commands = {}
        
        for tool_call in tool_calls_data:
            # Extract the command from the arguments
            if "function" in tool_call and "arguments" in tool_call["function"]:
                try:
                    # Parse the arguments JSON
                    args = json.loads(tool_call["function"]["arguments"])
                    command = args.get("command", "")
                    
                    if command:
                        # Store the command with its tool ID
                        unique_commands[command] = tool_call["id"]
                except json.JSONDecodeError:
                    print(f"DEBUG - Error parsing arguments JSON: {tool_call['function']['arguments']}")
                except Exception as e:
                    print(f"DEBUG - Error extracting command: {e}")
        
        return unique_commands

    def _filter_tool_calls(self, tool_calls_data, unique_commands):
        """Filter tool calls to only include unique commands"""
        filtered_tool_calls = []
        
        # Create a set of tool IDs for unique commands
        unique_tool_ids = set(unique_commands.values())
        
        # Filter the tool calls to only include those with unique IDs
        for tool_call in tool_calls_data:
            if tool_call["id"] in unique_tool_ids:
                filtered_tool_calls.append(tool_call)
        
        return filtered_tool_calls

    def _process_accumulated_tool_calls(self, accumulated_tool_calls, row_ref=None):
        """Process accumulated tool calls after streaming is complete"""
        # Convert the accumulated tool calls to a list
        tool_calls_data = list(accumulated_tool_calls.values())
        
        if tool_calls_data:
            # Get unique commands and their tool IDs
            unique_commands = self._extract_unique_commands(tool_calls_data)
            
            # Store only the unique tool calls
            for command, tool_id in unique_commands.items():
                # Store the pending tool call
                self.pending_tool_calls[tool_id] = {
                    "command": command,
                    "status": "pending",
                    "id": tool_id,
                    "function_name": "terminal_execute"
                }
            
            # Create a filtered list of tool calls with only unique commands
            filtered_tool_calls = self._filter_tool_calls(tool_calls_data, unique_commands)
            
            # Add the assistant message to the conversation with filtered tool calls
            if hasattr(self, 'current_chat'):
                self.current_chat.append({
                    "role": "assistant",
                    "content": "",  # Add empty content field to satisfy API requirements
                    "tool_calls": filtered_tool_calls
                })
            
            # Update UI with tool call information if needed
            if row_ref:
                try:
                    from gi.repository import GLib
                    GLib.idle_add(self._show_tool_calls, row_ref, filtered_tool_calls)
                except Exception as e:
                    print(f"DEBUG - Error showing tool calls: {e}")
                    traceback.print_exc()
        
        return tool_calls_data

    def _show_tool_calls(self, row_ref, tool_calls):
        """Show tool calls in the UI"""
        try:
            if hasattr(self, '_current_command_row') and self._current_command_row:
                # Format the tool calls as markdown
                tool_calls_md = "**Tool Calls:**\n\n"
                for tool_call in tool_calls:
                    function_name = tool_call.get("function", {}).get("name", "unknown")
                    args = tool_call.get("function", {}).get("arguments", "{}")
                    try:
                        args_dict = json.loads(args)
                        command = args_dict.get("command", "")
                        if command:
                            tool_calls_md += f"- `{command}`\n"
                    except:
                        tool_calls_md += f"- `{args}`\n"
                
                # Update the UI with the tool calls
                self._current_command_row.update_ai_response(tool_calls_md)
            return False
        except Exception as e:
            print(f"DEBUG - Error in show_tool_calls: {e}")
            traceback.print_exc()
            return False