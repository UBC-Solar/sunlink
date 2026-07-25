# UBC Solar's Sunlink Brief Overview

Welcome to UBC Solar's telemetry aggregation, storage, and visualization system, Sunlink. This guide will cover the **most important aspects** of running the system. Please see the `docs` folder for more detailed information. *For example, There may be links in this guide referring to information inside a doc within the `docs` folder*.

## Need Help Running Sunlink?
### SETUP Commands
**Recommended Everytime you Open Sunlink**
```bash
git pull
sudo docker compose restart
```
**MUST Run Once in Sunlink directory**
```bash
source  environment/bin/activate
```
This will activate the virtual environment that has the Python packages to run our system installed.

### Cellular Parser (Detailed Instructions)
For full setup and usage details of the cellular parser container, see the Sunlite README:  
https://github.com/UBC-Solar/sunlite/blob/main/src/grpc_cellular/README.md

### Cellular Startup
If it is your first time running Cellular, we need sshpass to bypass the password on the rpi. To do this run:

`sudo apt-get install sshpass`

Then we need to confirm that we can ssh into the RPI so run:

`ssh sunlite@100.88.33.33`

password: `solarisbest123`

If that works, then write `exit` in the terminal and you can proceed with the following bash command.

| Command | Description |
| --- | --- |
| `bash run_cellular.sh` | Simplifies the cellular parser startup to a single bash command by connecting to the Pi, syncing the Influx configuration from the local Sunlink environment, and launching the parser. |

### CAN or Radio Setup
Depending on what you are using see **CAN Setup** or **Radio Setup** sections below for how to set up CAN or Radio. Need to do this before running sunlink commands!

