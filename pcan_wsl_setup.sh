#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e 

echo "1. Installing WSL CAN tools and kernel build dependencies..."
sudo apt-get update
sudo apt-get install -y build-essential flex bison dwarves libssl-dev libelf-dev bc git wget linux-tools-virtual hwdata can-utils

echo "2. Installing usbipd-win on Windows host..."
# WSL can natively execute Windows binaries. We use winget.exe to install the host software.
# Note: This may open a Windows User Account Control (UAC) prompt.
winget.exe install --interactive --exact dorssel.usbipd-win || echo "usbipd-win installed or skipped."

echo "3. Cloning Microsoft WSL2 Linux Kernel (shallow clone for speed)..."
DIR_NAME="wsl-kernel-pcan"
rm -rf $DIR_NAME
git clone --depth=1 https://github.com/microsoft/WSL2-Linux-Kernel.git $DIR_NAME
cd $DIR_NAME

echo "4. Extracting current running kernel configuration..."
zcat /proc/config.gz > .config

echo "5. Injecting CAN and PEAK USB drivers into config..."
./scripts/config --enable CONFIG_CAN
./scripts/config --enable CONFIG_CAN_VCAN
./scripts/config --enable CONFIG_CAN_PEAK_USB
make olddefconfig

echo "6. Compiling the kernel (this will take several minutes)..."
make -j$(nproc)

echo "7. Locating Windows user profile..."
WIN_USER=$(cmd.exe /c "echo %USERNAME%" 2>/dev/null | tr -d '\r')
WIN_HOME="/mnt/c/Users/$WIN_USER"
DEST_PATH="$WIN_HOME/bzImage-pcan"

echo "8. Copying the compiled kernel to Windows..."
cp arch/x86/boot/bzImage "$DEST_PATH"

echo "==================================================================="
echo "COMPILATION COMPLETE."
echo "Your new kernel is located at: C:\Users\\$WIN_USER\bzImage-pcan"
echo "==================================================================="
echo ""
echo "FINAL STEP: Add or update your C:\Users\\$WIN_USER\.wslconfig file in Windows with these lines:"
echo ""
echo "[wsl2]"
echo "kernel=C:\\\\Users\\\\$WIN_USER\\\\bzImage-pcan"
echo ""
echo "Then, open a standard Windows PowerShell and restart WSL:"
echo "wsl --shutdown"
