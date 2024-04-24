import os
import re
import math
import paramiko
from parameters import ip_id, uebox_ip, callbox_ip, testing
from datetime import datetime, timedelta
from parameters import debug_mode
from parameters import sampling_window

def remote_params(unit):
    # Return per unit UEbox/Callbox parameters
    if unit == "ue0":
        # Parameters to be set if unit is "ue" (uebox)
        ssh_logs_mount_point = "./varlog/uebox.lte"
        log_filename_prefix = "ue0.log."
        remote_file_path = '/tmp/ue0.log'
        remote_directory = '/var/log/lte'
        remote_auth_key = './keys/uebox_ssh_ed25519.txt'
        remote_username = 'root'
        remote_host = uebox_ip

        if testing: # True if sshfs is used for remote log access
            # Parameters to be set if unit is "seil"
            ssh_logs_mount_point = "/home/user/lte.uebox"
            log_filename_prefix = "ue0.log."
            remote_file_path = '/tmp/ue0.log'
            # remote_file_path = '/home/user/lte.uebox/ue0.log'
            remote_directory = '/home/user/lte.uebox'
            remote_auth_key = '/home/user/.ssh/sshfs_proxy_ssh_ed25519.txt'
            remote_username = 'user'
            remote_host = '10.1.2.3'

    elif unit == "mme":
        # Parameters to be set if unit is "mme" (callbox)
        ssh_logs_mount_point = "./varlog/callbox.lte"
        log_filename_prefix = "mme.log."
        remote_file_path = '/tmp/mme.log'
        remote_directory = '/var/log/lte'
        remote_auth_key = './keys/callbox_ssh_ed25519.txt'
        remote_username = 'root'
        remote_host = callbox_ip

        if testing: # True if sshfs is used for remote log access
            # Parameters to be set if unit is "seil"
            ssh_logs_mount_point = "/home/user//lte.callbox"
            log_filename_prefix = "mme.log."
            remote_file_path = '/tmp/mme.log'
            remote_directory = '/home/user/lte.callbox'
            remote_auth_key = '/home/user/.ssh/sshfs_proxy_ssh_ed25519.txt'
            remote_username = 'user'
            remote_host = '10.1.2.3'

    else:
        if debug_mode: print("[logflatten] Invalid input. Please choose 'ue0' or 'mme'.")

    return ssh_logs_mount_point, log_filename_prefix, remote_file_path, \
           remote_host, remote_username, remote_auth_key, remote_directory


def list_remote_directories(unit):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Get per unit UEbox/Callbox parameters
    _,_,_,remote_host,remote_username,remote_auth_key,remote_directory = remote_params(unit)

    # Load the private key
    private_key = paramiko.Ed25519Key(filename=remote_auth_key)

    try:
        ssh.connect(remote_host, username=remote_username, pkey=private_key)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(f'ls -l {remote_directory}')

        # Read the output of the command
        output = ssh_stdout.read().decode()

        # Parse the output to get directory names
        directories = [line.split()[-1] for line in output.split('\n')[1:] if f"{unit}.log." in line]

        return directories

    except paramiko.AuthenticationException:
        if debug_mode: print("Authentication failed. Please check your credentials.")
    except paramiko.SSHException as ssh_ex:
        if debug_mode: print(f"SSH connection error: {ssh_ex}")
    finally:
        ssh.close()

