import os
import sys
import json
import heapq
import random
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from itertools import groupby
from util.parameters import round_interval

udp_payload = 200
rtp_payload = 200

def power_event(switch, time):
    # Template of instantaneous power event
    # Switch may take vales "on" or "off"
    event = {
        "start_time": time,
        "event": "power_" + switch
    }

    return event


def http_event(start, end):
    # Template of HTTP time interval
    # Define HTTP event by starting and ending times
    event = {
        "start_time": start,
        "end_time": end,
        "url": "http://192.168.3.1:8080/data?size=10000",
        "max_delay": 1,
        "max_cnx": 1000,
        "event": "http"
    }

    return event


def voip_event(start, end):
    # Template of VoIP time interval
    # Define VoIP event by starting and ending times
    event = {
        "start_time": start,
        "end_time": end,
        "dst_addr": "192.168.3.1",
        "payload_len": 32,
        "bit_rate": 12400,
        "vaf": 50,
        "mean_talking_duration": 8.6,
        "type": "voip",
        "event": "cbr_send"  # recv: downlink, send: uplink
    }

    return event


def rtp_event(start, end):
    # Template of RTP time interval
    # Define RTP event by starting and ending times
    event = {
        "start_time": start,
        "end_time": end,
        "dst_addr": "192.168.3.1",
        "payload_len": rtp_payload,
        "bit_rate": 1000000,
        "type": "rtp",
        "event": "cbr_send"  # recv: downlink, send: uplink
    }

    return event


def udp_event(start, end):
    # Template of UDP time interval
    # Define UDP event by starting and ending times
    event = {
        "start_time": start,
        "end_time": end,
        "dst_addr": "192.168.3.1",
        "payload_len": udp_payload,
        "bit_rate": 1000000,
        "type": "udp",
        "event": "cbr_send"  # recv: downlink, send: uplink
    }

    return event


def channel_attributes(channel_sim):
    # Define extra attributes if channel
    # simulation is selected
    if not channel_sim:
        return {}

    max_distance = 500
    min_distance = 0
    noise_spd = -174
    position = [random.uniform(0, 353), random.uniform(0, 353)]
    direction = random.uniform(0, 360)
    speed = random.uniform(40, 60)
    channel_type = "awgn"

    channel = {
        "max_distance": max_distance,
        "min_distance": min_distance,
        "noise_spd": noise_spd,
        "position": position,
        "direction": direction,
        "speed": speed,
        "channel": {
            "type": channel_type
        }
    }

    return channel


def config_template(channel_sim):
    # Define Amarisoft UE configuration template
    if not hasattr(config_template, "ue_id"):
        # Define the static variable if it doesn't exist yet
        config_template.ue_id = -1

    # Standard per UE parameter definition for ue.cfg file
    config_template.ue_id += 1
    ue_id = config_template.ue_id
    imsi = "{:015d}".format(1010123456789 + ue_id)
    imeisv = str(8180960000000101 + ue_id)
    sim_algo = "xor"
    K = "00112233445566778899aabbccddeeff"
    pdsch_max_its = 6
    as_release = 8
    ue_category = 4
    # Some extra parameters for the mme.cfg (DB) file
    amf = 36865
    sqn = "000000000000"

    ue_list_entry = {
        "ue_id": ue_id,
        "imsi": imsi,
        "imeisv": imeisv,
        "sim_algo": sim_algo,
        "channel_sim": channel_sim,
        "K": K,
        # "pdsch_max_its": pdsch_max_its,
        "as_release": as_release,
        "ue_category": ue_category,
        "sim_events": []
    }

    # Depending on the protocol, channel
    # conditions may be specified
    channel = channel_attributes(channel_sim)
    ue_list_entry.update(channel)

    ue_db_entry = {
        "imsi": imsi,
        "K": K,
        "amf": amf,
        "sqn": sqn,
        "sim_algo": sim_algo
    }

    return ue_list_entry, ue_db_entry


