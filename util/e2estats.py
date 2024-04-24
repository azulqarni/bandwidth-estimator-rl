import re
import time
import sys
import random
import paramiko
from statistics import mean, stdev
from datetime import datetime
from .logflatten import *
from .parameters import *

class BSTree:
    # binary search (BS) tree
    def __init__(self, value=None):
        self.left = None
        self.right = None
        self.value = value

    def insert(self, value):
        if not self.value:
            self.value = value
            return

        if self.value[0] == value[0]:
            return

        if value[0] < self.value[0]:
            if self.left:
                self.left.insert(value)
                return
            self.left = BSTree(value)
            return

        if self.right:
            self.right.insert(value)
            return
        self.right = BSTree(value)

    def find(self, value):
        if self.value and value == self.value[0]:
            return self

        if not self.value:
            return None

        if value < self.value[0]:
            if self.left == None:
                return False
            return self.left.find(value)

        if self.right == None:
            return False
        return self.right.find(value)

class Node:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None
        self.height = 1

class AVLTree:
    def __init__(self):
        self.root = None

    def insert(self, value):
        self.root = self._insert(self.root, value)

    def _insert(self, node, value):
        if not node:
            return Node(value)

        if value[0] < node.value[0]:
            node.left = self._insert(node.left, value)
        else:
            node.right = self._insert(node.right, value)

        node.height = 1 + max(self._get_height(node.left), self._get_height(node.right))
        balance = self._get_balance(node)

        # Left Left Case
        if balance > 1 and value[0] < node.left.value[0]:
            return self._right_rotate(node)

        # Right Right Case
        if balance < -1 and value[0] > node.right.value[0]:
            return self._left_rotate(node)

        # Left Right Case
        if balance > 1 and value[0] > node.left.value[0]:
            node.left = self._left_rotate(node.left)
            return self._right_rotate(node)

        # Right Left Case
        if balance < -1 and value[0] < node.right.value[0]:
            node.right = self._right_rotate(node.right)
            return self._left_rotate(node)

        return node

    def _get_height(self, node):
        if not node:
            return 0
        return node.height

    def _get_balance(self, node):
        if not node:
            return 0
        return self._get_height(node.left) - self._get_height(node.right)

    def _right_rotate(self, z):
        y = z.left
        T3 = y.right

        y.right = z
        z.left = T3

        z.height = 1 + max(self._get_height(z.left), self._get_height(z.right))
        y.height = 1 + max(self._get_height(y.left), self._get_height(y.right))

        return y

    def _left_rotate(self, y):
        x = y.right
        T2 = x.left

        x.left = y
        y.right = T2

        y.height = 1 + max(self._get_height(y.left), self._get_height(y.right))
        x.height = 1 + max(self._get_height(x.left), self._get_height(x.right))

        return x

    def find(self, key):
        return self._find(self.root, key)

    def _find(self, node, key):
        if not node:
            return None
        if node.value[0] == key:
            return node
        elif key < node.value[0]:
            return self._find(node.left, key)
        else:
            return self._find(node.right, key)

def list_to_hex (Bytes):
    # perform bytewise hex digit concatenation
    val = 0
    length = len (Bytes)
    for i in range (0, length):
        val += int (Bytes[i], 16) * (16 ** (2 * length - 2 * (i + 1)))
    return val

def time_to_ms (timestamp):
    # convert timestamp to number of ms from start of day
    units = timestamp.split (':')
    seconds = float (units[0]) * 3600 + float (units[1]) * 60 + float (units[2])
    return int (1e3 * seconds)

def log_load(unit, filename):
    # process file and return MAC packet lines, time indexed IP packets

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

    # Count (IP) packets of interest; we may want to downsample
    packet_count = 0

    # Define sparsity differently for each unit
    packet_sparsity = 1 # unit_packet_sparsity[unit]

    with open (filename) as file:
        for line in file:
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
                    mac_headers.append(line.strip())
            if ignore_content or comment_pattern.match(line):
                # Skip commented-lines and MAC payload
                continue
            if payload_lines <= max_payload_lines:
                # include only up to 16*max_payload_lines
                # bytes for packet ID
                ip_lines.append(line.strip())
                payload_lines += 1

    return ip_lines, list(reversed(mac_headers))

