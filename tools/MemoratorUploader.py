import canlib.kvmlib as kvmlib
import re
import datetime
import struct
import time
import sys

# Script Constants
global LOG_FOLDER
# LOG_FOLDER              = "/media/electrical/disk/"
NUM_LOGS                = 15
MB_TO_KB                = 1024
EPOCH_START             = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

# Formatting Constants
ANSI_GREEN              = "\033[92m"
ANSI_BOLD               = "\033[1m"
ANSI_RED                = "\033[91m"
ANSI_YELLOW             = "\033[93m"
ANSI_RESET              = "\033[0m"
ANSI_SAVE_CURSOR        = "\0337"
ANSI_RESTORE_CURSOR     = "\0338"

# Regex Patterns for logfile parsing
PATTERN_DATETIME        = re.compile(r't:\s*(.*?)\s*DateTime:\s*(.*)')
PATTERN_TRIGGER         = re.compile(r't:\s*(.*?)\s*Log Trigger Event.*')
PATTERN_EVENT           = re.compile(r't:\s*(.*?)\s*ch:1\s*f:\s*(.*?)\s*id:(.*?)\s*dlc:\s*(.*?)\s*d:(.*)')

# Data Constants
ERROR_ID                = 0

# Data Count Updater
MSGS_TO_UPDATE          = 1000


def upload(log_file: kvmlib.LogFile, parserCallFunc: callable, live_filters: list,  log_filters: list, display_filters: list, args: list, csv_file_f):
    start_time = None
    got_start_time = False
    global num_msgs_processed

    for event in log_file:
        str_event = str(event)
        
        if not got_start_time and PATTERN_DATETIME.search(str_event):
            got_start_time = True

            match = PATTERN_DATETIME.search(str_event)
            date_time_str = match.group(2)
            date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S') 
            utc_date_time_obj = date_time_obj.astimezone(datetime.timezone.utc)                 # Convert to UTC
            start_time = (utc_date_time_obj - EPOCH_START).total_seconds()
        elif PATTERN_TRIGGER.search(str_event):
            continue
        elif PATTERN_EVENT.search(str_event):
            match = PATTERN_EVENT.search(str_event)
            timestamp = start_time + float(match.group(1))
            timestamp_str = struct.pack('>d', timestamp).decode('latin-1')

            id = int(match.group(3).strip(), 16)

            if id == ERROR_ID:
                continue
            
            id_str = id.to_bytes(4, 'big').decode('latin-1') 

            dlc_str = match.group(4)

            data = bytes.fromhex(match.group(5).replace(' ', ''))
            data_str = data.ljust(8, b'\0').decode('latin-1')
            
            can_str = timestamp_str + "#" + id_str + data_str + dlc_str


            try:
                can_msg = parserCallFunc(can_str)
            except Exception as e:
                continue

            num_msgs_processed += 1

            if num_msgs_processed % MSGS_TO_UPDATE == 0:
                sys.stdout.write(ANSI_SAVE_CURSOR)  # Save cursor position
                sys.stdout.write(f"{ANSI_YELLOW}Processed {num_msgs_processed} Messages in {(time.time() - start_time_log):.2f} Seconds!{ANSI_RESET}")  # Yellow text
                sys.stdout.write(ANSI_RESTORE_CURSOR)  # Restore cursor position
                sys.stdout.flush()

            if not isinstance(can_msg, Exception) and can_msg is not None:
                dict_data = can_msg.data['display_data']['COL']
                class_name = dict_data['Class'][0]
                for i in range(len(dict_data['Timestamp'])):
                    csv_string = ",,0,,,"
                    csv_string += "T".join(dict_data['Timestamp'][i].split(" ")) + "Z"    # Timestamp
                    csv_string += "," + str(dict_data['Value'][i])                            # Value
                    csv_string += "," + dict_data['Measurement'][i]                      # Signal Name
                    csv_string += "," + dict_data['Source'][i]                           # Board Name
                    csv_string += "," + "Brightside"                                # Car Name
                    csv_string += "," + class_name                                  # Message Name

                    print(csv_string + '\n', file=csv_file_f, end='')
                
            continue
            

