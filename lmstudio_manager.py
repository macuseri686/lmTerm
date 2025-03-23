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
        """Send a tool result back to the AI after user confirmation"""
        if not self.current_model:
            print("Error: No model loaded. Please select a model.")
            return False
        
        try:
            # Check if this tool ID is in our pending tool calls
            if tool_id in self.pending_tool_calls:
                tool_info = self.pending_tool_calls[tool_id]
                
                # Update the tool info with the result
                tool_info["result"] = result
                tool_info["status"] = "completed"
                
                # Add the tool result to the conversation
                self.current_chat.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tool_id
                })
                
                # Make a new API request to get the next response
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
                    print(f"Error: API returned status code {response.status_code}")
                    print(f"Response: {response.text}")
                    return False
                
                result = response.json()
                # Debug: Print the response
                print(f"DEBUG - Tool Result API Response: {json.dumps(result, indent=2)}")
                
                # Process the response
                assistant_message = result['choices'][0]['message']
                
                # Check if the response includes tool calls
                if 'tool_calls' in assistant_message:
                    # Store the tool calls for later execution
                    tool_calls = assistant_message['tool_calls']
                    for tool_call in tool_calls:
                        new_tool_id = tool_call['id']
                        function_name = tool_call['function']['name']
                        arguments = json.loads(tool_call['function']['arguments'])
                        
                        # Store the pending tool call
                        self.pending_tool_calls[new_tool_id] = {
                            "command": arguments.get('command', ''),
                            "status": "pending",
                            "id": new_tool_id,
                            "function_name": function_name
                        }
                    
                    # Add the assistant message to the conversation
                    self.current_chat.append({
                        "role": "assistant",
                        "tool_calls": tool_calls
                    })
                    
                    # Find the window to create a new command row
                    from gi.repository import GLib, Gtk
                    
                    def create_new_command_row():
                        # Find all windows
                        windows = Gtk.Window.list_toplevels()
                        print(f"Found {len(windows)} top-level windows")
                        
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
                                
                                # Set the AI response first (if any content is provided)
                                if 'content' in assistant_message and assistant_message['content']:
                                    new_row.set_ai_response(assistant_message['content'])
                                
                                # Set the suggested command from the first tool call
                                if tool_calls and len(tool_calls) > 0:
                                    tool_call = tool_calls[0]
                                    arguments = json.loads(tool_call['function']['arguments'])
                                    command = arguments.get('command', '')
                                    new_row.set_suggested_command(command)
                                    new_row._command_id = tool_call['id']
                                    new_row.pending_command_id = tool_call['id']
                                
                                # Force the window to redraw
                                window.queue_draw()
                                
                                # Scroll to the bottom
                                if hasattr(window, '_scroll_to_bottom'):
                                    GLib.idle_add(window._scroll_to_bottom)
                                
                                break
                    
                    # Create a new command row for the next tool call
                    GLib.idle_add(create_new_command_row)
                    
                    return True
                else:
                    # No tool calls, just a regular response
                    content = assistant_message.get('content', '')
                    
                    # Add the assistant message to the conversation
                    self.current_chat.append({
                        "role": "assistant",
                        "content": content
                    })
                    
                    # Find the window to create a new response row
                    from gi.repository import GLib, Gtk
                    
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
                    
                    return True
            else:
                print(f"Error: Tool ID {tool_id} not found in pending tool calls")
                return False
        except Exception as e:
            print(f"Error sending tool result: {e}")
            traceback.print_exc()
            return False
    
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