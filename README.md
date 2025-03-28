# lmTerm

lmTerm is a GTK-based terminal application that integrates with LM Studio to provide completely local, private, and open source AI-assisted command-line interactions.

## Features

- AI-assisted command execution
- Direct command execution mode
- Command history with easy navigation
- Integration with LM Studio's local LLM models
- Tool execution with human-in-the-loop confirmation
- Markdown formatting support for AI responses
  
![Screenshot from 2025-03-22 18-14-26](https://github.com/user-attachments/assets/77cfd457-0d04-4095-a1ab-14d8e14fde3e)
![Screenshot from 2025-03-22 18-13-24](https://github.com/user-attachments/assets/5b9e3d72-83e5-4eac-907a-7e6425d3c0dd)

## Requirements

- Python 3.8+
- GTK 4.0
- Adwaita (Adw) 1.4 or higher
- LM Studio running locally
- PyGObject 3.42 or higher
- libadwaita 1.4 or higher

## Installation

### Linux Operating Systems

1. Install system dependencies:
   ```bash
   # For Ubuntu/Debian:
   sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1
   
   # For Fedora:
   sudo dnf install python3-gobject python3-gobject-gtk4 libadwaita
   ```

2. Clone the repository:
   ```bash
   git clone https://github.com/macuseri686/lmTerm.git
   cd lmTerm
   ```

3. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

4. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

5. Make sure LM Studio is running with the API server enabled (typically on port 1234)

6. Run the application:
   ```bash
   python lmterm.py
   ```

### macOS

1. Install Homebrew if you haven't already:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. Install GTK4, libadwaita, and their dependencies:
   ```bash
   brew install gtk4
   brew install libadwaita
   brew install pygobject3
   ```

3. Install Python if you haven't already:
   ```bash
   brew install python@3.11
   ```

4. Clone the repository:
   ```bash
   git clone https://github.com/macuseri686/lmTerm.git
   cd lmTerm
   ```

5. Create and activate a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

6. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

7. Download and install [LM Studio](https://lmstudio.ai) for macOS

8. Start LM Studio and enable the API server (typically on port 1234)

9. Run the application:
   ```bash
   python lmterm.py
   ```

## Configuration

lmTerm looks for a `config.json` file in the application directory with the following structure:

```json
{
  "lmstudio_api_url": "http://localhost:1234/v1"
}
```

If no configuration file is found, it defaults to `http://localhost:1234/v1`.

## Usage

### Modes

- **AI Mode**: Toggle the switch to "AI" to interact with the LLM. Type your prompt and press Enter or click "Run".
- **Command Mode**: Toggle the switch to "Command" to directly execute terminal commands.

### Model Selection

Select your preferred LLM model from the dropdown menu. Models are loaded from your running LM Studio instance.

### Command History

- Press the Up arrow key to access command history
- Navigate through history with Up/Down arrow keys
- Select a command by clicking or pressing Enter

### AI Agent

When in AI mode, the LLM can suggest commands to run. You can:
- Accept and run the suggested command
- Edit the command before running
- Cancel the command execution

## Development

The project structure:
- `lmterm.py`: Main application entry point
- `window.py`: Main application window
- `command_row.py`: UI component for command interactions
- `lmstudio_manager.py`: Interface to LM Studio API
- `terminal.py`: Terminal command execution utilities

## Troubleshooting

### Linux

1. If you get GTK-related errors:
   - Make sure you've installed all system dependencies
   - For Ubuntu/Debian: `sudo apt install --reinstall python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1`
   - For Fedora: `sudo dnf reinstall python3-gobject python3-gobject-gtk4 libadwaita`

2. If PyGObject is not found:
   - Try reinstalling it: `pip uninstall PyGObject && pip install PyGObject`
   - Make sure you're using the system Python for GTK bindings

### macOS

1. If you get GTK-related errors:
   - Make sure you've installed GTK4 and libadwaita via Homebrew
   - Try running: `brew reinstall gtk4 libadwaita pygobject3`
   - Ensure your virtual environment is using the correct Python version

2. If PyGObject is not found:
   - Try reinstalling it: `pip uninstall PyGObject && pip install PyGObject`
   - If that doesn't work, install via Homebrew: `brew install pygobject3`

3. If the application crashes on startup:
   - Check that LM Studio is running and the API server is enabled
   - Verify the port number in `config.json` matches your LM Studio settings

## License

[MIT License](LICENSE)