def memorator_upload_script(parserCallFunc: callable, live_filters: list,  log_filters: list, display_filters: list, args: list, csv_file_f):
    global num_msgs_processed
    global start_time_log 
    start_time_log = time.time()
    num_msgs_processed = 0

    ## If you look in the SD card there are 14 .KMF files. You are able to iterate thorugh them. However, 
    ## On closer inspection, each KMF file has EXACTLY the same logs! So, instead of going through each KMF
    ## and then uploading each of the logs, we only go through 1 KMF file and upload all of its logs. Thats what the fast option 
    ## does. The fast option means you upload all the logs of the first KMF file. However, we speculated that if the size of logs
    ## exceeds 1.1GB (the size of a single KMF file based on clicking 'properties' of the KMF file) then its possible (still not confirmed)
    ## that we would need to iterate through MULTIPLE KMF files. For now, we will do 1 KMF file.
    # numLogs = 1 if "fast" in [option.lower() for option in args.log_upload] else NUM_LOGS
    numLogs = 1
    
    # Get the log folder path as input
    LOG_FOLDER = input(f"{ANSI_GREEN}Enter the FULL ABSOLUTE path to the folder with .KMF files (include '/' at the end like ..../downloads/ and no '~'): {ANSI_RESET} ")  

    # Open each KMF file
    for i in range(numLogs):
        log_path = LOG_FOLDER + "LOG000{:02d}.KMF".format(i)
        kmf_file = kvmlib.openKmf(log_path.format(i))
        print(f"{ANSI_GREEN}Opening file: {log_path.format(i)}{ANSI_RESET}")  # Green stdout

        # Access the log attribute of the KMF object
        log = kmf_file.log

        # First calculate total number of events
        total_events = 0
        for log_file in log:
            total_events += log_file.event_count_estimation()

        # Display the number of logs
        num_logs = len(log)
        print(f"{ANSI_BOLD}Found {num_logs} logs with {total_events} events total{ANSI_RESET}")
        
        # Iterate over all log files
        for j, log_file in enumerate(log):
            # Calculate and display the approximate size
            num_events = log_file.event_count_estimation()
            kmf_file_size = kmf_file.disk_usage[0]
            kb_size = kmf_file_size * (num_events / total_events) * MB_TO_KB

            # Display information about each log
            start_time = log_file.start_time.isoformat(' ')
            end_time = log_file.end_time.isoformat(' ')
            print(f"{ANSI_BOLD}\nLog Idx = {j}, Approximate size = {kb_size:.2f} KB:{ANSI_RESET}")
            print(f"{ANSI_BOLD}\tEstimated events   : {num_events}{ANSI_RESET}")
            print(f"{ANSI_BOLD}\tStart time         : {start_time}{ANSI_RESET}")
            print(f"{ANSI_BOLD}\tEnd time           : {end_time}{ANSI_RESET}")

        # Close the KMF file
        kmf_file.close()

    upload_input = input(f"{ANSI_GREEN}Enter Log Indicies to Upload (Space Delimited) or type 'n' for no upload or 'y' for all: {ANSI_RESET} \n")
    delete_input = input(f"{ANSI_RED}Would you like to DELETE ALL after (y/n): {ANSI_RESET} \n")
    if upload_input.lower() != 'n' or upload_input == '':
        for i in range(numLogs):
            log_path = LOG_FOLDER + "LOG000{:02d}".format(i)
            kmf_file = kvmlib.openKmf(log_path.format(i))
            print(f"{ANSI_GREEN}Opening file: {log_path.format(i)}{ANSI_RESET}")  # Green stdout

            # Access the log attribute of the KMF object
            log = kmf_file.log
            
            # Iterate over all log files
            for j, log_file in enumerate(log):
                if (upload_input.lower() == 'y' or upload_input == ''):
                    upload(log[j], parserCallFunc, live_filters, log_filters, display_filters, args, csv_file_f)
                elif j in [int(i) for i in upload_input.split()]:
                    upload(log[j], parserCallFunc, live_filters, log_filters, display_filters, args, csv_file_f)

            
            # Close the KMF file
            kmf_file.close()

    print(f"\n{ANSI_BOLD}{ANSI_GREEN}====== DONE WRITING CSV ======{ANSI_RESET}{ANSI_RESET} \n")

    if delete_input.lower() == 'y':
        for i in range(numLogs):
            log_path = LOG_FOLDER + "LOG000{:02d}".format(i)
            kmf_file = kvmlib.openKmf(log_path.format(i))
            print(f"{ANSI_RED}Opening file: {log_path.format(i)}{ANSI_RESET}")  

            # Access the log attribute of the KMF object
            log = kmf_file.log
            log.delete_all()
            
            # Close the KMF file
            kmf_file.close()

            print(f"{ANSI_BOLD}{ANSI_RED}DELETED {log_path.format(i)}{ANSI_RESET}{ANSI_RESET}")  
    else:
        print(f"{ANSI_BOLD}{ANSI_GREEN}====== NOT DELETING ANYTHING ======{ANSI_RESET}{ANSI_RESET}\n")  

# TESTING PURPOSES
def main():
    memorator_upload_script()


if __name__ == "__main__":
    main()