def ue_lifecycle(simulation_horizon, offtime, ontime):
    # Return a lifecycle in list of tuples (start, end),
    # given a total simulation time in seconds, average off-time
    # and on-time, in total, following exponential dirstibution
    cycle = []
    end_time = 0
    minimum_distance = 1  # Minimum distance between cycles

    while end_time < simulation_horizon:
        # Generate the duration of time that the UE does not send data
        # Exponential distribution with mean 20 seconds, minimum 1
        off_duration = np.random.exponential(scale=offtime - 1) + 1
        # Round off_duration to the nearest integer
        off_duration = int(round(off_duration))

        # Generate the duration of time that the UE sends data
        # Exponential distribution with mean 5 seconds, minimum 1
        on_duration = np.random.exponential(scale=ontime - 1) + 1
        # Round on_duration to the nearest integer
        on_duration = int(round(on_duration))

        start_time = end_time + off_duration + minimum_distance
        end_time = start_time + on_duration

        cycle.append((start_time, min(end_time, simulation_horizon)))

    # Trim the last cycle to match the simulation horizon T
    cycle = [(start_time, end_time) for start_time, end_time in cycle
             if start_time <= simulation_horizon - minimum_distance]

    return cycle


def group_tuples(tuples, maxUsers):
    # Iterate over sorted tuples and group unique tuples
    result = [[] for _ in range(maxUsers)]
    if tuples:
        index = -1
        current = tuples[0]
        for tuple in tuples:
            if tuple == current:
                index += 1
            else:
                index = 0
                current = tuple
            result[index].append(tuple)

    return result


def ue_lifecycle_alt(activity_times, ue_counts):
    # Generate UE activity times using two lists:
    # 1) a list for UE acitivity intervals e.g., [10min, 2min, 4min]
    # 2) a list for active UE population e.g., [5, 3, 7]
    # That would be interpreted as: 5 UEs are active for the first 10min,
    # 3 UEs are active for the subsequent 2min, while 7 UEs are active for the final 4min

    ue_lifecycles = []

    current_time = 0
    current_ue_count = 0

    for time, count in zip(activity_times, ue_counts):
        for _ in range(count):
            start_time = current_time
            end_time = current_time + time
            ue_lifecycles.append((start_time, end_time))
            current_ue_count += 1
            if current_ue_count == count:
                current_ue_count = 0
                current_time = end_time
    # print(ue_lifecycles)
    return group_tuples(ue_lifecycles, max(ue_counts))


def ue_configure(proto, simulation_horizon, offtime, ontime):
    # Choose what protocol will the UE simulate:
    if proto == "HTTP":
        # Case HTTP
        event_handler = http_event
        channel_sim = False
    elif proto == "RTP":
        # Case RTP
        event_handler = rtp_event
        channel_sim = True
    elif proto == "UDP":
        # Case UDP
        event_handler = udp_event
        channel_sim = True
    elif proto == "VoIP":
        # Case VoIP
        event_handler = voip_event
        channel_sim = False
    else:
        print("Unsupported Protocol: " + proto)
        return {}, {}

    # Create a UE sequence of events based on random
    # events following expontial distribution
    ue, ue_db_entry = config_template(channel_sim)

    # Set powering-on event always at t=0
    event = power_event("on", 0)
    ue["sim_events"].append(event)

    # Get a unique UE lifecycle with parameters previously defined
    cycle = ue_lifecycle(simulation_horizon, offtime, ontime)

    for time in cycle:
        # Update the configuration template with the unique lifecycle
        event = event_handler(time[0], time[1])
        ue["sim_events"].append(event)

    # Set powering-off event always at t=simulation_horizon
    event = power_event("off", simulation_horizon)
    ue["sim_events"].append(event)

    return ue, ue_db_entry, channel_sim, cycle


