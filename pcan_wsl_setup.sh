#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "1. Installing WSL CAN tools..."
sudo apt-get update
sudo apt-get install -y linux-tools-virtual hwdata can-utils wget

echo "2. Installing usbipd-win on Windows host..."
# WSL can natively execute Windows binaries. We use winget.exe to install the host software.
# Note: This may open a Windows User Account Control (UAC) prompt.
winget.exe install --interactive --exact dorssel.usbipd-win || echo "usbipd-win installed or skipped."

echo "3. Locating Windows user profile..."
WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
WIN_HOME="/mnt/c/Users/$WIN_USER"
DEST_PATH="$WIN_HOME/bzImage-pcan"

echo "4. Downloading pre-compiled kernel from Google Drive..."
# We extract the file ID from the shareable link to force a direct download
wget --no-check-certificate "https://docs.google.com/uc?export=download&id=1ubS1mpVaoXLuAkjDefm8T7TJQKOHsK2h" -O "$DEST_PATH"

echo "==================================================================="
echo "SETUP COMPLETE."
echo "The pre-compiled kernel is located at: C:\Users\\$WIN_USER\bzImage-pcan"
echo "==================================================================="
echo ""
echo "FINAL STEP: You must create a configuration file in Windows so WSL knows to use this kernel."
echo "1. Open Notepad in Windows."
echo "2. Paste the following two lines:"
echo ""
echo "[wsl2]"
echo "kernel=C:\\\\Users\\\\$WIN_USER\\\\bzImage-pcan"
echo ""
echo "3. Save the file exactly as: C:\Users\\$WIN_USER\.wslconfig"
echo ""
echo "Then, open an Administrator Windows PowerShell and restart WSL:"
echo "wsl --shutdown"