### RUNNING SUNLINK Commands
| **Command**                                                | **Description**                                                                                                                                                                                                                    |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `./link_telemetry.py -p /dev/ttyUSB0 -b 921600 --prod --batch-size 2000 --local`     | **Useful at COMP!**: (Before reading, see [Sunlink Radio Pre-requistes](#can-setup-windows)). Uses radio (serial port) and does all parsing locally. Write to the "CAN_prod" bucket on InfluxDB.                                                                                             |
| `./link_telemetry.py -o --prod --batch-size 4000 --local`     | **Useful for BMS**: (Before reading, see [Sunlink CAN Pre-requistes](#can-setup-on-native-linux)). Uses CAN (-o) and does parsing locally instead of a docker container for increased speed. Set the batch size to 2x the typical data rate in seconds. To find the data rate, look at the yellow output when you run `./link_telemetry.py` and ballpark the number of messages processed every second. Writes to CAN_prod.                                                                                                 |        
| `./link_telemetry.py -r can --debug -f 200 --batch-size 400 --local`     | **Useful for Testing**: Uses random message generation and does all parsing locally. Write to the "CAN_test" bucket on InfluxDB.     

### [Data/Memorator UPLOAD](./tools/DATA_UPLOAD_SOP.md)

### Common Issues
| **Problem**                                                | **Solution**                                                                                                                                                                                                                    |
| ---------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RTNETLINK answers: Device or resource busy`    | Restart CAN peripheral by unplugging the PCAN and plugging it back in. [Then run the commands here.](#can-setup-on-native-linux).                                                                                             |
| `Cannot find device "can0"`    | [Follow this](https://github.com/UBC-Solar/sunlink/blob/main/docs/DETAILED_OVERVIEW.md#how-to-install-linux-pcan-drivers)                                                                                             |

### Connecting via TailScale network
If someone is running telemetry, you are able to leech off of there influxdb/grafana instance by connecting to their tailscale network. If you are on Mac/Linux, Tailscale should have been set up when you installed Sunlink. If you are on windows or did not install Tailscale do:
1. Download Tailscale [here](https://tailscale.com/download/windows) and run the exe file:
2. Navigate to `Program Files/Tailscale` in terminal
3. Run `.\tailscale.exe up --authkey=tskey-auth-<authkeyhere>` - Ask your lead for the authkey


#### Running Grafana/Influx with Tailscale IP:
```
tailscale status | grep "<name of laptop>"
```
For example this returns the tailscale IP:
```
tailscale status | grep "greg"

100.101.183.2     gregorybian-thinkpad-e16-gen-3
```
Then to access grafana use :3000 and influx :8080 at the end of the tailscale IP, i.e.:
`100.101.183.2:3000`

You will be prompted to enter a username and password, by default it is:
```
Username: admin
Password: new_password
```
### CAN Setup on Native Linux
#### HW Side setup
Make absolutely sure you have:
* **5V** for CAN
* **120 ohm** termination on **at least** one side of the bus. For best results terminate both sides but in practice, during benchtop testing we only need one 120 ohm to reduce signal reflection sufficiently. *Note: [PCAN's do not come with termination resistors](https://forum.peak-system.com/viewtopic.php?t=5727) so use a CAN splitter and put on the jumper caps for termination*. 


#### Commands
Organized by command then explanation.
```bash
sudo ip link set can0 type can bitrate 500000
sudo ip link set can0 up
```
**Optionally to dump/print out CAN messages**
```bash
candump -td -H -x -c can0
```
#### Explanation
Your native Linux computer probably already has drivers for CAN installed, **but you need to setup the Peak-Systems USB-CAN reader on the computer**. 
1. First command sets up the virtual CAN peripheral on your computer. the `type can` tells the software that this is a CAN device. The `bitrate 500000` sets the bitrate to 500kHz, which **is what Solar standardly uses**.
2. The second command sets the virtual CAN peripheral to be "up" or active. **At this point you should see the PCAN blinking slowly. If CAN is being sent then the LED blinks fast**
3. The third command is optional and will print out the CAN messages that are being sent to the computer. This is useful for debugging and testing purposes. The `-td` flag tells the software to print out the ***t**ime **d**elta*, `-H` tells it print hardware (PCAN) timestamps instead of your computer's timestamp format, `-x` tells it print extra info like Rx/Tx (Was the CAN message going into your computer or out), and `-c` is the basic color mode level (you see a nice blue when you dump).

### CAN Setup Windows
Super easy, just download the [driver setup application Peak-Systems provides for windows](https://www.peak-system.com/quick/DrvSetup).

### Radio Setup on Native Linux
Already works out of the box. Use the `/dev/ttyUSB0` port. 

### Radio Setup on WSL
#### Commands
**Run as Administrator** Windows PowerShell. *Note: replace <BUSID> with the bus ID of the of **USB Serial Converter Device**
```powershell
winget install --interactive --exact dorssel.usbipd-win
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```
Now open WSL and run the following commands:
```bash
sudo usermod -a -G tty $USER
sudo usermod -a -G dialout $USER
```
#### Powershell Commands Explanation
1. The first command installs the USBIPD-WIN project which is required to connect USB devices to WSL2.
2. The second command lists all the connected USB devices. Look for the **Serial Converter Device**.
3. The third command binds a specific USB device. For the radio module's USB look for something that says **serial** in it.
4. The fourth command attaches the USB device to WSL2. This is required to access the USB device from WSL2.

#### WSL2 Commands Explanation
1. The first command adds your WSL2 user to the `tty` group. This is required to access the serial port.
2. The second command adds your WSL2 user to the `dialout` group. This is required to access the serial port.
3. The third command restarts WSL2. This is required to apply the changes made in the previous two commands.

#### Relevant Link
> https://learn.microsoft.com/en-us/windows/wsl/connect-usb

## How to Install Sunlink?
1. **Download the Script**

   Download the `setup.sh` script into the directory where you want to set up the telemetry cluster:

   ```sh
   curl -O https://raw.githubusercontent.com/UBC-Solar/sunlink/main/setup.sh
   ```
**IF MacOS!!**
   ```sh
   curl -O https://raw.githubusercontent.com/UBC-Solar/sunlink/main/MacOS_setup.sh
   ```
2. **Add Execute/Run Permsissions**

   Make the script executable:

   ```sh
   chmod +x setup.sh
   ```
3. **Run the Script**
    Run the script with the following command:
    
    ```sh
    ./setup.sh
    ```
Now just follow the instructions on screen.     