def fetch_latest_log(unit):
    # Get the last modified date of the remote file
    # and fetch it from /tmp/{ue0,mme}.log to logs/ue0.log.$TIMESTAMP
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    local_directory = create_local_directory()

    # Get per unit UEbox/Callbox parameters
    _,log_filename_prefix, remote_file_path, remote_host, \
    remote_username, remote_auth_key, remote_directory = remote_params(unit)

    # Load the private key
    private_key = paramiko.Ed25519Key(filename=remote_auth_key)
    local_filepath = None
    try:
        ssh.connect(remote_host, username=remote_username, pkey=private_key)
        sftp = ssh.open_sftp()

        # The latest logs is at /tmp/{ue0,mme}.log and lacks external timestamping
        remote_file_stat = sftp.stat(remote_file_path)
        last_modified_timestamp = remote_file_stat.st_mtime
        last_modified_date = datetime.fromtimestamp(last_modified_timestamp).strftime("%Y%m%d")

        # Especially for recent file /tmp/{ue0,mme}.log, follow the other logs
        # naming convetion and get file extension from first encounetered timestamp
        # in the contents (time), as well as the file creation date (calendar date)
        with sftp.open(remote_file_path) as remote_file:
            # Read the file line by line until we find the timestamp
            for line in remote_file:
                line = line.strip()
                timestamp = extract_timestamp(line, last_modified_date)
                if timestamp:
                    # Append the timestamp to the local filename
                    local_filename = f'{log_filename_prefix}{timestamp}'
                    local_filepath = os.path.join(local_directory, local_filename)

                    # Download the remote file to the local folder
                    sftp.get(remote_file_path, local_filepath)
                    if debug_mode: print(f"[logflatten] Copying {remote_file_path} to {local_filepath}")
                    break  # Stop reading the file once we found the timestamp
            else:
                if debug_mode: print("[logflatten] Timestamp not found in the file.")

        sftp.close()

        return local_filepath # Return the new timestamped filename

    except paramiko.AuthenticationException:
        if debug_mode: print("Authentication failed. Please check your credentials.")
    except paramiko.SSHException as ssh_ex:
        if debug_mode: print(f"SSH connection error: {ssh_ex}")
    finally:
        ssh.close()

def fetch_remote_files(unit, remote_files):
    # Fetch files with full-paths in list remote_files
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    local_directory = create_local_directory()

    # Get per unit UEbox/Callbox parameters
    _, _, _, remote_host, remote_username, remote_auth_key, \
        remote_directory = remote_params(unit)

    # Load the private key
    private_key = paramiko.Ed25519Key(filename=remote_auth_key)

    try:
        ssh.connect(remote_host, username=remote_username, pkey=private_key)
        sftp = ssh.open_sftp()

        # local log files paths
        local_logs = []

        # Fetch each file from the remote directory and store it in the local directory
        for file_name in remote_files:
            remote_path = os.path.join(remote_directory, file_name)
            local_path = os.path.join(local_directory, file_name)
            sftp.get(remote_path, local_path)
            if debug_mode: print(f"[logflatten] Copying {remote_path} to {local_path}")
            local_logs.append(local_path)

        sftp.close()

        return local_logs  # Return the list of the local logs

    except paramiko.AuthenticationException:
        if debug_mode: print("Authentication failed. Please check your credentials.")
    except paramiko.SSHException as ssh_ex:
        if debug_mode: print(f"SSH connection error: {ssh_ex}")
    finally:
        ssh.close()

def create_local_directory():
    # Locate and if necessary, create local logs folder
    local_directory = './logs'

    if not os.path.exists(local_directory):
        os.makedirs(local_directory)

    return local_directory

def get_log_directory(unit, isLocal):
    # Get local or remote log directory contents
    if isLocal:
        ssh_logs_mount_point, _, _, _, _, _, _ = remote_params(unit)
        log_files = os.listdir(ssh_logs_mount_point)
        log_files = [log for log in log_files if f"{unit}.log." in log]
    else:
        log_files = list_remote_directories(unit)

    # Sort them; binary search will be performed
    log_files.sort()

    return log_files

def get_current_datetime_string():
    now = datetime.now()
    formatted_date_time = now.strftime("%Y%m%d.%H:%M:%S")
    return formatted_date_time

def parse_timestamp(timestamp_str):
    return datetime.strptime(timestamp_str, "%Y%m%d.%H:%M:%S")

def timestamp_to_milliseconds(timestamp):
    return timestamp.timestamp() * 1000

def milliseconds_to_seconds_ceil(milliseconds):
    return math.ceil(milliseconds / 1000)

def subtract_milliseconds_from_timestamp(timestamp_str, milliseconds_to_subtract):
    given_timestamp = parse_timestamp(timestamp_str)
    given_seconds = milliseconds_to_seconds_ceil(milliseconds_to_subtract)
    new_timestamp = given_timestamp - timedelta(seconds=given_seconds)
    return new_timestamp.strftime("%Y%m%d.%H:%M:%S")