def ue_configure_alt(proto, simulation_horizon, cycle):
    # Choose what protocol will the UE simulate:
    if proto == "HTTP":
        # Case HTTP
        event_handler = http_event
        channel_sim = False
    elif proto == "RTP":
        # Case RTP
        event_handler = rtp_event
        channel_sim = True
    elif proto == "UDP":
        # Case UDP
        event_handler = udp_event
        channel_sim = True
    elif proto == "VoIP":
        # Case VoIP
        event_handler = voip_event
        channel_sim = False
    else:
        print("Unsupported Protocol: " + proto)
        return {}, {}

    # Create a UE sequence of events based on random
    # events following expontial distribution
    ue, ue_db_entry = config_template(channel_sim)

    # Set powering-on event always at t=0
    event = power_event("on", 0)
    ue["sim_events"].append(event)

    for time in cycle:
        # Update the configuration template with the unique lifecycle
        event = event_handler(time[0], time[1])
        ue["sim_events"].append(event)

    # Set powering-off event always at t=simulation_horizon
    event = power_event("off", simulation_horizon)
    ue["sim_events"].append(event)

    return ue, ue_db_entry, channel_sim


def plot_piecewise_constant_function(simulation_horizon, sorted_tuples, folder_path):
    # Check if the first element of the first tuple is 0, and insert (0, 0) if needed
    if sorted_tuples[0][0] != 0:
        sorted_tuples.insert(0, (0, 0))

    # Check if the first element of the last tuple is T, and append (T, 0) if needed
    if sorted_tuples[-1][0] != simulation_horizon:
        sorted_tuples.append((simulation_horizon, 0))

    t_values = [t for t, _ in sorted_tuples]
    n_values = [n for _, n in sorted_tuples]

    # Add an extra point at the end to make the last constant interval end at t_max + 1
    t_values.append(t_values[-1] + 1)
    n_values.append(n_values[-1])

    plt.step(t_values, n_values, where='post')
    plt.xlabel('Time')
    plt.ylabel('Active Users')
    plt.title('User Activity')
    plt.grid(True)

    # Set the vertical axis to show integer values
    plt.yticks(range(int(min(n_values)), int(max(n_values)) + 1))

    # Set the x-axis limits to remove dead space
    plt.xlim(min(t_values), max(t_values))

    # Add more grid lines to the horizontal axis
    num_values = 10  # You can adjust this value to control the grid frequency
    step_size = simulation_horizon / num_values
    plt.xticks(range(int(min(t_values)), int(max(t_values)) + 1, int(step_size)))

    figure_path = os.path.join(folder_path, 'user_activity.pdf')
    plt.savefig(figure_path)
    plt.close()


def augment_cycles(input_list):
    # Transform a list of acitivity tuples (start, end) into contrbution
    # list of tuples (start, 1), (end, -1), effectively doubling its size
    transformed_list = [(x, 1) for x, y in input_list] + [(y, -1) for x, y in input_list]
    return transformed_list


def create_acitivity_plot(folder_path, ue_cycles, simulation_horizon):
    # List of (start, end) -> List of (start, 1), (end, -1)
    augmented_cycles = [augment_cycles(input_list) for input_list in ue_cycles]

    # Sort the above list based on first element (time)
    sorted_cycles = [sorted(lst, key=lambda x: x[0]) for lst in augmented_cycles]

    # Merge partial contributions from each user
    merged_cycles = heapq.merge(*sorted_cycles, key=lambda x: x[0])

    # Transform it into list of tuples (t_i, +1), (t_i+1, -1), etc.
    sorted_lifecycle = [(x, y) for x, y in merged_cycles]

    # Aggregate user contributions
    cumsum = 0
    # Cumulative sum of a list of tuples' second elements
    aggregated_lifecycle = [(cycle[0], (cumsum := cumsum + cycle[1])) for cycle in sorted_lifecycle]

    # Plot aggregated user contribution list
    plot_piecewise_constant_function(simulation_horizon, aggregated_lifecycle, folder_path)


