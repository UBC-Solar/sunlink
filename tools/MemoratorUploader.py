import canlib.kvmlib as kvmlib
import re
import datetime
import struct
import time

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
ANSI_RESET              = "\033[0m"

# Regex Patterns for logfile parsing
PATTERN_DATETIME        = re.compile(r't:\s+(.*?)\s+DateTime:\s+(.*)')
PATTERN_TRIGGER         = re.compile(r't:\s+(.*?)\s+Log Trigger Event.*')
PATTERN_EVENT           = re.compile(r't:\s+(.*?)\s+ch:0 f:\s+(.*?) id:(.*?) dlc:\s+(.*?) d:(.*)')

# Data Constants
ERROR_ID                = 0

# Delay Constants
SEND_TO_PARSER_DELAY    = 0.006


def upload(log_file: kvmlib.LogFile, parserCallFunc: callable, live_filters: list,  log_filters: list, display_filters: list, args: list, endpoint: str):
    start_time = None
    for event in log_file:
        str_event = str(event)
        if PATTERN_DATETIME.search(str_event):
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

            parserCallFunc(can_str, live_filters, log_filters, display_filters, args, endpoint)
            time.sleep(SEND_TO_PARSER_DELAY)
            

def memorator_upload_script(parserCallFunc: callable, live_filters: list,  log_filters: list, display_filters: list, args: list, endpoint: str):
    numLogs = 1 if "fast" in [option.lower() for option in args.log_upload] else NUM_LOGS
    
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

    upload_input = input(f"{ANSI_GREEN}Do you want to upload all logs now (y/n)?: {ANSI_RESET} \n")
    if upload_input.lower() == 'y' or upload_input.lower() == '\n':
        for i in range(numLogs):
            log_path = LOG_FOLDER + "LOG000{:02d}".format(i)
            kmf_file = kvmlib.openKmf(log_path.format(i))
            print(f"{ANSI_GREEN}Opening file: {log_path.format(i)}{ANSI_RESET}")  # Green stdout

            # Access the log attribute of the KMF object
            log = kmf_file.log
            
            # Iterate over all log files
            for j, log_file in enumerate(log):
                upload(log[j], parserCallFunc, live_filters, log_filters, display_filters, args, endpoint)

            # Clear the log files
            delete_input = input(f"{ANSI_GREEN}Do you want to {ANSI_RESET}{ANSI_RED}DELETE{ANSI_RESET} {ANSI_GREEN}all logs now (y/n)?: {ANSI_RESET} ")
            if delete_input.lower() == 'y' or delete_input.lower() == '\n':
                log.delete_all()
            
            # Close the KMF file
            kmf_file.close()
        

# TESTING PURPOSES
def main():
    memorator_upload_script()


if __name__ == "__main__":
    main()
