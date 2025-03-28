#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define installation paths
APP_NAME="lmterm"
INSTALL_DIR="/usr/local/share/$APP_NAME"
BIN_DIR="/usr/local/bin"
DESKTOP_DIR="/usr/local/share/applications"
ICON_NAME="com.lmstudio.lmterm" # Use the application ID for the icon name
# Assuming SVG icon, adjust if using PNG (e.g., /usr/local/share/icons/hicolor/256x256/apps)
ICON_SOURCE="lmTerm.png"
ICON_DEST_DIR="/usr/local/share/icons/hicolor/256x256/apps"

# Check for root privileges
if [ "$(id -u)" -ne 0 ]; then
   echo "This script must be run as root. Please use sudo." >&2
   exit 1
fi

# Determine script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check for required files in the script directory
if [ ! -f "$SCRIPT_DIR/lmterm.py" ] || [ ! -f "$SCRIPT_DIR/window.py" ] || [ ! -f "$SCRIPT_DIR/style.css" ] || [ ! -f "$SCRIPT_DIR/$ICON_SOURCE" ]; then
    echo "Error: Missing required files (lmterm.py, window.py, style.css, $ICON_SOURCE) in the script directory." >&2
    exit 1
fi

echo "Starting installation of $APP_NAME..."

# Create directories
echo "Creating directories..."
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$DESKTOP_DIR"
mkdir -p "$ICON_DEST_DIR"

# Copy application files
echo "Copying application files to $INSTALL_DIR..."
cp "$SCRIPT_DIR"/*.py "$INSTALL_DIR/"
cp "$SCRIPT_DIR"/*.css "$INSTALL_DIR/"
cp "$SCRIPT_DIR"/*.png "$INSTALL_DIR/" 2>/dev/null || true # Copy PNG files, ignore errors if none exist
cp "$SCRIPT_DIR"/*.json "$INSTALL_DIR/" 2>/dev/null || true # Copy JSON files, ignore errors if none exist

# Create a wrapper script in BIN_DIR to run the application
# This avoids issues with Python finding modules and data files
echo "Creating executable wrapper in $BIN_DIR/$APP_NAME..."
cat << EOF > "$BIN_DIR/$APP_NAME"
#!/bin/bash
# Wrapper script to run lmterm from its installation directory
PYTHON_EXEC=\$(command -v python3 || command -v python)
if [ -z "\$PYTHON_EXEC" ]; then
    echo "Error: Python 3 interpreter not found." >&2
    exit 1
fi
cd "$INSTALL_DIR"
exec "\$PYTHON_EXEC" lmterm.py "\$@"
EOF

# Make the wrapper executable
chmod +x "$BIN_DIR/$APP_NAME"

# Copy icon
echo "Installing icon to $ICON_DEST_DIR..."
cp "$SCRIPT_DIR/$ICON_SOURCE" "$ICON_DEST_DIR/$ICON_NAME.png"

# Create .desktop file
echo "Creating .desktop file in $DESKTOP_DIR..."
cat << EOF > "$DESKTOP_DIR/$ICON_NAME.desktop"
[Desktop Entry]
Name=LM Terminal
Comment=A simple terminal interface for LM Studio
Exec=$APP_NAME
Icon=$ICON_NAME
Type=Application
Categories=Utility;TerminalEmulator;Development;
StartupNotify=true
Keywords=lmstudio;llm;ai;chat;terminal;
EOF

# Update caches
echo "Updating desktop database and icon cache..."
update-desktop-database "$DESKTOP_DIR" || echo "Warning: update-desktop-database failed. Desktop entry might not appear immediately."
gtk-update-icon-cache "/usr/local/share/icons/hicolor" || echo "Warning: gtk-update-icon-cache failed. Icon might not appear immediately."

echo "Installation complete!"
echo "You can now run '$APP_NAME' from your terminal or find 'LM Terminal' in your application menu."

exit 0 