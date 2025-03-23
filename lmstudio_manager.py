import threading
import traceback
import time
import requests
import json
import os
import platform
import datetime

# Check if LM Studio is available
LMSTUDIO_AVAILABLE = True
try:
    # Try to load config.json for API settings
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            LMSTUDIO_API_URL = config.get('lmstudio_api_url', 'http://localhost:1234/v1')
    else:
        LMSTUDIO_API_URL = 'http://localhost:1234/v1'
except Exception as e:
    print(f"Error loading config: {e}")
    LMSTUDIO_API_URL = 'http://localhost:1234/v1'

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
            if model_index < len(self.available_models):
                # Get the model ID from the available models list
                model_id = self.available_models[model_index].get('id', '')
                if model_id:
                    # Store the model ID
                    self.current_model = model_id
                    print(f"Set current model to: {model_id}")
                    return True
                else:
                    print(f"Error: Model at index {model_index} has no ID")
                    return False
            else:
                print(f"Error: Invalid model index {model_index}, only {len(self.available_models)} models available")
                return False
        except Exception as e:
            print(f"Error setting model: {e}")
            traceback.print_exc()
            return False
    
    def get_response(self, prompt):
        """Get a response from the current model"""
        if not self.current_model:
            return "Error: No model loaded. Please select a model."
        
        try:
            print(f"Using model: {self.current_model}")
            
            # Create a chat completion request
            payload = {
                "model": self.current_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": -1
            }
            
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
                error_msg = f"Error: API returned status code {response.status_code}"
                print(f"{error_msg}, response: {response.text}")
                return error_msg
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
            payload = {
                "model": self.current_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": -1,
                "stream": True
            }
            
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
            # Check if the tool ID exists in pending tool calls
            if tool_id in self.pending_tool_calls:
                # Get the tool info
                tool_info = self.pending_tool_calls[tool_id]
                
                # Update the tool info with the result
                tool_info["result"] = result
                tool_info["status"] = "completed"
                
                # Create a new message for the tool result
                tool_message = {
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_id
                }
                
                # Add the tool message to the conversation
                if hasattr(self, 'current_chat'):
                    self.current_chat.append(tool_message)
                
                # Make a new API request to get the next response
                if hasattr(self, 'current_model') and self.current_model:
                    # Create a chat completion request
                    payload = {
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
                        "tool_choice": "auto"
                    }
                    
                    # Debug: Print the request payload
                    print(f"DEBUG - Tool Result API Request: {json.dumps(payload, indent=2)}")
                    
                    response = requests.post(
                        f"{LMSTUDIO_API_URL}/chat/completions", 
                        json=payload
                    )
                    
                    if response.status_code != 200:
                        print(f"Error: API returned status code {response.status_code}, response: {response.text}")
                        return False
                    
                    result = response.json()
                    # Debug: Print the response
                    print(f"DEBUG - Tool Result API Response: {json.dumps(result, indent=2)}")
                    
                    # Check if the response contains tool calls
                    if "choices" in result and len(result["choices"]) > 0:
                        assistant_message = result["choices"][0]["message"]
                        
                        # Add the assistant message to the conversation
                        if hasattr(self, 'current_chat'):
                            self.current_chat.append(assistant_message)
                        
                        # Import GTK libraries
                        from gi.repository import GLib, Gtk
                        
                        # Process the response based on whether it contains tool calls or not
                        if "tool_calls" in assistant_message:
                            # Process tool calls
                            self._process_tool_calls_response(assistant_message)
                        else:
                            # Process regular text response
                            self._process_text_response(assistant_message)
                        
                        return True
                    else:
                        print("Error: No choices in API response")
                        return False
                else:
                    print(f"Error: No current model set")
                    return False
            else:
                print(f"Error: Tool ID {tool_id} not found in pending tool calls")
                return False
        except Exception as e:
            error_msg = f"Error sending tool result: {e}"
            print(error_msg)
            traceback.print_exc()
            return False
    
    def _process_tool_calls_response(self, assistant_message):
        """Process a response that contains tool calls"""
        from gi.repository import GLib, Gtk
        
        # Extract tool calls
        tool_calls = assistant_message["tool_calls"]
        
        # Track unique commands to avoid duplicates
        unique_commands = {}  # Use dict to map command -> first tool_id
        
        # First pass: identify unique commands
        for tool_call in tool_calls:
            if tool_call["function"]["name"] == "terminal_execute":
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                    command = arguments.get("command", "")
                    if command and command not in unique_commands:
                        unique_commands[command] = tool_call["id"]
                except Exception as e:
                    print(f"Error parsing tool call arguments: {e}")
        
        # If we have duplicate commands, log them
        if len(unique_commands) < len(tool_calls):
            print(f"Found {len(tool_calls)} tool calls but only {len(unique_commands)} unique commands")
        
        # Store only the unique tool calls
        for command, tool_id in unique_commands.items():
            # Find the tool call with this ID
            for tool_call in tool_calls:
                if tool_call["id"] == tool_id:
                    # Store the pending tool call
                    self.pending_tool_calls[tool_id] = {
                        "command": command,
                        "status": "pending",
                        "id": tool_id,
                        "function_name": tool_call["function"]["name"]
                    }
                    break
        
        # Store the first command and tool ID for use in the nested function
        first_command = None
        first_tool_id = None
        if unique_commands:
            first_command = list(unique_commands.keys())[0]
            first_tool_id = unique_commands[first_command]
        
        def create_new_response_row():
            # Find all windows
            windows = Gtk.Window.list_toplevels()
            
            for window in windows:
                # Check if it's our application window
                if hasattr(window, 'command_rows'):
                    print(f"Found {len(windows)} top-level windows")
                    
                    # Create a new command row
                    from command_row import CommandRow
                    new_row = CommandRow()
                    
                    # Check if the window has the correct container attribute
                    if hasattr(window, 'command_container'):
                        window.command_container.append(new_row)
                        window.command_rows.append(new_row)
                        print(f"Added new row to command_container")
                    else:
                        print("Error: Window has no command_container attribute")
                        return
                    
                    # Set the suggested command if we have one
                    if first_command and first_tool_id:
                        # Set the suggested command
                        new_row.set_suggested_command(first_command)
                        new_row._command_id = first_tool_id
                        new_row.pending_command_id = first_tool_id
                        
                        # Store a reference to the command row for later use
                        self._current_command_row = new_row
                    
                    # Force the window to redraw
                    window.queue_draw()
                    
                    # Scroll to the bottom
                    if hasattr(window, '_scroll_to_bottom'):
                        GLib.idle_add(window._scroll_to_bottom)
                    
                    break
        
        # Create a new response row
        GLib.idle_add(create_new_response_row)
    
    def _process_text_response(self, assistant_message):
        """Process a response that contains only text content"""
        from gi.repository import GLib, Gtk
        
        # Extract the content
        content = assistant_message.get('content', '')
        
        def create_new_response_row():
            # Find all windows
            windows = Gtk.Window.list_toplevels()
            
            for window in windows:
                # Check if it's our application window
                if hasattr(window, 'command_rows'):
                    # Create a new command row
                    from command_row import CommandRow
                    new_row = CommandRow()
                    
                    # Check if the window has the correct container attribute
                    if hasattr(window, 'command_container'):
                        window.command_container.append(new_row)
                        window.command_rows.append(new_row)
                        print(f"Added new row to command_container")
                    else:
                        print("Error: Window has no command_container attribute")
                        return
                    
                    # Set the AI response
                    new_row.set_ai_response(content)
                    
                    # Force the window to redraw
                    window.queue_draw()
                    
                    # Scroll to the bottom
                    if hasattr(window, '_scroll_to_bottom'):
                        GLib.idle_add(window._scroll_to_bottom)
                    
                    break
        
        # Create a new response row
        GLib.idle_add(create_new_response_row)
    
    def _update_streaming_ui(self, content_delta):
        """Update the UI with a new chunk of streaming content"""
        if hasattr(self, '_current_command_row'):
            self._current_command_row.update_streaming_ai_response(content_delta)
    
    def _finish_streaming_ui(self):
        """Finalize the streaming UI by removing the spinner"""
        if hasattr(self, '_current_command_row'):
            self._current_command_row.finish_streaming_ai_response()
    
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

            # system prompt
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
                                    for tool_call_delta in delta["tool_calls"]:
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
                        except json.JSONDecodeError:
                            print(f"Error parsing JSON from chunk: {json_str}")
                        except Exception as e:
                            print(f"Error processing chunk: {e}")
                            traceback.print_exc()
            
            # Process any tool calls after streaming is complete
            tool_calls_data = list(accumulated_tool_calls.values())
            if tool_calls_data:
                # Track unique commands to avoid duplicates
                unique_commands = {}  # Use dict to map command -> first tool_id
                
                # First pass: identify unique commands
                for tool_call in tool_calls_data:
                    if tool_call['function']['name'] == 'terminal_execute':
                        try:
                            arguments_str = tool_call['function']['arguments']
                            if arguments_str and arguments_str.strip():
                                arguments = json.loads(arguments_str)
                                command = arguments.get('command', '')
                                if command and command not in unique_commands:
                                    unique_commands[command] = tool_call['id']
                        except Exception as e:
                            print(f"Error parsing tool call arguments: {e}")
                
                # If we have duplicate commands, log them
                if len(unique_commands) < len(tool_calls_data):
                    print(f"Found {len(tool_calls_data)} tool calls but only {len(unique_commands)} unique commands")
                    print(f"Unique commands: {list(unique_commands.keys())}")
                
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
                for tool_call in tool_calls_data:
                    try:
                        arguments_str = tool_call['function']['arguments']
                        arguments = json.loads(arguments_str) if arguments_str else {}
                        command = arguments.get('command', '')
                        
                        # Only include this tool call if it's the first one with this command
                        if command and unique_commands.get(command) == tool_call['id']:
                            filtered_tool_calls.append(tool_call)
                    except Exception:
                        # If we can't parse the arguments, skip this tool call
                        continue
                
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
        except Exception as e:
            error_msg = f"Error running streaming agent: {e}"
            if on_complete:
                on_complete(error_msg)
            traceback.print_exc()
            return error_msg