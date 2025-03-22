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
            
            response = requests.post(
                f"{LMSTUDIO_API_URL}/chat/completions", 
                json=payload
            )
            
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
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
            system_info = f"""
System Information:
- OS: {platform.system()} {platform.release()} ({platform.version()})
- Python: {platform.python_version()}
- CPU: {platform.processor()} ({cpu_cores})
- Memory: {memory_info}
- Current Date/Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            # systtem prompt
            system_prompt = """
You are an AI assistant that lives in the terminal on a linux system. 
You can write message responses to the user, and you can execute commands using the tools provided to you. 
You can also use markdown to format your responses. 

Your role is to help the user with their high level tasks by executing commands and writing responses back to the user.
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
                        msg["content"] = system_info
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
                "tools": api_tools
            }
            
            response = requests.post(
                f"{LMSTUDIO_API_URL}/chat/completions", 
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"Error: API returned status code {response.status_code}"
                if on_message:
                    on_message(error_msg)
                return error_msg
            
            result = response.json()
            
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
                
                # Find the window and command row to update the UI
                from gi.repository import GLib, Gtk
                from command_row import CommandRow
                
                def start_response_ui():
                    # Find all windows
                    windows = Gtk.Window.list_toplevels()
                    print(f"Found {len(windows)} top-level windows")
                    
                    for window in windows:
                        # Check if it's our application window
                        if hasattr(window, 'command_rows'):
                            # Find the most recent command row
                            if window.command_rows:
                                latest_row = window.command_rows[-1]
                                print(f"Found latest command row: {latest_row}")
                                
                                # Start a new AI response with spinner
                                new_box, new_label = latest_row.start_new_ai_response()
                                
                                # Store the row for later updates
                                self._current_command_row = latest_row
                                
                                # Force the window to redraw
                                window.queue_draw()
                                
                                # Ensure the expander is expanded to show the new content
                                latest_row.set_expanded(True)
                                
                                break
                
                # Start the UI response with a spinner
                GLib.idle_add(start_response_ui)
                
                # Make the API request to continue the conversation with streaming
                payload = {
                    "model": self.current_model,
                    "messages": self.current_chat,
                    "stream": True  # Enable streaming
                }
                
                print(f"Sending tool result for model: {self.current_model}")
                
                # Start a streaming request
                response = requests.post(
                    f"{LMSTUDIO_API_URL}/chat/completions", 
                    json=payload,
                    stream=True  # Enable streaming in the request
                )
                
                if response.status_code != 200:
                    print(f"Error: API returned status code {response.status_code}")
                    print(f"Response: {response.text}")
                    return False
                
                # Process the streaming response
                accumulated_content = ""
                
                # Start a thread to process the streaming response
                def process_stream():
                    nonlocal accumulated_content
                    
                    try:
                        for line in response.iter_lines():
                            if line:
                                # Remove the "data: " prefix
                                if line.startswith(b'data: '):
                                    line = line[6:]
                                
                                # Skip "[DONE]" message
                                if line == b'[DONE]':
                                    continue
                                
                                try:
                                    # Parse the JSON chunk
                                    chunk = json.loads(line)
                                    
                                    # Extract the content delta
                                    if 'choices' in chunk and len(chunk['choices']) > 0:
                                        delta = chunk['choices'][0].get('delta', {})
                                        content_delta = delta.get('content', '')
                                        
                                        if content_delta:
                                            # Accumulate the content
                                            accumulated_content += content_delta
                                            
                                            # Update the UI with the new chunk
                                            GLib.idle_add(self._update_streaming_ui, content_delta)
                                except json.JSONDecodeError:
                                    print(f"Error parsing JSON from chunk: {line}")
                                    continue
                        
                        # Add the complete message to the conversation
                        self.current_chat.append({
                            "role": "assistant",
                            "content": accumulated_content
                        })
                        
                        # Finalize the UI
                        GLib.idle_add(self._finish_streaming_ui)
                        
                    except Exception as e:
                        print(f"Error processing stream: {e}")
                        traceback.print_exc()
                        GLib.idle_add(self._finish_streaming_ui)
                
                # Start the streaming thread
                import threading
                threading.Thread(target=process_stream).start()
                
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