def extract_timestamp(line, filedate):
    # Regular expression pattern to find the timestamp at the beginning of the line
    timestamp_pattern = r'^(\d{2}:\d{2}:\d{2}\.\d{3})'
    match = re.match(timestamp_pattern, line)
    if match:
        timestamp = match.group(1)
        # Reformat the timestamp to "YYYYMMDD.HH:MM:SS"
        timestamp = f"{filedate}.{timestamp[:2]}:{timestamp[3:5]}:{timestamp[6:8]}"
        return timestamp
    return None

def find_latest_file_before_time(unit, log_files, target_time):
    # Opearte on sorted files list to perform binary search
    left, right = 0, len(log_files) - 1
    latest_file = None if not log_files else log_files[0]

    # Get per unit UEbox/Callbox parameters
    _,log_filename_prefix,_,_,_,_,_ = remote_params(unit)

    while left <= right:
        mid = (left + right) // 2
        filename = log_files[mid]
        timestamp_str = filename[len(log_filename_prefix):]
        timestamp = datetime.strptime(timestamp_str, "%Y%m%d.%H:%M:%S")

        if timestamp < target_time:
            latest_file = filename
            left = mid + 1
        else:
            right = mid - 1

    return latest_file

def extract_sample_mme_entries(start_time_dt, time_samples_dt):
    # Set this to True, to load logs files from local folder
    isLocal = False

    unit = "mme"
    # Get per unit UEbox/Callbox parameters
    ssh_logs_mount_point, _, remote_file_path, remote_host, remote_username, \
    remote_auth_key, remote_directory = remote_params(unit)

    # Check directory where files post-log-rotation are stored
    log_files = get_log_directory(unit, isLocal)

    # To decide which logs are necessary, it is important to
    # take the latest log's timestamps into account
    if not isLocal:
        # Fetch current log file /tmp/{ue0,mme}.log
        local_filepath = fetch_latest_log(unit)
        if local_filepath:
            basename = os.path.basename(local_filepath)
            # latest log's timestamp can be appended to sorted list
            log_files.append(basename)
    else:
        # Take separately stored latest/current log, too
        basename = os.path.basename(remote_file_path)
        # latest log's timestamp can be appended to sorted list
        log_files.append(basename)

    # Perform binary search on the log filenames' timestamps
    latest_file = find_latest_file_before_time(unit, log_files, start_time_dt)

    if latest_file:
        # Find the index of the latest_file in the sorted list
        index_of_latest_file = log_files.index(latest_file)

        if debug_mode: print(f"[logflatten] Remote files of interest:", end=' ')
        if debug_mode: print(log_files[index_of_latest_file:])

        if not isLocal:
            # Fetch remote logs: (i) Files indicated by binary search, except
            # for the current log in /tmp/{ue0,mme}.log, which has been already copied
            target_files = log_files[index_of_latest_file:-1]
            local_logs = fetch_remote_files(unit, target_files)
            if local_filepath:
                local_logs.append(local_filepath)

        else:
            # Process logs that are accessible via the current file system;
            # this works with sshfs too.
            local_logs = [os.path.join(ssh_logs_mount_point, filename) \
                for filename in log_files[index_of_latest_file:]]

        sample_idx = 0
        ip_entries = []
        sample_timestamp = []
        # print (time_samples_dt)
        for filepath in local_logs:
            # Now that all logs of interest are accessible locally, process them
            ip_lines, sample_real_timestamps, sample_idx = extract_mme_entries_from_file(unit, filepath, time_samples_dt, sample_idx)
            ip_entries.extend(ip_lines)
            sample_timestamp.extend(sample_real_timestamps)
            # print(f"[logflatten] Found {sample_idx} samples from mme logs.")
            # if sample_idx >= len(time_samples_dt):
            #     break

        # print (f"[logflatten] Returned {sample_idx} samples from mme logs.")
        # print (ip_entries)
        return ip_entries, sample_timestamp

    else:
        return [], []

