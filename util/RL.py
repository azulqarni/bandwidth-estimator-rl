import math
import statistics
import numpy as np
from collections import defaultdict
from .parameters import *

# RL code does not work if state/context dimension changes
def compute_cost_of_action(action, cost_type):
    if cost_type == "exponential":
        cost = math.exp(action)
        return cost
    else:
        cost = action
        return cost


def compute_rl_reward(action, qos_reward, visualize=False):
    cost_of_action = compute_cost_of_action(action, type_of_cost)
    round_cost = cost_of_action + (1 - qos_reward) * QoS_cost_violation
    round_reward = -round_cost
    max_cost = PRBs[-1] + QoS_cost_violation
    min_cost = PRBs[0]
    min_reward = -max_cost
    max_reward = -min_cost
    round_reward = (round_reward - min_reward) / (max_reward - min_reward)
    if visualize:
        round_reward = -round_cost
    return round_reward


def compute_qos_reward(action, RL_reward):
    cost_of_action = compute_cost_of_action(action, type_of_cost)
    max_cost = PRBs[-1] + QoS_cost_violation
    min_cost = PRBs[0]
    min_reward = -max_cost
    max_reward = -min_cost
    round_reward = RL_reward * (max_reward - min_reward) + min_reward
    round_cost = -round_reward
    QoS_reward = 1 - (round_cost - cost_of_action) / QoS_cost_violation
    return QoS_reward


# Find most pulled arm for the policy of the second episode
# noinspection PyTypeChecker
def find_most_used_arm(trajectory_file, last_rounds):
    context_vs_arms = defaultdict(list)
    with open(trajectory_file, 'r') as f:
        data = [x.strip().split('\t') for x in f]
    data.pop(0)     # 0:BW - 1:Users - 2:MCS - 3:BSR - 4:QoS - 5:Reward
    data = np.array(data).astype(float)

    last_rounds = np.array(last_rounds).astype(int)
    last_rounds = last_rounds - 1

    for t in last_rounds:
        actual_arm = data[t, 0]
        arm = PRBs.index(actual_arm)

        users = data[t, 1]
        mcs = data[t, 2]
        bsr = data[t, 3]

        actual_context = [users, mcs, bsr]
        context = indexify_context(actual_context)

        context = tuple(context)
        context_vs_arms[context].append(arm)

    context_vs_most_used_arm = {}
    for key in context_vs_arms.keys():
        temp_list = context_vs_arms[key]
        mode = statistics.mode(temp_list)
        context_vs_most_used_arm[key] = mode
    return context_vs_most_used_arm


# second policy is the first epsilon-soft policy
def second_policy(state, context_vs_most_used_arm):
    arms = list(range(num_arms))
    high_prob = 1 - epsilon + epsilon / num_arms
    low_prob = epsilon / num_arms
    probabilities = num_arms*[low_prob]
    if state in context_vs_most_used_arm.keys():
        best_action = context_vs_most_used_arm[state]
    else:
        # if state did not occur, be optimistic and choose the smallest arm
        best_action = 0
    probabilities[best_action] = high_prob
    print(f"[RL] Second policy: Actions {PRBs} drawn using pmf {probabilities}")
    selected_action = np.random.choice(arms, 1, True, probabilities)
    selected_action = int(selected_action)
    return selected_action


