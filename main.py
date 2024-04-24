import sys
from .util.logflatten import remove_all_files_from_directory
from .util.ucb1 import *
from .util.RL import *
from .util.liveness import ws_set_bandwidth, calculate_context
from .util.calculate_reward import *
from datetime import datetime
from collections import defaultdict
import time
import os.path

now = datetime.now()
timestring = now.strftime("at %H:%M on %m/%d")
print(f"[main] Program started {timestring}")
trajectories_folder = './trajectories'
timestring = now.strftime("%Y%m%d%H%M")
trajectory_file = os.path.join(trajectories_folder, timestring + "_trajectory.txt")
file1 = open(trajectory_file, "w")
file1.write(f"BW\tUsers\tMCS\tBSR\tDelay\tReward\t{algorithm}\n")
file1.close()

# Keep track of the number of times a specific number of users was encountered
users_vs_counts = defaultdict(int)

# Keep track of the round number of the most recent rounds_per_episode rounds that a specific number of users occured
users_vs_last_rounds = defaultdict(list)

# Intialization for UCB1 (whenever a new number of users appears create new UCB1 instance)
ucb1_objects = np.empty(tuple(num_context_component_values), dtype=UCB1)

# policy iteration
returns = defaultdict(list)
Q = {}

# value iteration
state_transition_count = defaultdict(lambda: defaultdict(int))
best_action_map = defaultdict(lambda: defaultdict(int))  # best action vs state for each number of users