def extract_ue_entries_within_intervals(time_intervals_dt):
    # Set this to True, to load logs files from local folder
    isLocal = False

    unit = "ue0"
    # Get per unit UEbox/Callbox parameters
    ssh_logs_mount_point, _, remote_file_path, remote_host, remote_username, \
    remote_auth_key, remote_directory = remote_params(unit)

    # Check directory where files post-log-rotation are stored
    log_files = get_log_directory(unit, isLocal)

    # To decide which logs are necessary, it is important to
    # take the latest log's timestamps into account
    if not isLocal:
        # Fetch current log file /tmp/{ue0,mme}.log
        local_filepath = fetch_latest_log(unit)
        if local_filepath:
            basename = os.path.basename(local_filepath)
            # latest log's timestamp can be appended to sorted list
            log_files.append(basename)
    else:
        # Take separately stored latest/current log, too
        basename = os.path.basename(remote_file_path)
        # latest log's timestamp can be appended to sorted list
        log_files.append(basename)

    # Perform binary search on the log filenames' timestamps
    try:
        start_time_dt = time_intervals_dt[0][0]
    except IndexError:
        return [], []

    latest_file = find_latest_file_before_time(unit, log_files, start_time_dt)

    if latest_file:
        # Find the index of the latest_file in the sorted list
        index_of_latest_file = log_files.index(latest_file)

        if debug_mode: print(f"[logflatten] Remote files of interest:", end=' ')
        if debug_mode: print(log_files[index_of_latest_file:])

        if not isLocal:
            # Fetch remote logs: (i) Files indicated by binary search, except
            # for the current log in /tmp/{ue0,mme}.log, which has been already copied
            target_files = log_files[index_of_latest_file:-1]
            local_logs = fetch_remote_files(unit, target_files)
            if local_filepath:
                local_logs.append(local_filepath)

        else:
            # Process logs that are accessible via the current file system;
            # this works with sshfs too.
            local_logs = [os.path.join(ssh_logs_mount_point, filename) \
                for filename in log_files[index_of_latest_file:]]

        mac_entries = []
        ip_entries = [[] for _ in range(len(time_intervals_dt))]
        for filepath in local_logs:
            # Now that all logs of interest are accessible locally, process them
            ip_lines, mac_headers = extract_ue_entries_from_file(unit, filepath, time_intervals_dt)
            for i in range (0, len(ip_entries)):
                ip_entries[i].extend(ip_lines[i])
            mac_entries.extend(mac_headers)

        # print (f"[logflatten] Returned {len(ip_entries)} windows from ue0 logs.")
        return ip_entries, list(reversed(mac_entries))

    else:
        return [], []

def parse_packet_timestamp(timestamp_str):
    # Parse a timestamp string into a datetime object
    return datetime.strptime(timestamp_str, "%H:%M:%S.%f")

def find_interval_index0(timestamp_dt, intervals):
    # Intervals are sorted by default
    # Sort the intervals based on their start times
    sorted_intervals = intervals # sorted(intervals, key=lambda x: x[0])

    # Binary search to find the interval containing the timestamp
    low, high = 0, len(sorted_intervals) - 1

    while low <= high:
        mid = (low + high) // 2
        interval_start, interval_end = sorted_intervals[mid]

        if interval_start <= timestamp_dt <= interval_end:
            return mid, True
        elif timestamp_dt < interval_start:
            high = mid - 1
        else:
            low = mid + 1

    return low, False

def find_interval_indices(timestamp_dt, intervals):
    # Convert the input timestamp to a datetime object
    # timestamp_dt = parse_timestamp(timestamp)

    # Sort the intervals based on their start times
    # sorted_intervals = sorted(intervals, key=lambda x: x[0])

    # Iterate through the sorted intervals and yield matching indices
    for index, (interval_start, interval_end) in enumerate(intervals):
        if interval_start <= timestamp_dt <= interval_end:
            yield index