def policy_iteration(trajectory_file, last_rounds, Q, returns):
    with open(trajectory_file, 'r') as f:
        data = [x.strip().split('\t') for x in f]
    data.pop(0)     # 0:BW - 1:Users - 2:MCS - 3:BSR - 4:QoS - 5:Reward
    data = np.array(data).astype(float)

    last_rounds = np.array(last_rounds).astype(int)
    last_rounds = last_rounds - 1

    # Approximate Q values
    # Find first time that state-action pair occurred in the episode
    first_times = {}
    for t in last_rounds:
        actual_action = data[t, 0]
        actual_state = [data[t, 1], data[t, 2], data[t, 3]]
        action = PRBs.index(actual_action)
        state = indexify_context(actual_state)
        state_action = tuple([state[0], state[1], state[2], action])
        if state_action not in first_times.keys():
            first_times[state_action] = t

    for key in first_times.keys():
        G = 0
        k = 0
        mean_round_reward = 0
        for t in last_rounds:
            if t < first_times[key]:
                continue
            round_reward = compute_rl_reward(data[t, 0], data[t, 5])
            G += gamma ** k * round_reward
            k += 1
            mean_round_reward += round_reward
        # START MODIFICATION HERE
        # project to T rounds to accurately describe G
        mean_round_reward = mean_round_reward / k
        T = len(last_rounds)
        for t in range(T, T + first_times[key]):
            G += gamma ** k * mean_round_reward
            k += 1
        # END MODIFICATION HERE
        returns[key].append(G)
        Q[key] = sum(returns[key])/len(returns[key])

    return Q, returns


def epsilon_soft_policy(state, Q):
    best_action_candidates = []
    candidate_Q_values = []
    state = tuple(state)
    for action in range(num_arms):
        state_action = state + (action,)
        if state_action in Q.keys():
            best_action_candidates.append(action)
            candidate_Q_values.append(Q[state_action])

    # if this state has never occurred before, assign high probability to the median action/bandwidth
    if not best_action_candidates:
        print(f"[RL] State never occured before, assigning high probability to the smallest arm...")
        # if state did not occur, be optimistic and choose the smallest arm
        best_action = 0
    # if state has occured before, assign high probability to the action/bandwidth with the highest Q value
    else:
        print(f"[RL] Candidate arms {best_action_candidates}")
        print(f"[RL] Q values {candidate_Q_values}")
        Q_max = max(candidate_Q_values)
        best_action_index = candidate_Q_values.index(Q_max)  # returns smallest action in case of ties
        best_action = best_action_candidates[best_action_index]

    high_prob = 1 - epsilon + epsilon / num_arms
    low_prob = epsilon / num_arms

    probabilities = num_arms*[low_prob]
    probabilities[best_action] = high_prob
    selected_action = np.random.choice(list(range(num_arms)), 1, True, probabilities)
    selected_action = int(selected_action)
    print(f"[RL] Actions {PRBs} drawn using pmf {probabilities}")
    return selected_action