t = 0
while True:
    round_start = time.time()
    t += 1
    print(f"[main] Start of round {t}")

    # Obtain the current actual state/context
    actual_context, num_alive_users = calculate_context()
    end_time = time.time()
    time_taken_context = end_time - round_start
    print(f"[main] State/context retrieval took {time_taken_context:.3f} seconds")

    # Return the indices of the actual state/context
    context = indexify_context(actual_context)
    # Do not peform adaptation, consider a single state
    if algorithm == "no_adaptation":
        context = [0, 0, 0]
    user_bound = Users[context[0]]
    print(f"[main] [Users, Avg_UL_MCS, Sum_UL_BSR ] = {actual_context} --> {context}")

    # Exit episode if all users are disconnected based on the current state/context
    if num_alive_users == 0:
        print("[main] All users powered off.")
        break

    # Number of rounds that this number of users occurred
    users_vs_last_rounds[context[0]].append(t)
    users_vs_counts[context[0]] += 1
    users_rounds = users_vs_counts[context[0]]
    if users_rounds <= initial_rounds:
        episode_of_users = 1
        round_of_users = users_rounds
    else:
        temp_rounds = users_rounds - initial_rounds
        episode_of_users = -(temp_rounds // -rounds_per_episode) + 1  # ceil integral division
        round_of_users = temp_rounds % rounds_per_episode
    print(f"[main] This is round {round_of_users} of episode {episode_of_users} for [users <= {user_bound}]")

    # Select action
    start_time = time.time()

    if algorithm == "UCB1_only" or algorithm == "no_adaptation":

        # Construct a new UCB1 object for this context if one does not already exist
        if not ucb1_objects[tuple(context)]: ucb1_objects[tuple(context)] = UCB1(num_arms, arm_correlations)

        # Refer to current ucb1 object as 'ucb1' for convenience
        ucb1 = ucb1_objects[tuple(context)]

        # Choose an arm
        selected_action = ucb1.select_arm()

    elif algorithm == "policy_iteration":

        if episode_of_users <= 1:

            # Employ UCB1 algorithm
            if not ucb1_objects[tuple(context)]: ucb1_objects[tuple(context)] = UCB1(num_arms, arm_correlations)

            # Refer to current ucb1 object as 'ucb1' for convenience
            ucb1 = ucb1_objects[tuple(context)]

            # Choose an arm
            selected_action = ucb1.select_arm()

        elif episode_of_users <= 2:

            # call the second policy, i.e., the first epsilon-soft policy
            selected_action = second_policy(tuple(context), context_vs_most_used_arm)
        else:

            # Select action using the updated epsilon-soft policy given the current state and Q matrix
            selected_action = epsilon_soft_policy(context, Q)

    elif algorithm == "value_iteration":

        if episode_of_users <= 1:

            # Employ UCB1 algorithm
            if not ucb1_objects[tuple(context)]: ucb1_objects[tuple(context)] = UCB1(num_arms, arm_correlations)

            # Refer to current ucb1 object as 'ucb1' for convenience
            ucb1 = ucb1_objects[tuple(context)]

            # Choose an action
            selected_action = ucb1.select_arm()

        else:
            # select best action computed by value iteration with high_prob and the rest with low_prob
            mini_state = tuple([context[1], context[2]])
            best_action = best_action_map[context[0]][mini_state]
            selected_action = epsilon_soft_policy_select(best_action)

    # Find actual bandwidth in PRBs from selected action/arm
    actual_bandwidth = unindexify_bandwidth(selected_action)
    print(f"[main] Allocated Bandwidth = {actual_bandwidth} PRBs")

    # Enforce selected action/arm, i.e., bandwidth update via Amarisoft API
    ws_set_bandwidth(actual_bandwidth)
    end_time = time.time()
    time_taken_arm = end_time - start_time
    if debug_mode: print(f"[main] Arm selection took: {time_taken_arm:.3f} seconds")

    # clear contents of "logs" directory
    remove_all_files_from_directory(logs)

    # Start logging the output of ping command to collect packet delays of all connected users
    ips = ue_ip_addresses(True)
    log_packet_delays(ips)
    try:
        # Sleep for round_interval seconds to find the effect of the action on multiple packets
        print(f"[main] Sleeping for {round_interval} seconds...")
        time.sleep(round_interval)
    except KeyboardInterrupt:
        print(f"[main] Keyboard interrupt, killing ping command and resetting to 90 PRBs...")
        packet_delays = fetch_packet_delays_and_stop_logging(ips)
        ws_set_bandwidth(90)
        now = datetime.now()
        timestring = now.strftime("at %H:%M on %m/%d")
        print(f"[main] Program ended {timestring}")
        sys.exit(130)

    # Extract packet delays and stop pinging
    startt_time = time.time()
    packet_delays = fetch_packet_delays_and_stop_logging(ips)

    # Evaluate the QoS of the current state-action pair based on the logged packet delays
    QoS_metric, QoS_reward = evaluate_qos(packet_delays)

    # Compute RL reward
    RL_round_reward = compute_rl_reward(actual_bandwidth, QoS_reward)

    print(f"[main] QoS metric = {QoS_metric} ms")
    print(f"[main] QoS reward = {QoS_reward}")
    print(f"[main] RL reward = {RL_round_reward}")
    endt_time = time.time()
    if debug_mode: print(f"[main] Evaluation time {endt_time -startt_time}s")

    # Log the tuple (action, state, QoS metric, reward) and add it to the current trajectory file of the policy
    start_time = time.time()
    file1 = open(trajectory_file, "a")
    actual_context[1] = round(actual_context[1], 2)
    QoS_metric = round(QoS_metric, 2)
    reward = round(QoS_reward, 4)
    file1.write(f"{actual_bandwidth}\t{actual_context[0]}\t{actual_context[1]}\t{actual_context[2]}\t{QoS_metric}"
                f"\t{reward}\n")
    file1.close()

    if episode_of_users <= 1 or algorithm == "UCB1_only" or algorithm == "no_adaptation":
        # Update the UCB1 object with the selected arm and reward
        ucb1.update(selected_action, QoS_reward)

    end_time = time.time()
    if debug_mode: print(f"Logging and updating arm took {end_time - start_time}")
    # sleep for inactivity_timer in enb.cfg to ensure that inactive users switch to RRC idle state
    time.sleep(0.1)

    # Record total round duration
    round_end = time.time()
    time_taken = round_end - round_start
    print(f"[main] Total round duration = {time_taken :.3f} seconds\n")

    # Check if an episode has just been completed
    if algorithm == "UCB1_only" or algorithm == "no_adaptation":
        continue
    if algorithm == "policy_iteration":
        if users_rounds == initial_rounds:
            # The first episode has just been completed
            # Find most used arm for each occured context to find the first epsilon-soft policy (second policy overall)
            context_vs_most_used_arm = find_most_used_arm(trajectory_file, users_vs_last_rounds[context[0]])
            users_vs_last_rounds[context[0]].clear()
            print(f"[main] Episode {episode_of_users} for [users <= {user_bound}] completed. "
                  f"Found the most used arms for each context...\n\n")
        elif users_rounds >= initial_rounds and (users_rounds - initial_rounds) % rounds_per_episode == 0:
            # Another episode has been completed so perform policy iteration to improve current epsilon-soft policy
            # Receive the Q values and total rewards for each state-action pair, and then update them
            Q, returns = policy_iteration(trajectory_file, users_vs_last_rounds[context[0]], Q, returns)
            users_vs_last_rounds[context[0]].clear()
            print(f" Episode {episode_of_users} for [users <= {user_bound}] completed. "
                  f"Performed policy iteration to improve epsilon-soft policy.\n")
    if algorithm == "value_iteration":
        if users_rounds >= initial_rounds and (users_rounds - initial_rounds) % rounds_per_episode == 0:
            # An episode has been completed so perform value iteration to improve current epsilon-soft policy

            # First update transition probability matrix and the state transition count
            P, state_transition_count[context[0]] = \
                update_transition_matrix(trajectory_file, users_vs_last_rounds[context[0]],
                                         state_transition_count[context[0]])
            users_vs_last_rounds[context[0]].clear()

            best_action_map[context[0]] = value_iteration(P)
            print(f"[main] Best action map for [users <= {user_bound}] is: {best_action_map[context[0]]}")
            print(f"[main] Episode {episode_of_users} for [users <= {user_bound}] completed. "
                  f"Performed value iteration to improve epsilon-soft policy.\n")


# Reset to 90 PRBs and terminate program
ws_set_bandwidth(90)
now = datetime.now()
timestring = now.strftime("at %H:%M on %m/%d")
print(f"[main] Program ended {timestring}")