def get_config_content():
    text = f'''/* UE simulator configuration file version 2021-09-18
 * Copyright (C) 2015-2021 Amarisoft
 */
#define TDD            0 // Values: 0 (FDD), 1(TDD)
#define CELL_BANDWIDTH 20 // Values: 1.4 (1.4MHz), 3 (3MHz), 5 (5MHz), 10 (10MHz), 15 (15MHz), 20 (20MHz)
#define N_ANTENNA_DL   1 // Values: 1 (SISO), 2 (MIMO 2x2), 4 (MIMO 4x4)
#define N_ANTENNA_UL   1 // Values: 1, 2
#define UE_COUNT       {num_ue} // number of simulated UEs
#define CHANNEL_SIM    {int(channel_sim)} // Values: 0 (UE channel simulator disabled), 1 (UE channel simulator enabled)

{{
//  log_options: "all.level=debug,all.max_size=32",
  log_options: "all.level=none,all.max_size=0,mac.level=debug,mac.max_size=0",
  log_filename: "/tmp/ue0.log",

  /* Enable remote API and Web interface */
  com_addr: "0.0.0.0:9002",

//  include "rf_driver/config.cfg",
  include "rf_driver/config_sdr2.cfg",

  /* Each cell group must define cells of same type (lte, catm, nbiot or nr)
   * Cells of same type can be spread across multiple groups
   */
  cell_groups: [{{
    /* If true, allow the simulation of several UEs at the same time and
       allow dynamic UE creation from remote API */
#if CHANNEL_SIM == 1
    multi_ue: true,
    channel_sim: true,
#else
#if UE_COUNT > 1
    multi_ue: true,
#else
    multi_ue: false,
#endif
#endif

    cells: [
      {{
        bandwidth: CELL_BANDWIDTH,
#if TDD == 1
        dl_earfcn: 40620, /* DL center frequency: 2593 MHz (band 41) */
#else
        dl_earfcn: 3350,  /* DL center frequency: 2680 MHz (Band 7) */
#endif
        n_antenna_dl: N_ANTENNA_DL,
        n_antenna_ul: N_ANTENNA_UL,

        /* must be provided if multi_ue = true */
        global_timing_advance: -1, // -1: use the timing advance from the first received RAR

#if CHANNEL_SIM == 1
        position: [0, 0],
        antenna: {{
          type: "isotropic",
        }},
        ref_signal_power: 9,
        ul_power_attenuation: 120,
#endif

      }}
    ],

    /* If case your system has a high SNR and you are running high number of
     * UEs, enable this option to optimize PDCCH decoding and save CPU
     */
    pdcch_decode_opt: false,
    pdcch_decode_opt_threshold: 0.1,
  }}],
'''
    return text

############ MAIN ############
if __name__ == "__meain__":

    if len(sys.argv) > 1:
        try:
            num_ue = int(sys.argv[1])
        except ValueError:
            print("Argument 1 must be an integer.")
            sys.exit(1)
    else:
        # Set default value to 2
        num_ue = 10

    # Define UE lifecycle specifications: time horizon of 120s,
    # mean off-time, on-time 20s, 5s, respectively, as well as
    # protocol simulation; put the thumb on the scale for HTTP.
    proto_list = ["HTTP", "HTTP", "RTP", "UDP", "VoIP"]
    num_proto = len(proto_list)
    # Simulation duration in seconds
    simulation_horizon = 600
    # Average UE inactive time in seconds
    offtime = 30
    # Average UE active time in seconds
    ontime = 30
    ue_list = []
    ue_db = []
    ue_cycles = []
    channel_sim = True
    for _ in range(num_ue):
        # Get a specified amount of unique UEs
        # and their lifecycles of protocol activity
        proto = proto_list[3]  # proto_list[random.randint(0, num_proto - 1)]
        ue, ue_db_entry, ue_channel, ue_cycle = ue_configure(proto, simulation_horizon, offtime, ontime)
        ue_list.append(ue)
        ue_db.append(ue_db_entry)
        channel_sim |= ue_channel
        ue_cycles.append(ue_cycle)

    # Get the current timestamp and create a config folder
    # marked by the timestamps, where files will be stored
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    folder_path = f"config_{timestamp}"
    # Check if the folder exists, create it if necessary
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Create a graph featuring active users per time unit
    create_acitivity_plot(folder_path, ue_cycles, simulation_horizon)

    # Define the file name in the timestamped folder
    filename = os.path.join(folder_path, 'ue_db-test.cfg')
    # Print the JSON output with ue_db
    json_output = json.dumps(ue_db, indent=2)[1:-1]
    # Open the proto.mme.timestamp.cfg in write mode
    with open(filename, 'w') as file:
        # Redirect the print statement to write to the file
        print(f'ue_db: [{json_output}]', file=file)

    # Define the file name in the timestamped folder
    filename = os.path.join(folder_path, 'proto.ue.cfg')
    # Print the JSON output with ue_list
    json_output = json.dumps(ue_list, indent=2)[1:-1]
    # Open the proto.ue.timestamp.cfg in write mode
    with open(filename, 'w') as file:
        # Redirect the print statement to write to the file
        print(f'ue_list: [{json_output}]', file=file)

    # Define the file name in the timestamped folder
    filename = os.path.join(folder_path, 'ue-test.cfg')
    # Open the ue.timestamp.cfg in write mode
    with open(filename, 'w') as file:
        # Redirect the print statement to write to the file
        text = get_config_content()
        print(text, file=file)
        print(f'ue_list: [{json_output}],\n}}', file=file)