def update_transition_matrix(trajectory_file, last_rounds, state_transition_count):
    with open(trajectory_file, 'r') as f:
        data = [x.strip().split('\t') for x in f]
    data.pop(0)     # 0:BW - 1:Users - 2:MCS - 3:BSR - 4:QoS - 5:Reward
    data = np.array(data).astype(float)

    last_rounds = np.array(last_rounds).astype(int)
    last_rounds = last_rounds - 1

    # count times state_action (s,a) resulted to newstate_reward (s',r) in the new data
    for t in last_rounds[:-1]:

        # find the state_action (s,a)
        actual_action = data[t, 0]
        action = indexify_bandwidth(actual_action)
        actual_state = [data[t, 1], data[t, 2], data[t, 3]]
        state = indexify_context(actual_state)
        state.pop(0)    # remove number of users
        state_action = tuple([state[0], state[1], action])  # MCS, BSR, bandwdith (indices)

        # find the newstate_reward (s',r)
        QoS_reward = data[t, 5]
        RL_reward = compute_rl_reward(actual_action, QoS_reward)

        actual_newstate = [data[t + 1, 1], data[t + 1, 2], data[t + 1, 3]]
        newstate = indexify_context(actual_newstate)
        newstate.pop(0)  # remove number of users

        newstate_reward = tuple([newstate[0], newstate[1], RL_reward])  # MCS, BSR, RL_reward (indices except RL reward)
        tuple_of_two_tuples = (state_action, newstate_reward)
        state_transition_count[tuple_of_two_tuples] += 1

    fake_state_transition_count = state_transition_count.copy()
    # Extend transition counts by exploiting arm correlations
    for key in state_transition_count.keys():
        state_action = key[0]
        newstate_reward = key[1]

        # Find QoS reward
        RL_reward = newstate_reward[2]
        bandwidth = PRBs[state_action[2]]
        QoS_reward = compute_qos_reward(bandwidth, RL_reward)

        # begin extending
        current_count = state_transition_count[key]
        if QoS_reward == 1:
            # assume that all higher bandwidths would also meet QoS, result to same newMCS and slightly better newBSR
            for action in range(state_action[2] + 1, len(PRBs)):
                # new considered state action pair is the same but with different action
                state_action_new = list(key[0])
                state_action_new[2] = action

                # new newstate_reward is the same but with smaller BSR and reward that reflects the action reward
                newstate_reward_new = list(key[1])
                newstate_reward_new[1] = max(key[1][1] - 1, 0)
                RL_reward_new = compute_rl_reward(PRBs[action], 1)
                newstate_reward_new[2] = RL_reward_new

                state_action_new = tuple(state_action_new)
                newstate_reward_new = tuple(newstate_reward_new)
                tuple_of_two_tuples_new = tuple([state_action_new, newstate_reward_new])
                fake_state_transition_count[tuple_of_two_tuples_new] += current_count
        else:
            # assume that all lower bandwidths would also not meet QoS and consider same newMCS slightly worse newBSR
            for action in range(0, state_action[2]):
                # new considered state action pair is the same but with different action
                state_action_new = list(key[0])
                state_action_new[2] = action

                # new newstate_reward is the same but with larger BSR and reward that reflects the action reward
                newstate_reward_new = list(key[1])
                newstate_reward_new[1] = min(key[1][1] + 1, len(BSRs) - 1)
                RL_reward_new = compute_rl_reward(PRBs[action], 0)
                newstate_reward_new[2] = RL_reward_new

                state_action_new = tuple(state_action_new)
                newstate_reward_new = tuple(newstate_reward_new)
                tuple_of_two_tuples_new = tuple([state_action_new, newstate_reward_new])
                fake_state_transition_count[tuple_of_two_tuples_new] += current_count

    # count the number of times that each state_action pair in fake_state_transition_count appears
    fake_state_action_count = defaultdict(int)
    for key in fake_state_transition_count.keys():
        state_action = key[0]
        fake_state_action_count[state_action] += fake_state_transition_count[key]

    # fill up the fake_state_transition_count matrix in the places where a whole row is empty
    for mcs in range(len(MCSs)):
        for bsr in range(len(BSRs)):
            for w in range(len(PRBs)):
                state_action = tuple([mcs, bsr, w])
                # if this state_action pair did not receive value, then whole row is empty so fill it up
                if fake_state_action_count[state_action] == 0:
                    # be optimistic and assign P(mcs', bsr', r | mcs, bsr, a) = 1 if mcs'=mcs bsr'= 0 and r = rmax(a)
                    # to do simply put count = 1 only for the above state_action , newstate_reward pair
                    optimistic_reward = compute_rl_reward(PRBs[w], 1)
                    newstate_reward = tuple([mcs, 0, optimistic_reward])
                    tuple_of_two_tuples = tuple([state_action, newstate_reward])
                    fake_state_transition_count[tuple_of_two_tuples] += 1
                    fake_state_action_count[state_action] += 1

    # Now compute the probability matrix using the fake_state_transition_count matrix
    probability_matrix = defaultdict(float)
    for key in fake_state_transition_count.keys():
        state_action = key[0]
        probability_matrix[key] = fake_state_transition_count[key] / fake_state_action_count[state_action]

    # # Check if probability matrix rows sum to 1 as it should be the case for every stochastic matrix
    # for mcs in range(len(MCSs)):
    #     for bsr in range(len(BSRs)):
    #         for w in range(len(PRBs)):
    #             s = 0
    #             state_action = tuple([mcs, bsr, w])
    #             for new_mcs in range(len(MCSs)):
    #                 for new_bsr in range(len(BSRs)):
    #                     # The possible rewards are only two
    #                     reward1 = compute_rl_reward(PRBs[w], 1)
    #                     reward2 = compute_rl_reward(PRBs[w], 0)
    #
    #                     newstate_reward1 = tuple([new_mcs, new_bsr, reward1])
    #                     newstate_reward2 = tuple([new_mcs, new_bsr, reward2])
    #
    #                     tuple_of_two_tuples1 = tuple([state_action, newstate_reward1])
    #                     tuple_of_two_tuples2 = tuple([state_action, newstate_reward2])
    #                     p1 = probability_matrix[tuple_of_two_tuples1]
    #                     p2 = probability_matrix[tuple_of_two_tuples2]
    #                     if p1 < 0 or p2 < 0 or p1 > 1 or p2 > 1:
    #                         print(f"[RL] Error! Transition matrix has an element not in [0,1]")
    #                     s += p1 + p2
    #             if s != 1:
    #                 print(f"[RL] Error! The sum of a row of the transition matrix is {s}!")
    #
    # total_elements = len(MCSs)*len(BSRs)*len(PRBs)*len(MCSs)*len(BSRs)*2
    # if len(probability_matrix) != total_elements:
    #     print(f"[RL] Error! The len of probability_matrix is {len(probability_matrix)} instead of {total_elements}")
    # print(f"[RL] The probability_matrix is {probability_matrix}")
    return probability_matrix, state_transition_count


