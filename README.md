# lmTerm

lmTerm is a GTK-based terminal application that integrates with LM Studio to provide completely local, private, and open source AI-assisted command-line interactions.

## Features

- AI-assisted command execution
- Direct command execution mode
- Command history with easy navigation
- Integration with LM Studio's local LLM models
- Tool execution with human-in-the-loop confirmation
- Markdown formatting support for AI responses

[Video_2025-03-22_00-06-07.webm](https://github.com/user-attachments/assets/521a8dcb-78e5-42b1-9135-34d4667d7bb5)
![Screenshot from 2025-03-21 23-46-27](https://github.com/user-attachments/assets/006e0660-e45b-41c2-9525-a7030e37a1ad)
![Screenshot from 2025-03-21 23-44-51](https://github.com/user-attachments/assets/367ac4ab-345b-4876-ab95-60bfcec1a457)

## Requirements

- Python 3.8+
- GTK 4.0
- Adwaita (Adw) 1
- LM Studio running locally

## Installation

1. Clone the repository:
   ```git clone https://github.com/macuseri686/lmTerm.git```
   ```cd lmTerm```

2. Install dependencies:
   ```pip install -r requirements.txt```

3. Make sure LM Studio is running with the API server enabled (typically on port 1234)

4. Run the application:
   ```python lmterm.py```

## Configuration

lmTerm looks for a `config.json` file in the application directory with the following structure:

```
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

## License

[MIT License](LICENSE)
