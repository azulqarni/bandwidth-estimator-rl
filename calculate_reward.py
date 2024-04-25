import sys
import time
import numpy as np
import paramiko
from statistics import mean
from .logflatten import remote_params
from .parameters import *
from .liveness import ue_ip_addresses

estimated_dl_delay = 15  # in ms

def log_packet_delays(ips):
    packet_size = udp_payload

    try:
        # Create an SSH client
        ssh_client = paramiko.SSHClient()

        _, _, _, remote_host, remote_username, remote_auth_key, _ = remote_params('mme')

        # Load the private key for authentication
        private_key = paramiko.Ed25519Key(filename=remote_auth_key)

        # Auto-add the remote server's host key (this is insecure, and you should verify the host key in production)
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the remote server
        ssh_client.connect(remote_host, username=remote_username, pkey=private_key)

        for ip_address in ips:
            # Execute the remote script in the background
            command = f'/root/rtt.sh {ip_address} {packet_size} > /dev/null 2>&1 &'
            _, _, _ = ssh_client.exec_command(command)

        # Close the SSH connection
        ssh_client.close()

        return

    except paramiko.AuthenticationException as auth_exception:
        print(f"Authentication failed: {auth_exception}")
    except paramiko.SSHException as ssh_exception:
        print(f"SSH connection failed: {ssh_exception}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the SSH connection if it's still open
        if ssh_client.get_transport() is not None:
            ssh_client.close()


def fetch_packet_delays_and_stop_logging(ip_addresses):
    try:
        # Create an SSH client
        ssh_client = paramiko.SSHClient()

        _, _, _, remote_host, remote_username, remote_auth_key, _ = remote_params('mme')

        # Load the private key for authentication
        private_key = paramiko.Ed25519Key(filename=remote_auth_key)

        # Auto-add the remote server's host key (this is insecure, and you should verify the host key in production)
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Connect to the remote server
        ssh_client.connect(remote_host, username=remote_username, pkey=private_key)

        # Terminate BS to UE ping
        _, _, _ = ssh_client.exec_command('/usr/bin/killall -15 ping')

        output_list = []

        # Obtain the remote RTT values
        for ip_address in ip_addresses:
            stdin, stdout, stderr = ssh_client.exec_command(f'/usr/bin/cat /root/packet_delays_{ip_address}.log')
            # Parse the stdout into a list
            output = stdout.read().decode().splitlines()
            output_list.append([float(val) - estimated_dl_delay for val in output])

        # Close the SSH connection
        ssh_client.close()

        # Return the RTT delays (list of floats)
        return output_list

    except paramiko.AuthenticationException as auth_exception:
        print(f"Authentication failed: {auth_exception}")
    except paramiko.SSHException as ssh_exception:
        print(f"SSH connection failed: {ssh_exception}")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # Close the SSH connection if it's still open
        if ssh_client.get_transport() is not None:
            ssh_client.close()


def evaluate_qos(packet_delays_lists):
    if not packet_delays_lists:
        print(f"[calculate_reward] No ping responses received, packet delays set to a very high value")
        QoS_metric = round_interval * 1000
        r = 0
        return QoS_metric, r

    # Per user processing
    num_of_users = len(packet_delays_lists)
    user_metrics = []
    for u in range(num_of_users):
        user_packet_delays = packet_delays_lists[u]
        if user_packet_delays:
            if desired_QoS == "avg_packet_delay":
                user_metric = mean(user_packet_delays)
                user_metrics.append(user_metric)
            elif desired_QoS == "tail_packet_delay":
                user_metric = np.percentile(user_packet_delays, 90)
                user_metrics.append(user_metric)
        else:
            print(f"[calculate_reward] No ping responses received for user {u}, packet delays set to a very high value")
            user_metric = round_interval * 1000
            user_metrics.append(user_metric)

    # NS-level processing
    QoS_metric = max(user_metrics)
    r = 1 if QoS_metric <= Q_target_value else 0
    return QoS_metric, r


if __name__ == "__main__":
    ips = ue_ip_addresses(True)
    log_packet_delays(ips)  # UE IP address, packet size
    time.sleep(5)  # argument in seconds
    delays = fetch_packet_delays_and_stop_logging(ips)
    print(delays)  # packet delays are in ms
    Q, reward = evaluate_qos(delays)
    print(Q)
    print(reward)