def extract_ue_entries_from_file(unit, filepath, time_intervals_dt):
    # Process file and return MAC packet lines, time indexed IP packets
    # represented by bitwise hex digit concatenation of their payload.
    # The packets' timestamps are subjects to constraints

    if debug_mode: print('[logflatten] Now locally processing: ', end='')
    if debug_mode: print (filepath)

    # Load log file
    with open(filepath, "r") as file:
        log_content = file.readlines()

    # Get per unit UEbox/Callbox parameters
    _,log_filename_prefix,_,_,_,_,_ = remote_params(unit)

    # Regex for commented lines to ignore
    comment_pattern = re.compile(r'^\s*(?:#.*)?$')

    # Regex timestamps patterns to match
    timestamp_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}')

    # store only ip packets here
    ip_lines = [[] for _ in range(len(time_intervals_dt))]
    # store ip packets per separate indexed intervals
    index = 0

    # store remaining packets (MAC, etc.) here
    mac_headers = []

    # payload line (amari log format) counter
    payload_lines = 0

    # specify up to how many bytes will be used for packet ID
    max_payload_lines = 3

    # Flag to indicate when to ignore lines
    ignore_content = False

    # Count (IP) packets of interest; we may want to downsample
    packet_count = 0

    interesting = False

    matching_indices = []

    # Define sparsity differently for each unit
    packet_sparsity = 1 # unit_packet_sparsity[unit]

    filename_date = filepath.split(log_filename_prefix)[-1].split(".")[0]
    if filename_date == 'log':
        mtime = os.path.getmtime(filepath)
        last_modified_time = datetime.fromtimestamp(mtime)
        filename_date = last_modified_time.strftime("%Y%m%d")

    for line in log_content:
        match = re.search(r'^\d{2}:\d{2}:\d{2}\.\d{3}', line)
        if match:
            interesting = False
            # Amarisoft logs timestamps contain only relative time from the start of day
            timestamp_str = match.group()
            # Augment timestamp to include calendar date...
            str_timestamp = filename_date + "." + timestamp_str
            timestamp = datetime.strptime(str_timestamp, "%Y%m%d.%H:%M:%S.%f")
            # index, interesting = find_interval_index(timestamp, time_intervals_dt)
            matching_indices = list(find_interval_indices(timestamp, time_intervals_dt))

        if matching_indices:
            if match:
                if ip_id in line:
                    # Collect payload for IP packets
                    payload_lines = 0
                    ignore_content = False
                    packet_count += 1
                    if packet_count % packet_sparsity != 0:
                        ignore_content = True
                else:
                    # Discard payload for other type (MAC, etc.) packets
                    ignore_content = True
                    # for such packets, just keep the header
                    mac_headers.append(line) #.strip())

            if ignore_content or comment_pattern.match(line):
                # Skip commented-lines and MAC payload
                continue

            if payload_lines <= max_payload_lines:
                # include only up to 16*max_payload_lines
                # bytes for packet ID
                for index in matching_indices:
                    ip_lines[index].append(line) #.strip())
                payload_lines += 1

    return ip_lines, mac_headers

