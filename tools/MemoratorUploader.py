import canlib.kvmlib as kvmlib
import re
import datetime
import struct

# Script Constants
PATH                = "D:\\LOG000{:02d}.KMF"
NUM_LOGS            = 15
MB_TO_KB            = 1024
EPOCH_START         = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)

# Formatting Constants
ANSI_GREEN          = "\033[92m"
ANSI_BOLD           = "\033[1m"
ANSI_RED            = "\033[91m"
ANSI_RESET          = "\033[0m"

# Regex Patterns for logfile parsing
PATTERN_DATETIME    = re.compile(r't:\s+(.*?)\s+DateTime:\s+(.*)')
PATTERN_TRIGGER     = re.compile(r't:\s+(.*?)\s+Log Trigger Event.*')
PATTERN_EVENT       = re.compile(r't:\s+(.*?)\s+ch:0 f:\s+(.*?) id:\s+(.*?) dlc:\s+(.*?) d:(.*)')


def upload(log_file: kvmlib.LogFile, parserCallFunc: callable, live_filters: list,  log_filters: list, args: list, endpoint: str):
    start_time = None
    for event in log_file:
        str_event = str(event)
        print(str_event)
        if PATTERN_DATETIME.search(str_event):
            match = PATTERN_DATETIME.search(str_event)
            date_time_str = match.group(2)
            print(f"Matched DateTime: {date_time_str}")
            date_time_obj = datetime.datetime.strptime(date_time_str, '%Y-%m-%d %H:%M:%S')
            date_time_obj = date_time_obj.replace(tzinfo=datetime.timezone.utc)  
            start_time = (date_time_obj - EPOCH_START).total_seconds()
        elif PATTERN_TRIGGER.search(str_event):
            continue
        elif PATTERN_EVENT.search(str_event):
            match = PATTERN_EVENT.search(str_event)
            timestamp = start_time + float(match.group(1))
            timestamp_str = struct.pack('>d', timestamp).decode('latin-1')

            id = int(match.group(3), 16)
            id_str = id.to_bytes(4, 'big').decode('latin-1') 

            dlc_str = match.group(4)

            data = bytes.fromhex(match.group(5).replace(' ', ''))
            data_str = data.decode('latin-1')
            
            can_str = timestamp_str + "#" + id_str + data_str + dlc_str

            parserCallFunc(can_str, live_filters, log_filters, args, endpoint)
            

def memorator_upload_script(parserCallFunc: callable, live_filters: list,  log_filters: list, args: list, endpoint: str):
    # Open each KMF file
    for i in range(NUM_LOGS):
        kmf_file = kvmlib.openKmf(PATH.format(i))
        print(f"{ANSI_GREEN}Opening file: {PATH.format(i)}{ANSI_RESET}")  # Green stdout

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

        # Ask the user what to upload
        upload_input = input(f"{ANSI_GREEN}Enter what logs to upload ('all' or x-y inclusive ranges comma separated):{ANSI_RESET} ")
        if upload_input.lower() == 'all':
            # Upload all logs
            for j in range(num_logs):
                upload(log[j], parserCallFunc, live_filters, log_filters, args, endpoint)
        else:
            # Parse the user input
            ranges = upload_input.split(',')
            for r in ranges:
                if '-' not in r:
                    idx = int(r)
                    if idx < 0 or idx >= num_logs:
                        print(f"{ANSI_RED}Index {idx} is out of range{ANSI_RESET}")
                    else:
                        upload(log[idx], parserCallFunc, live_filters, log_filters, args, endpoint)
                else:
                    start, end = map(int, r.split('-'))
                    # Upload the specified logs
                    for j in range(start, end + 1):
                        if j < 0 or j >= num_logs:
                            print(f"{ANSI_RED}Index {j} is out of range{ANSI_RESET}")
                        else:
                            upload(log[j], parserCallFunc, live_filters, log_filters, args, endpoint)
        
        # Close the KMF file
        kmf_file.close()


# TESTING PURPOSES
def main():
    memorator_upload_script()


if __name__ == "__main__":
    main()