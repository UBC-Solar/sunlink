# Data Upload SOP
This SOP explains:
1. **Pre-Driving Checks**
2. **Correct Data Upload Procedure** 
3. **Memorator Upload Script Maintainence**

Generally speaking these are a list of solutions to problems we had when settting up our data uploading pathway for the first time in 2024 Summer. This is extremely useful to know for those in the future working with this script.

## Pre-Driving Checks
1. Is the Memorator being powered correctly (12V)? 
2. Is the Memorator sending out RTC Timestamp CAN messages? Are these timestamps actually synced with real time or are they off by a few minutes? If its off you need to sync the time in the [Kvaser Memorator application](https://github.com/UBC-Solar/firmware_v3/tree/master/tools/t_programs/sendRTC#configuration-set-up) 
3. Does the SD Card have enough space for the driving time you are about to complete? You can expect 50Mb used per hour of driving as of [2025 CAN load](https://ubcsolar26.monday.com/boards/7524367653/pulses/9265626553/posts/4163711942). If not delete some logs (see the next section).

### Delete Logs
Sometimes you need to create space for the logs. In this case, uncomment the following 2 sections in the memorator. Look for the `""" START UNCOMMENT TO DELETE LOGS """` and the `""" END UNCOMMENT TO DELETE LOGS """` comments to find these sections. Once you uncomment them re-run the script and delete all.

## Correct Data Upload Procedure
The general upload script procedure is below:
1. `sudo usermod -aG docker $USER` -> Add your user to the docker group 
2. `newgrp docker` -> Allows docker group usage withou sudo. 
3. Plug in the SD Card from the Memorator into your computer. *You may need an SD card to USB adpater. Find these in the FW Proto box*. If you want to upload to the bay computer, then run the script on the bay computer.
4. Open `sunlink` and source your environment. Do a `git pull` as well
5. Now type in `./link_telemetry.py -u fast` in the sunlink root directory.
6. Paste and Enter in the absolute folder path with the KMF files. For example: `/media/<USERNAME>/disk/` or `/media/aarjav/disk/`
7. Look at the various logs choose which **Log Idx**'s you want to upload. Use the date the log was produced to guide you. Example entry `1 5 6 10`. 

Here are some notes regarding this process
- Look at which log indicies have start/end dates that match your **driving days**. Ex. you typically drive and then you take the SD card out of the memorator right after and upload data. So check for the logs that line up with this time.
- Read instructions and errors carefully. Go slow. As an **EMD Member** its your responsibility thta data is uploaded correctly. If you just ran the script and it looked like the data was uploaded successfully because the last line says DONE' then you have failed! Read each output carefully and see if an error occurred stopping a successful upload.

## Memorator Upload Script Maintainence
- The `./scripts/csv_upload.sh` is a problematic script sometimes. This is because different computers will have different problems. So its important to test out the memorator upload script every semester and ensure *at least* all of the **EMD** team can run the memorator upload script. Yes, [dual booting Ubuntu or having Ubuntu natively is a requirement](https://wiki.ubcsolar.com/en/subteams/embedded/embedded-dev-env-setup.md). I recommend 22.04.  
- The `setup.sh` script has a section to install the drivers to use the Memorator Upload script. Specifically, these are the `canlib` drivers which include `linuxcan` and `kvlibsdk`. In there you may need to change the `sudo wget -P ~ --content-disposition "https://resources.kvaser.com/PreProductionAssets/Product_Resources/kvlibsdk_5_45_724.tar.gz"` command or the `sudo tar -xzvf ~/linuxcan*.tar.gz -C ~ ` commands due to them being out of date. In the first command, the entire URL might change because Kvaser has a tendency to do that... For example, in the latter command the regex using `*` may not apply in the future.  