def extract_mme_entries_from_file(unit, filepath, time_samples_dt, sample_idx, tolerance_seconds = sampling_window/2):
    # Process file and return MAC packet lines, time indexed IP packets
    # represented by bitwise hex digit concatenation of their payload.
    # The packets' timestamps are subjects to constraints

    if debug_mode: print('[logflatten] Now locally processing: ', end='')
    if debug_mode: print (filepath)

    # Load log file
    with open(filepath, "r") as file:
        log_content = file.readlines()

    # Get per unit UEbox/Callbox parameters
    _,log_filename_prefix,_,_,_,_,_ = remote_params(unit)

    # Regex for commented lines to ignore
    comment_pattern = re.compile(r'^\s*(?:#.*)?$')

    # Regex timestamps patterns to match
    timestamp_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}')

    # store only ip packets here
    ip_lines = []

    # store remaining packets (MAC, etc.) here
    mac_headers = []

    # payload line (amari log format) counter
    payload_lines = 0

    # specify up to how many bytes will be used for packet ID
    max_payload_lines = 3

    # Flag to indicate when to ignore lines
    ignore_content = False

    # Flag to indicate when to append lines
    append_mode = False

    # Count (IP) packets of interest; we may want to downsample
    packet_count = 0

    # Define sparsity differently for each unit
    packet_sparsity = 1 # unit_packet_sparsity[unit]

    sample_timestamp = []

    filename_date = filepath.split(log_filename_prefix)[-1].split(".")[0]
    if filename_date == 'log':
        mtime = os.path.getmtime(filepath)
        last_modified_time = datetime.fromtimestamp(mtime)
        filename_date = last_modified_time.strftime("%Y%m%d")

    for line in log_content:
        if sample_idx >= len(time_samples_dt):
            break
        match = re.search(r'^\d{2}:\d{2}:\d{2}\.\d{3}', line)
        if match:
            # Check if timestamp if acceptable
            append_mode = False
            # Amarisoft logs timestamps contain only relative time from the start of day
            timestamp_str = match.group()
            # Augment it by date for robustness
            str_timestamp = filename_date + "." + timestamp_str
            timestamp = datetime.strptime(str_timestamp, "%Y%m%d.%H:%M:%S.%f")
            # print (f"Looking for: {time_samples_dt[sample_idx]}, encountered {timestamp}")
            if ip_id in line and abs((time_samples_dt[sample_idx] - timestamp).total_seconds()) <= tolerance_seconds:
                # Flag packet if its timestamp is within sample range
                # print(f"Looking for: {time_samples_dt[sample_idx]}, found {timestamp}[{sample_idx}]")
                append_mode = True
                sample_idx += 1
                sample_timestamp.append(timestamp)
                # print (line)
            elif (timestamp - time_samples_dt[sample_idx]).total_seconds() > tolerance_seconds:
                # Skip sample if no sample within tolerance window is found
                sample_idx += 1

        if append_mode:
            # Store content only for flagged/acceptable packets
            if match:
                if ip_id in line:
                    # Collect payload for IP packets
                    payload_lines = 0
                    ignore_content = False
                    packet_count += 1
                    if packet_count % packet_sparsity != 0:
                        ignore_content = True
                else:
                    # Discard payload for other type (MAC, etc.) packets
                    ignore_content = True

            if ignore_content or comment_pattern.match(line):
                # Skip commented-lines and MAC payload
                continue

            if payload_lines <= max_payload_lines:
                # include only up to 16*max_payload_lines
                # bytes for packet ID
                ip_lines.append(line) #.strip())
                payload_lines += 1

    return ip_lines, sample_timestamp, sample_idx


def extract_entries_since_time(unit, start_time):
    # Set this to True, to load logs files from local folder
    isLocal = False

    # Get per unit UEbox/Callbox parameters
    ssh_logs_mount_point, _, remote_file_path, remote_host, remote_username, \
    remote_auth_key, remote_directory = remote_params(unit)

    # Check directory where files post-log-rotation are stored
    log_files = get_log_directory(unit, isLocal)

    # To decide which logs are necessary, it is important to
    # take the latest log's timestamps into account
    if not isLocal:
        # Fetch current log file /tmp/{ue0,mme}.log
        local_filepath = fetch_latest_log(unit)
        if local_filepath:
            basename = os.path.basename(local_filepath)
            # latest log's timestamp can be appended to sorted list
            log_files.append(basename)
    else:
        # Take separately stored latest/current log, too
        basename = os.path.basename(remote_file_path)
        # latest log's timestamp can be appended to sorted list
        log_files.append(basename)

    # Perform binary search on the log filenames' timestamps
    latest_file = find_latest_file_before_time(unit, log_files, start_time)

    if latest_file:
        # Find the index of the latest_file in the sorted list
        index_of_latest_file = log_files.index(latest_file)

        if debug_mode: print(f"[logflatten] Remote files of interest:", end=' ')
        if debug_mode: print(log_files[index_of_latest_file:])

        if not isLocal:
            # Fetch remote logs: (i) Files indicated by binary search, except
            # for the current log in /tmp/{ue0,mme}.log, which has been already copied
            target_files = log_files[index_of_latest_file:-1]
            local_logs = fetch_remote_files(unit, target_files)
            if local_filepath:
                local_logs.append(local_filepath)

        else:
            # Process logs that are accessible via the current file system;
            # this works with sshfs too.
            local_logs = [os.path.join(ssh_logs_mount_point, filename) \
                for filename in log_files[index_of_latest_file:]]

        ip_entries = []
        mac_entries = []
        for filepath in local_logs:
            # Now that all logs of interest are accesible locally, process them
            ip_lines, mac_headers = extract_entries_from_file(unit, filepath, start_time, datetime.now())
            ip_entries.extend(ip_lines)
            mac_entries.extend(mac_headers)

        return ip_entries, list(reversed(mac_entries))

    else:
        return [], []