elif __name__ == "__main__":

    if len(sys.argv) > 1:
        try:
            num_ue = int(sys.argv[1])
        except ValueError:
            print("Argument 1 must be an integer.")
            sys.exit(1)
    else:
        # Set default value to 2
        num_ue = 10

    # Define UE lifecycle specifications: time horizon of 120s,
    # mean off-time, on-time 20s, 5s, respectively, as well as
    # protocol simulation; put the thumb on the scale for HTTP.
    proto_list = ["HTTP", "HTTP", "RTP", "UDP", "VoIP"]
    num_proto = len(proto_list)
    ue_list = []
    ue_db = []
    ue_cycles = []
    channel_sim = True
    ####################################################################################################################
    repetitions = 8
    ue_counts = [2, 4, 6] * repetitions
    activity_times = [2*60, 5*60, 8*60] * repetitions      # seconds
    simulation_horizon = sum(activity_times)
    ue_cycles = ue_lifecycle_alt(activity_times, ue_counts)
    for ue_cycle in ue_cycles:
        # Get a specified amount of unique UEs
        # and their lifecycles of protocol activity
        proto = proto_list[2]  # proto_list[random.randint(0, num_proto - 1)]
        ue, ue_db_entry, ue_channel = ue_configure_alt(proto, simulation_horizon, ue_cycle)
        ue_list.append(ue)
        ue_db.append(ue_db_entry)
        channel_sim |= ue_channel

    # Get the current timestamp and create a config folder
    # marked by the timestamps, where files will be stored
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    folder_path = f"config_{timestamp}"
    # Check if the folder exists, create it if necessary
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

    # Create a graph featuring active users per time unit
    create_acitivity_plot(folder_path, ue_cycles, simulation_horizon)

    # Define the file name in the timestamped folder
    filename = os.path.join(folder_path, 'ue_db-test.cfg')
    # Print the JSON output with ue_db
    json_output = json.dumps(ue_db, indent=2)[1:-1]
    # Open the proto.mme.timestamp.cfg in write mode
    with open(filename, 'w') as file:
        # Redirect the print statement to write to the file
        print(f'ue_db: [{json_output}]', file=file)

    # Define the file name in the timestamped folder
    filename = os.path.join(folder_path, 'proto.ue.cfg')
    # Print the JSON output with ue_list
    json_output = json.dumps(ue_list, indent=2)[1:-1]
    # Open the proto.ue.timestamp.cfg in write mode
    with open(filename, 'w') as file:
        # Redirect the print statement to write to the file
        print(f'ue_list: [{json_output}]', file=file)

    # Define the file name in the timestamped folder
    filename = os.path.join(folder_path, 'ue-test.cfg')
    # Open the ue.timestamp.cfg in write mode
    with open(filename, 'w') as file:
        # Redirect the print statement to write to the file
        text = get_config_content()
        print(text, file=file)
        print(f'ue_list: [{json_output}],\n}}', file=file)