def value_iteration(P):
    theta = 0.5
    state_values = defaultdict(float)
    max_deviation = theta + 1

    while max_deviation > theta:
        max_deviation = 0
        # scan all states
        for mcs in range(len(MCSs)):
            for bsr in range(len(BSRs)):
                state = tuple([mcs, bsr])
                previous_state_value = state_values[state]
                candidate_values = []

                # for each state scan all actions
                for w in range(len(PRBs)):
                    total = 0
                    for new_mcs in range(len(MCSs)):
                        for new_bsr in range(len(BSRs)):
                            for qos_reward in range(2):
                                state_action = tuple([mcs, bsr, w])

                                RL_reward = compute_rl_reward(PRBs[w], qos_reward)
                                newstate = tuple([new_mcs, new_bsr])
                                newstate_reward = tuple([new_mcs, new_bsr, RL_reward])

                                tuple_of_two_tuples = tuple([state_action, newstate_reward])
                                transition_prob = P[tuple_of_two_tuples]

                                term = transition_prob*(RL_reward + gamma*state_values[newstate])
                                total += term
                    candidate_values.append(total)
                state_values[state] = max(candidate_values)
                max_deviation = max(max_deviation, abs(previous_state_value - state_values[state]))

    # find deterministic policy
    best_action = defaultdict(int)
    # scan all states
    for mcs in range(len(MCSs)):
        for bsr in range(len(BSRs)):
            state = tuple([mcs, bsr])
            candidate_values = []

            # for each state scan all actions
            for w in range(len(PRBs)):
                total = 0
                for new_mcs in range(len(MCSs)):
                    for new_bsr in range(len(BSRs)):
                        for qos_reward in range(2):
                            state_action = tuple([mcs, bsr, w])

                            RL_reward = compute_rl_reward(PRBs[w], qos_reward)
                            newstate = tuple([new_mcs, new_bsr])
                            newstate_reward = tuple([new_mcs, new_bsr, RL_reward])

                            tuple_of_two_tuples = tuple([state_action, newstate_reward])
                            transition_prob = P[tuple_of_two_tuples]

                            term = transition_prob * (RL_reward + gamma * state_values[newstate])
                            total += term
                candidate_values.append(total)
            winner = candidate_values.index(max(candidate_values))
            best_action[state] = winner

    return best_action


def epsilon_soft_policy_select(best_action):
    print(f"[RL] Best action is: {PRBs[best_action]} PRBs")
    high_prob = 1 - epsilon + epsilon / num_arms
    low_prob = epsilon / num_arms

    probabilities = num_arms*[low_prob]
    probabilities[best_action] = high_prob
    selected_action = np.random.choice(list(range(num_arms)), 1, True, probabilities)
    selected_action = int(selected_action)
    return selected_action


