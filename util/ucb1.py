import numpy as np

from .RL import compute_rl_reward
from .parameters import PRBs


class UCB1:
    def __init__(self, num_arms, arm_correlations):
        self.num_arms = num_arms
        self.iterations = 0
        self.counts = [0] * num_arms
        self.avg_rewards = [0.0] * num_arms

        # Determine if arm correlations are considered
        self.arm_correlations = arm_correlations

        # When correlations are considered, self.counts[a] is not the number of times that arm 'a' is selected
        self.times_selected = [0] * num_arms

    def select_arm(self):
        ucb_indices = [0.0] * self.num_arms

        for arm in range(self.num_arms):
            if self.counts[arm] == 0:
                selected_arm = arm
                # self.print_debug_info(ucb_indices, selected_arm)
                self.times_selected[selected_arm] += 1
                return selected_arm

            exploitation = self.avg_rewards[arm]
            exploration = np.sqrt((2 * np.log(self.iterations) / self.counts[arm]))
            ucb_indices[arm] = exploitation + exploration

        max_ucb_value = max(ucb_indices)
        selected_arm = ucb_indices.index(max_ucb_value)  # returns smallest arm if ties exist

        # self.print_debug_info(ucb_indices, selected_arm)
        self.times_selected[selected_arm] += 1
        return selected_arm

    def print_debug_info(self, ucb_values, selected_arm):
        print(f"Counts: {self.counts}")
        print(f"Average Rewards: {self.avg_rewards}")
        print(f"UCB Values: {ucb_values}")
        print(f"Selected Arm: {selected_arm}")

    def single_arm_update(self, arm, reward):
        self.counts[arm] += 1
        new_counts = self.counts[arm]
        old_counts = new_counts - 1

        old_avg_reward = self.avg_rewards[arm]
        new_avg_reward = 1 / float(new_counts) * (old_avg_reward * old_counts + reward)
        self.avg_rewards[arm] = new_avg_reward

    def update(self, selected_arm, QoS_reward):

        # The selected arm is always updated regardless of correlations
        bandwidth = PRBs[selected_arm]
        reward = compute_rl_reward(bandwidth, QoS_reward)
        self.single_arm_update(selected_arm, reward)

        # if arm correlations are considered, also update correlated arms
        if self.arm_correlations:
            # If we did not meet the SLA, smaller arms/bandwidths would also fail
            if QoS_reward == 0:
                for arm in range(selected_arm):
                    bandwidth = PRBs[arm]
                    reward = compute_rl_reward(bandwidth, QoS_reward)
                    self.single_arm_update(arm, reward)
            # If we met the SLA, larger arms/bandwidths would also succeed
            if reward == 1:
                for arm in range(selected_arm + 1, self.num_arms):
                    bandwidth = PRBs[arm]
                    reward = compute_rl_reward(bandwidth, QoS_reward)
                    self.single_arm_update(arm, reward)

        # Algorithm just finished an iteration
        self.iterations += 1


# ------------------------------------------------- Main starts here ---------------------------------------------------
if __name__ == "__main__":

    # Set number of arms and their arm dependent delay to simulate rewards later on
    NUM_ARMS = 1000
    arm_dependent_delay = list(reversed(range(NUM_ARMS)))  # larger arms/bandwidths achieve smaller delay
    desired_delay_upper_bound = 2000

    # Create an instance of UCB1 with the specified number of arms and specify if arm correlations are considered
    ucb = UCB1(NUM_ARMS, True)

    num_rounds = 100000
    total_reward = 0
    for i in range(num_rounds):
        # Choose an arm
        arm_selected = ucb.select_arm()

        # Simulate a reward for the selected arm
        noise = np.random.normal(0, 1)
        delay = arm_dependent_delay[arm_selected] + noise
        if delay <= desired_delay_upper_bound:
            REWARD = 1
        else:
            REWARD = 0

        # Update the UCB1 model with the selected arm and reward
        ucb.update(arm_selected, REWARD)
        total_reward += REWARD

    print(f"Total reward is: {total_reward}")
    print(ucb.times_selected)