def parse_ip_packet_cluster(ip_lines):
    # max number of bytes per line is 16
    numFields = 16
    timestamps = []
    # Skip last line as it may be truncated
    numLines = len (ip_lines) - 1
    ip_packets = []
    for i in range (0, numLines):
        numWords = len (ip_lines[i].split())
        # Skip lines that are not IP headers e.g., truncation: "..."
        # also, check for dropped packets e.g.:
        # 16:51:57.874 [IP] UL 0004 Packet dropped
        if numWords < 2 or "dropped" in ip_lines[i] or not ip_id in ip_lines[i]:
            continue

        payload = []
        # print (ip_lines[i])
        # Find nominal packet size from len=* variable.
        numBytes = int (ip_lines[i].split()[4].split("=")[1])
        timestamp = ip_lines[i].split()[0]
        while i + 1 < numLines and \
              ip_lines[i + 1].split()[0] != "..." and \
              ip_lines[i + 1].split()[1] != "[IP]": # see comment below
              # payload linewise termination condition (inverted...)
              # comment: assuming strict-ish log formatting that does not
              # allow non commented lines with <2 words that are neither headers
              # nor truncation abbreviation, we do not check list boundaries
            # print(ip_lines[i])
            i, j = i + 1, 1
            tokens = ip_lines[i].split()
            # Concatenate up to 16 payload bytes per line
            while j <= numFields and numBytes > 0:
                payload.append (tokens[j])
                numBytes -= 1
                j += 1

        packet = (list_to_hex (payload), time_to_ms (timestamp))
        ip_packets.append(packet)

    return ip_packets

def parse_ue (time_intervals_dt):
    # Bitwise hex digit concatenation of packet payload
    # Collect data with timestamp >= start_time_str

    # Fetch remote timestamped log files
    # start_time = datetime.strptime(start_time_str, "%Y%m%d.%H:%M:%S")
    # print (time_intervals_dt)
    start_time = time.time()
    ip_lines_clusters, mac_headers = extract_ue_entries_within_intervals(time_intervals_dt)
    end_time = time.time()
    time_taken = end_time - start_time
    if debug_mode: print(f"[e2estats] extract_ue_entries_within_intervals took: {time_taken:.3f} seconds")
    # print (unit + " - " + str(len(ip_lines)))

    # Initialize list of trees as empty list
    tree_cluster = []
    packet_windows = []
    start_time = time.time()
    for ip_lines in ip_lines_clusters:
        ip_packets = parse_ip_packet_cluster(ip_lines)
        random.shuffle(ip_packets)
        # (i) Use BS tree for Tx packets OR
        data = BSTree () # AVLTree () #
        packet_per_cluster = 0
        for packet in ip_packets:
            data.insert(packet)
            packet_per_cluster += 1

        packet_windows.append(packet_per_cluster)
        tree_cluster.append(data)
    end_time = time.time()
    time_taken = end_time - start_time
    if debug_mode: print(f"[e2estats] parse_ip_packet_cluster[ue] took: {time_taken:.3f} seconds")
    if debug_mode: print(f"[e2estats] {len(packet_windows)} samples from Rx logs are sought for amongst their respective amount of packets at Tx logs {packet_windows}")
    return tree_cluster, mac_headers

