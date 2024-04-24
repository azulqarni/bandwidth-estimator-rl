import shutil
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt
import os.path
from RL import compute_rl_reward
from parameters import *

filename = "202311200253_trajectory"
print(f"Plotting {filename}...")

params = {'font.size': 16, 'font.family': 'serif'}
plt.rcParams.update(params)
plt.rcParams["axes.prop_cycle"] = plt.cycler("color", plt.cm.tab10.colors)

trajectories_folder = './trajectories'
trajectory_file = os.path.join(trajectories_folder, filename + '.txt')

plots_folder = './plots/' + filename
# Check whether the specified path exists or not
isExist = os.path.exists(plots_folder)
if not isExist:
    os.makedirs(plots_folder)
    print("Creating a plots folder for this trajectory file...")

# Copy trajectory to its plot folder
shutil.copy(trajectory_file, plots_folder)

# Read data of trajectory_file
with open(trajectory_file, 'r') as f: data = [x.strip().split('\t') for x in f]
data.pop(0)     # 0:BW - 1:Users - 2:MCS - 3:BSR - 4:QoS - 5:Reward
data = np.array(data).astype(float)
rounds = np.arange(len(data))
actions = data[:, 0]
users = data[:, 1].astype(int)
mcs = data[:, 2]
bsrs = data[:, 3]
QoS = data[:, 4]
QoS_rewards = data[:, 5].astype(int)

RL_rewards = np.empty(len(data))
for t in rounds:
    RL_rewards[t] = compute_rl_reward(actions[t], QoS_rewards[t])


cumsum_bandwidth = np.cumsum(actions)
current_avg_bandwidth = np.divide(cumsum_bandwidth, rounds + 1)
cumsum_QoS_rewards = np.cumsum(QoS_rewards)
current_success_percentage = np.divide(cumsum_QoS_rewards, rounds + 1)
cumsum_RL_rewards = np.cumsum(RL_rewards)
current_reward_rate = np.divide(cumsum_RL_rewards, rounds + 1)

# Find the rounds for each users value
users_vs_rounds = defaultdict(list)
for t in rounds:
    actual_state = [users[t], mcs[t], bsrs[t]]
    state = indexify_context(actual_state)
    UEs = state[0]
    UEs_bound = Users[UEs]
    users_vs_rounds[UEs_bound].append(t)

# Plots over time
marker_size = 10

plt.figure(figsize=(8, 4))
plt.step(rounds, users)
plt.xlabel('Round')
plt.ylabel('Active Users')
plt.yticks(users)
filename = 'Users_over_time.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')


plt.figure(figsize=(8, 4))
for key in users_vs_rounds.keys():
    current_rounds = users_vs_rounds[key]
    plt.scatter(current_rounds, current_success_percentage[current_rounds], s=marker_size, label=f"users $\leq$ {key}")
    plt.legend()
plt.xlabel('Round')
plt.ylabel('Total QoS Success (%)')
filename = 'QoS_Success_over_time.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')


plt.figure(figsize=(8, 4))
for key in users_vs_rounds.keys():
    current_rounds = users_vs_rounds[key]
    plt.scatter(current_rounds, cumsum_RL_rewards[current_rounds], s=marker_size, label=f"users $\leq$ {key}")
    plt.legend()
plt.xlabel('Round')
plt.ylabel('Total Reward')
plt.ticklabel_format(axis='both', style='sci', scilimits=(0, 4))
filename = 'Total_Reward_over_time.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')

plt.figure(figsize=(8, 4))
for key in users_vs_rounds.keys():
    current_rounds = users_vs_rounds[key]
    plt.scatter(current_rounds, current_avg_bandwidth[current_rounds], s=marker_size, label=f"users $\leq$ {key}")
    plt.legend()
plt.xlabel('Round')
plt.ylabel('AVg. PRBs')
filename = 'Bandwidth_over_time.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')

plt.figure(figsize=(8, 4))
for key in users_vs_rounds.keys():
    current_rounds = users_vs_rounds[key]
    plt.scatter(current_rounds, actions[current_rounds], s=marker_size, label=f"users $\leq$ {key}")
    plt.legend()
plt.xlabel("Round")
plt.ylabel("PRBs")
filename = 'PRBS_over_time.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')

# Plots over episodes
episode_QoS_success_percentage = defaultdict(list)
episode_RL_reward = defaultdict(list)
episode_avg_bw = defaultdict(list)

