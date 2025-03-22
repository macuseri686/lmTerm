import subprocess
import shlex
import traceback
import gi
import threading
import os
import time

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

# Global flag to control command execution
REQUIRE_CONFIRMATION = True
PENDING_COMMANDS = {}

def execute_command(command, timeout=30, require_confirmation=None, parent_widget=None):
    """Execute a terminal command and return the output"""
    print(f"DEBUG - execute_command called with: {command}")
    traceback.print_stack()  # This will show us the call stack
    
    # Check if confirmation is required
    if require_confirmation is None:
        require_confirmation = REQUIRE_CONFIRMATION
    
    if require_confirmation:
        # Generate a unique ID for this command
        command_id = str(hash(command + str(time.time())))
        
        # Store the command for later execution
        PENDING_COMMANDS[command_id] = {
            "command": command,
            "timeout": timeout,
            "status": "pending"
        }
        
        # Return a placeholder message
        return f"COMMAND_PENDING:{command_id}:Command '{command}' requires user confirmation."
    
    # Check if the command is a cd command
    if command.strip().startswith("cd "):
        return handle_cd_command(command)
    
    # Check if the command needs sudo
    if command.strip().startswith("sudo "):
        return execute_sudo_command(command, timeout, parent_widget)
    
    # If confirmation is not required or has been given, execute the command
    try:
        # Run the command and capture output
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=timeout
        )
        
        # Combine stdout and stderr
        output = result.stdout
        
        if result.stderr:
            if output:
                output += "\n" + result.stderr
            else:
                output = result.stderr
        
        # If no output, indicate success
        if not output:
            output = f"Command executed successfully (exit code: {result.returncode})"
        
        return output
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def execute_sudo_command(command, timeout=30, parent_widget=None):
    """Execute a sudo command with password prompt"""
    # Create a dialog to ask for the sudo password
    password = None
    password_result = []  # Use a list to store the result across threads
    
    def show_password_dialog():
        dialog = Adw.MessageDialog.new(parent_widget.get_root() if parent_widget else None,
                                      "Sudo Password Required",
                                      f"The command '{command}' requires sudo privileges.")
        
        # Add password entry
        password_entry = Gtk.PasswordEntry()
        password_entry.set_show_peek_icon(True)
        password_entry.set_margin_top(10)
        password_entry.set_margin_bottom(10)
        password_entry.set_margin_start(10)
        password_entry.set_margin_end(10)
        
        # Add the password entry to the dialog
        dialog.set_extra_child(password_entry)
        
        # Add buttons
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "OK")
        dialog.set_default_response("ok")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        
        # Connect to the response signal
        def on_response(dialog, response):
            if response == "ok":
                password_result.append(password_entry.get_text())
            dialog.destroy()
        
        dialog.connect("response", on_response)
        
        # Show the dialog
        dialog.present()
    
    # Show the dialog in the main thread
    GLib.idle_add(show_password_dialog)
    
    # Wait for the password to be entered
    max_wait = 60  # Maximum wait time in seconds
    wait_interval = 0.1
    waited = 0
    
    while not password_result and waited < max_wait:
        time.sleep(wait_interval)
        waited += wait_interval
    
    if not password_result:
        return "Password entry timed out or was cancelled."
    
    password = password_result[0]
    
    # Execute the command with the provided password
    try:
        # Remove 'sudo' from the command as we'll use it with sudo -S
        cmd = command.replace("sudo ", "", 1)
        
        # Use sudo -S to read password from stdin
        process = subprocess.Popen(
            ["sudo", "-S"] + shlex.split(cmd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send the password to stdin
        stdout, stderr = process.communicate(input=password + "\n", timeout=timeout)
        
        # Combine stdout and stderr
        output = stdout
        
        if stderr:
            # Filter out the password prompt message
            filtered_stderr = "\n".join([line for line in stderr.split("\n") 
                                        if not line.startswith("[sudo] password for")])
            if filtered_stderr:
                if output:
                    output += "\n" + filtered_stderr
                else:
                    output = filtered_stderr
        
        # If no output, indicate success
        if not output:
            output = f"Command executed successfully (exit code: {process.returncode})"
        
        return output
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def confirm_command(command_id, parent_widget=None):
    """Execute a command that was previously deferred"""
    if command_id in PENDING_COMMANDS:
        command_info = PENDING_COMMANDS[command_id]
        command = command_info["command"]
        timeout = command_info["timeout"]
        
        # Mark as executing
        command_info["status"] = "executing"
        
        # Execute the command with confirmation bypassed
        result = execute_command(command, timeout, require_confirmation=False, parent_widget=parent_widget)
        
        # Update with result
        command_info["result"] = result
        command_info["status"] = "completed"
        
        return result
    else:
        return "Error: Command not found"

def cancel_command(command_id):
    """Cancel a command that was previously deferred"""
    if command_id in PENDING_COMMANDS:
        # Mark as canceled
        PENDING_COMMANDS[command_id]["status"] = "canceled"
        return f"Command canceled by user."
    else:
        return "Error: Command not found"

def handle_cd_command(command):
    """Handle the cd command by changing the current working directory"""
    # Extract the target directory
    target_dir = command.strip()[3:].strip()
    
    try:
        # Change the directory
        os.chdir(target_dir)
        
        # Return the new working directory
        return f"Changed directory to: {os.getcwd()}"
    except Exception as e:
        return f"Error changing directory: {str(e)}" 