def parse_mme(start_time_str, num_samples):
    start_time_dt = datetime.strptime(start_time_str, "%Y%m%d.%H:%M:%S")
    end_time_dt = datetime.now()

    window_size= max_delay/1000  # seconds
    time_delta = (end_time_dt - start_time_dt) / (num_samples - 1)  # Calculate the time interval between samples
    samples_dt = [start_time_dt + i * time_delta for i in range(num_samples)]

    start_time = time.time()
    # Update coarse timestamps with actual ones
    ip_lines, samples_dt = extract_sample_mme_entries(start_time_dt, samples_dt)
    end_time = time.time()
    time_taken = end_time - start_time
    if debug_mode: print(f"[e2estats] extract_sample_mme_entries took: {time_taken:.3f} seconds")

    start_time = time.time()
    ip_packets = parse_ip_packet_cluster(ip_lines)
    end_time = time.time()
    time_taken = end_time - start_time
    if debug_mode: print(f"[e2estats] parse_ip_packet_cluster[mme] took: {time_taken:.3f} seconds")

    time_intervals_dt = [(sample - timedelta(seconds=window_size), sample) for sample in samples_dt]
    random_samples_str = [sample.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] for sample in samples_dt]
    time_intervals_str = [(sample[0].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],sample[1].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]) for sample in time_intervals_dt]
    if debug_mode: print(f'[e2estats] Looking for samples around: {random_samples_str}')
    if debug_mode: print(f'[e2estats] Looking for matches in: {time_intervals_str}')
    return ip_packets, time_intervals_dt

def parse_bsr (filename, unit, start_time_str):
    # Bitwise hex digit concatenation of packet payload
    # Collect data with timestamp >= start_time_str

    if oldStyle:
        # Read static input
        _, mac_headers = log_load(unit, filename)
    else:
        # Fetch remote timestamped log files
        start_time = datetime.strptime(start_time_str, "%Y%m%d.%H:%M:%S")
        _, mac_headers = extract_entries_since_time(unit, start_time)
    # print (unit + " - " + str(len(ip_lines)))

    return mac_headers

def e2e_stats(data_tx, data_rx):
    # Calculate end-to-end delays by searching
    # for received packets in transmitted logs
    lost_packets = 0
    e2e_delay = []
    for i in range(0, len(data_rx)):
        if not data_tx[i]:
            lost_packets += 1
            continue
        mapper = data_tx[i].find(data_rx[i][0])  # Reversed the roles of data_tx and data_rx

        if mapper:
            tx_time = mapper.value[1]  # Reversed the roles of data_tx and data_rx
            rx_time = data_rx[i][1]  # Reversed the roles of data_tx and data_rx
            e2e_delay.append(rx_time - tx_time)
        else:
            # for packets not received within a predefined window
            lost_packets += 1
            e2e_delay.append(max_delay)

    print(f'[e2estats] {len(e2e_delay)} packets taken into account for end-to-end delay, of which {lost_packets} are unmatched')
    return lost_packets, e2e_delay

# Function to extract the timestamp from the line
def extract_timestamp(line):
    timestamp_str = line.split(' ')[0]
    return datetime.strptime(timestamp_str, "%H:%M:%S.%f")

# Function to calculate the time difference in seconds
def calculate_time_difference(timestamp1, timestamp2):
    return (timestamp2 - timestamp1).total_seconds()

def last_bsr(mac_headers, active_users):
    # define a regex for matching MAC UL/DL BSR logs for active users
    ue_ids = '|'.join([format(ue_id, '04x') for ue_id in active_users])
    pattern = r'\[MAC\].*?(DL|UL).*?(' + ue_ids + r').*?b=(\d+)'

    # Define a list of DL/UL buffer length tuples
    bsr = [[None, None] for _ in range(len(active_users))]

    # index tuples by directionality
    dirmap = {"DL": 0, "UL": 1, }

    # Set the threshold time difference in seconds (window size)
    threshold_seconds = 1

    if mac_headers:
        # Extract the timestamp from the first line
        first_timestamp = extract_timestamp(mac_headers[0])

    # traverse the MAC header logs in decreasing time
    for line in mac_headers:
        current_timestamp = extract_timestamp(line)
        time_difference = calculate_time_difference(first_timestamp, current_timestamp)
        # Loop through the subsequent lines and compare their timestamps
        if time_difference > threshold_seconds:
            break

        match = re.search(pattern, line)
        if match:
            # Direction is DL/UL or 0/1
            direction = match.group(1)
            try:
                # UE ID is provided by input list active_users
                ue_id = active_users.index(int(match.group(2), 16))
                # BSR value is the RHS of b equals
                bsr_value = int(match.group(3))
            except ValueError:
                # Handle the case where the hexadecimal conversion failed
                continue

            except IndexError:
                # Handle the case where the value is not found in the active_users list
                continue

            # update BSR values with the earliest enountered
            if  bsr[ue_id][dirmap[direction]] is None:
                bsr[ue_id][dirmap[direction]] = bsr_value
                # Count the number of missing values (None) in the list
                if 0 == sum(item.count(None) for item in bsr):
                    break

    # If after checking all the UL relevant logs, BSR for a user
    # is not found, assume the user has been recenty inactive, therefore b=0
    bsr = [[0 if value is None else value for value in user_bsr] for user_bsr in bsr]
    return bsr