def extract_entries_from_file(unit, filepath, start_time, end_time):
    # Process file and return MAC packet lines, time indexed IP packets
    # represented by bitwise hex digit concatenation of their payload.
    # The packets' timestamps are subjects to constraints

    if debug_mode: print('[logflatten] Now locally processing: ', end='')
    if debug_mode: print (filepath)

    # Load log file
    with open(filepath, "r") as file:
        log_content = file.readlines()

    # Get per unit UEbox/Callbox parameters
    _,log_filename_prefix,_,_,_,_,_ = remote_params(unit)

    # Regex for commented lines to ignore
    comment_pattern = re.compile(r'^\s*(?:#.*)?$')

    # Regex timestamps patterns to match
    timestamp_pattern = re.compile(r'^\d{2}:\d{2}:\d{2}\.\d{3}')

    # store only ip packets here
    ip_lines = []

    # store remaining packets (MAC, etc.) here
    mac_headers = []

    # payload line (amari log format) counter
    payload_lines = 0

    # specify up to how many bytes will be used for packet ID
    max_payload_lines = 3

    # Flag to indicate when to ignore lines
    ignore_content = False

    # Flag to indicate when to append lines
    append_mode = False

    # Count (IP) packets of interest; we may want to downsample
    packet_count = 0

    # Define sparsity differently for each unit
    packet_sparsity = 1 # unit_packet_sparsity[unit]

    # Amarisoft logs timestamps contain only relative time from the start of day
    filename_date = filepath.split(log_filename_prefix)[-1].split(".")[0]
    if filename_date == 'log':
        mtime = os.path.getmtime(filepath)
        last_modified_time = datetime.fromtimestamp(mtime)
        filename_date = last_modified_time.strftime("%Y%m%d")

    for line in log_content:
        if not append_mode:
            match = re.search(r'^\d{2}:\d{2}:\d{2}\.\d{3}', line)
            if match:
                timestamp_str = match.group()
                # Augment timestamp to include calendar date...
                str_timestamp = filename_date + "." + timestamp_str
                timestamp = datetime.strptime(str_timestamp, "%Y%m%d.%H:%M:%S.%f")
                if start_time <= timestamp <= end_time:
                    append_mode = True

        if append_mode:
            if timestamp_pattern.match(line):
                if ip_id in line:
                    # Collect payload for IP packets
                    payload_lines = 0
                    ignore_content = False
                    packet_count += 1
                    if packet_count % packet_sparsity != 0:
                        ignore_content = True
                else:
                    # Discard payload for other type (MAC, etc.) packets
                    ignore_content = True
                    # for such packets, just keep the header
                    mac_headers.append(line) #.strip())

            if ignore_content or comment_pattern.match(line):
                # Skip commented-lines and MAC payload
                continue

            if payload_lines <= max_payload_lines:
                # include only up to 16*max_payload_lines
                # bytes for packet ID
                ip_lines.append(line) #.strip())
                payload_lines += 1

    return ip_lines, mac_headers

def remove_all_files_from_directory(directory_path):
    try:
        # Get the list of files in the directory
        file_list = os.listdir(directory_path)

        # Loop through the files and delete them
        for filename in file_list:
            file_path = os.path.join(directory_path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)

        if debug_mode: print("[logflatten] All files have been removed from the directory.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    # Replace the following variables with your desired start time
    start_time_str = "20230726.18:00:26"

    start_time = datetime.strptime(start_time_str, "%Y%m%d.%H:%M:%S")
    time_intervals_dt = []

    ip_entries, mac_entries = extract_ue_entries_within_intervals(time_intervals_dt)

    with open('out.txt', 'w') as file:
        for entry in ip_entries:
            if debug_mode: print(entry, end='', file=file) #.strip())
