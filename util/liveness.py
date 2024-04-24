import re
import sys
import json
import subprocess
from parameters import *
from logflatten import get_current_datetime_string, subtract_milliseconds_from_timestamp
from e2estats import parse_bsr, last_bsr

def calculate_context():
    # Obtain the current context
    ue_list, mcs, active_users, num_alive_users = liveness(for_real)

    # Extract Uplink MCS and find average over users
    ul_mcs = [x[1] for x in mcs if x[1] is not None]
    if ul_mcs:
        avg_ul_mcs = sum(ul_mcs) / len(ul_mcs)
    else:
        avg_ul_mcs = 28
        print("No MCS found. Considering best possible MCS...")

    # For each UE, calculate its per-cell CQI
    # ue_cqi = [sum(cell_list) / len(cell_list) for _, _, cell_list in ue_list]
    # Calculate the average of per-UE CQI
    # avg_cqi = sum(ue_cqi) / len(ue_cqi)

    # Get some initial necessary data for context calculation
    starting_time = get_current_datetime_string()

    # Current starting time minus tolerance: How far in the past - 5s
    starting_buffer_time = subtract_milliseconds_from_timestamp(starting_time, 1e3)

    # print(f"Calculating context using packets with timestamps from [{starting_buffer_time}] to [{starting_time}].")

    # should we look to get enough data for context calculation?
    mac_headers = parse_bsr(ue_log, "ue0", starting_buffer_time)

    # Get the BSR indices per user per direction (DL/UL)
    bsr = last_bsr(mac_headers, active_users)

    # Find the BSR values in bytes using the b values from the logs
    ul_bsr = [bsr_list[direct[1]] for direct in bsr]

    # Sum the BSR values in bytes from the list above
    sum_ul_bsr = sum(ul_bsr)

    # Find the index of the above sum's closest value
    sum_ul_bsr_idx = min(range(len(bsr_list)), key=lambda i: abs(bsr_list[i] - sum_ul_bsr))

    # Context is number of active users, MCS, BSR
    context = [len(active_users), avg_ul_mcs, sum_ul_bsr_idx]

    return context, num_alive_users


def run_ws_command(node_command, ip_address, config_json_str):
    try:
        # Run the Node.js command and capture the output
        completed_process = subprocess.run(
            [node_command, ip_address, config_json_str],
            capture_output=True,
            text=True,
            check=True
        )

        # Get the output
        node_output = completed_process.stdout.strip()
        return node_output
    except subprocess.CalledProcessError as e:
        print(f"Error executing the Node.js command: {e}")
        return None


def ws_set_bandwidth(total_rb):
    # Selected arm is mapped to total_rb

    # Assign a value to first_rb
    first_rb = 5

    # Create a JSON object with the required configuration
    config_json = {
        "message": "config_set",
        "cells": {
            "1": {
                "pusch_fixed_rb_alloc": True,
                "pusch_fixed_rb_start": first_rb,
                "pusch_fixed_l_crb": total_rb
            }
        }
    }

    # Convert the JSON object to a string
    config_json_str = json.dumps(config_json)

    # Execute the command through the Amarisoft API
    ip_address = f"{callbox_ip}:9001"
    node_command = "./ws.js"
    node_output = run_ws_command(node_command, ip_address, config_json_str)
    if debug_mode: print(f"[liveness] The output of the ./ws.js is: {node_output}")


def ws_get_user_status(for_real4=True):
    if not for_real4:
        # Read the ws.js output from a file
        filename = 'ws.out'
        try:
            with open(filename, 'r') as file:
                node_output = file.read()
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found.")
            return None
    else:
        # Create a JSON object with the required configuration
        config_json = {
            "message": "ue_get"
        }

        # Convert the JSON object to a string
        config_json_str = json.dumps(config_json)

        # Execute the command through the Amarisoft API
        ip_address = f"{uebox_ip}:9002"
        node_command = "./ws.js"
        node_output = run_ws_command(node_command, ip_address, config_json_str)

    return node_output


def liveness(for_real1):
    node_output = ws_get_user_status(for_real1)
    mcs = []
    ue_list = []
    active_users = []
    num_alive_users = 0
    if node_output is not None:
        # Find the index of the first opening curly bracket in the output
        json_start_index = node_output.find('{')
        if json_start_index != -1:
            # Extract the JSON substring from the output
            json_data_str = node_output[json_start_index:]

            try:
                # Parse the JSON output and store the JSON
                # data in a Python variable as a dictionary.
                json_data = json.loads(json_data_str)

                for ue in json_data['ue_list']:
                    cells_cqi = []
                    cells_list = ue['cells']
                    for cell in cells_list:
                        cells_cqi.append(cell['cqi'])
                    ue_info = (ue['ue_id'], ue['rrc_state'], cells_cqi)
                    ue_list.append(ue_info)
                    if ue['emm_state'] != 'power off':
                        # count alive users
                        num_alive_users += 1

                    dl_mcs = ue.get('dl_mcs', None)
                    ul_mcs = ue.get('ul_mcs', None)
                    mcs.append((dl_mcs, ul_mcs))

                # Find the active UE IDs
                active_users = [t[0] for t in ue_list if t[1] == 'connected']

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
            except KeyError as e:
                print(f"KeyError: {e}")

    # note that a user may be alive, but idle
    return ue_list, mcs, active_users, num_alive_users


def ue_ip_addresses(for_real2):
    node_output = ws_get_user_status(for_real2)
    ue_ip = []
    if node_output is not None:
        # Find the index of the first opening curly bracket in the output
        json_start_index = node_output.find('{')
        if json_start_index != -1:
            # Extract the JSON substring from the output
            json_data_str = node_output[json_start_index:]

            try:
                # Parse the JSON output and store the JSON
                # data in a Python variable as a dictionary.
                json_data = json.loads(json_data_str)

                # Extract the IP address from each of the active users
                for ue in json_data['ue_list']:
                    if ue['rrc_state'] == 'connected':
                        ue_ip.append(ue["pdn_list"][0]["ipv4"])

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
            except KeyError as e:
                print(f"KeyError: {e}")

    # note that a user may be alive, but idle
    return ue_ip


if __name__ == "__main__":
    FOR_REAL = True
    if "static" in sys.argv:
        for_real = False

    UE_list, MCS, ACTIVE_UEs, ALIVE_UEs = liveness(FOR_REAL)
    print("The UE list:", UE_list)
    print("Number of connected UEs:", ACTIVE_UEs)
    print("Number of alive UEs:", ALIVE_UEs)
    print("MCS (DL,UL):", MCS)
    print("UE IP addresses: ", ue_ip_addresses(FOR_REAL))