def scp_file(remote_file_path, local_file_path, ssh_key_path, ssh_username, ssh_host):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Load the private key
    private_key = paramiko.Ed25519Key(filename=ssh_key_path)

    try:
        # Connect to the remote server
        ssh.connect(hostname=ssh_host, username=ssh_username, pkey=private_key)

        # Create an SFTP client to perform the file transfer
        sftp = ssh.open_sftp()

        # Download the remote file to the local path
        sftp.get(remote_file_path, local_file_path)

        # Close the SFTP connection
        sftp.close()

    except paramiko.AuthenticationException as e:
        print("Authentication failed:", e)
    except paramiko.SSHException as e:
        print("SSH connection failed:", e)
    except Exception as e:
        print("An error occurred:", e)
    finally:
        ssh.close()

def fetch_logs(*args):
    local_file_path = [ue_log, enb_log]
    remote_path = ["/tmp/ue.log", "/tmp/mme.log"]
    ssh_key_path = ["./keys/uebox_ssh_ed25519.txt", "./keys/callbox_ssh_ed25519.txt"]
    remote_server = [uebox_ip, callbox_ip]
    username = "root"

    # Create a local "logs" folder
    if not os.path.exists(logs):
        try:
            os.makedirs(logs)
            print(f"Folder '{logs}' created successfully.")
        except OSError as e:
            print(f"Error creating folder '{logs}': {e}")

    for value in args:
        if value == "ue":
            print("Fetching UE logs...")
            scp_file(remote_path[0], local_file_path[0], ssh_key_path[0], username, remote_server[0])

        elif value == "mme":
            print("Fetching MME logs...")
            scp_file(remote_path[1], local_file_path[1], ssh_key_path[1], username, remote_server[1])

        else:
            print(f"Invalid argument: '{value}'")

if __name__ == "__main__":
    # Tree operating functions are recursive
    # sys.setrecursionlimit(10000)

    # fetch_logs("ue", "mme")
    if len(sys.argv) > 1:
        enb_log = f'scenarios/mme-export.{sys.argv[1]}.log'
        ue_log  = f'scenarios/ue-export.{sys.argv[1]}.log'

    # enb_log = f'scenarios/mme-export.9.log'
    # ue_log  = f'scenarios/ue-export.9.log'

    # data_rx, _           = parse (enb_log, "mme")
    # data_tx, mac_headers = parse (ue_log,  "ue0") #, "20230726.18:04:01")

    # bsr = last_bsr(mac_headers, [1,2])
    # print ("BSR [DL/UL]: ", bsr)

    # Select reward calculation based on enB side acting as indexer or indexee
    # lost_packets, e2e_delay = e2e_stats(data_tx, data_rx)
    # print ("Lost Packets.......................: " + str (lost_packets))
    # print ("Maximum End-to-End Delay.......(ms): " + str (max (e2e_delay)))
    # print ("Minimum End-to-End Delay.......(ms): " + str (min (e2e_delay)))
    # print ("Average End-to-End Delay.......(ms): " + str (round (mean (e2e_delay), 2)))
    # print ("Deviation of End-to-End Delay..(ms): " + str (round (stdev (e2e_delay), 2)))