for key in users_vs_rounds.keys():
    current_rounds = users_vs_rounds[key]
    current_rounds = np.array(current_rounds)
    lists_of_rounds = []
    for i in range(0, len(current_rounds), rounds_per_episode):
        episode_list = current_rounds[i:i+rounds_per_episode]
        lists_of_rounds.append(episode_list)

    for current_list in lists_of_rounds:
        QoS_success = 0
        RL_reward = 0
        avg_bw = 0
        for t in current_list:
            QoS_success += QoS_rewards[t]
            RL_reward += RL_rewards[t]
            avg_bw += actions[t]

        QoS_success = QoS_success / len(current_list)
        RL_reward = RL_reward / len(current_list)
        avg_bw = avg_bw / len(current_list)

        episode_QoS_success_percentage[key].append(QoS_success)
        episode_RL_reward[key].append(RL_reward)
        episode_avg_bw[key].append(avg_bw)

plt.figure(figsize=(8, 4))
count = 1
number_of_keys = len(episode_QoS_success_percentage.keys())
for key in episode_QoS_success_percentage.keys():
    current_list = episode_QoS_success_percentage[key]
    current_list = np.array(current_list) * 100
    current_episodes = range(len(current_list))
    plt.subplot(1, number_of_keys, count)
    plt.bar(current_episodes, current_list)
    plt.title(f"users $\leq$ {key}")
    plt.xlabel('Episode')
    plt.ylabel('QoS Success (%)')
    # plt.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
    count += 1
plt.subplots_adjust(wspace=0.6)
filename = 'QoS_Success_per_episode.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')


plt.figure(figsize=(8, 4))
count = 1
number_of_keys = len(episode_RL_reward.keys())
for key in episode_RL_reward.keys():
    current_list = episode_RL_reward[key]
    current_list = np.array(current_list).astype(float)
    current_episodes = range(len(current_list))
    plt.subplot(1, number_of_keys, count)
    plt.bar(current_episodes, current_list)
    plt.title(f"users $\leq$ {key}")
    plt.xlabel('Episode')
    plt.ylabel('RL Reward per Episode')
    # plt.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
    count += 1
plt.subplots_adjust(wspace=0.6)
filename = 'RL_reward_per_episode.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')

# Plots over last episode
plt.figure(figsize=(8, 4))
string_list = map(str, episode_QoS_success_percentage.keys())
string_list = [f"$\leq$ {i}" for i in string_list]
values_list = [episode_QoS_success_percentage[key][-1] for key in episode_QoS_success_percentage.keys()]
plt.bar(string_list, values_list)
plt.xlabel("Users")
plt.ylabel('QoS Success (%)')
plt.title('Last episode')
filename = 'QoS_Success_last_episode.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')


plt.figure(figsize=(8, 4))
string_list = map(str, episode_avg_bw.keys())
string_list = [f"$\leq$ {i}" for i in string_list]
values_list = [episode_avg_bw[key][-1] for key in episode_avg_bw.keys()]
plt.bar(string_list, values_list)
plt.xlabel("Users")
plt.ylabel('Avg. PRBs')
plt.title('Last episode')
filename = 'Avg_PRBs_last_episode.pdf'
plt.tight_layout()
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')


# Plots per number of users
plt.figure(figsize=(8, 4))
string_list = map(str, episode_QoS_success_percentage.keys())
string_list = [f"$\leq$ {i}" for i in string_list]
values_list = [100*sum(episode_QoS_success_percentage[key])/len(episode_QoS_success_percentage[key])
               for key in episode_QoS_success_percentage.keys()]
bars = plt.bar(string_list, values_list)
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 0.05, int(yval), ha='center')
plt.ylim(0, 1.1*max(values_list))
plt.xlabel("Users")
plt.ylabel('QoS Success (%)')
plt.title('Overall')
filename = 'QoS_Success_overall.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')

plt.figure(figsize=(8, 4))
string_list = map(str, episode_avg_bw.keys())
string_list = [f"$\leq$ {i}" for i in string_list]
values_list = [sum(episode_avg_bw[key])/len(episode_avg_bw[key]) for key in episode_avg_bw.keys()]
bars = plt.bar(string_list, values_list)
for bar in bars:
    yval = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2, yval + 0.05, int(yval), ha='center')
plt.ylim(0, 1.1*max(values_list))
plt.xlabel("Users")
plt.ylabel('Avg. PRBs')
plt.title('Overall')

filename = 'Avg_PRBs_overall.pdf'
plot_file = os.path.join(plots_folder, filename)
plt.savefig(plot_file, bbox_inches='tight')
