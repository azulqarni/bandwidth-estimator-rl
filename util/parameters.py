# import sys
# May need a higher recursion limit for BST based e2e delay calculation
# sys.setrecursionlimit(10000)


def unindexify_bandwidth(arm):
    bandwidth = PRBs[int(arm)]
    return bandwidth


def indexify_bandwidth(bandwidth):
    arm = PRBs.index(bandwidth)
    return arm


def indexify_context(context):
    indexified_context = []
    k = 0
    for component_value in context:
        component_possible_values = list_of_lists[k]
        indexified_context.append(len(component_possible_values)-1)     # assume the largest index initially
        li = 0
        for value in component_possible_values:
            if component_value <= value:
                indexified_context[k] = li
                break
            li = li + 1
        k = k + 1
    return indexified_context


# Considered PRB allocations
# PRBs = [10, 20, 30, 40, 50, 60, 72, 80, 90]  # needs to agree with possible-PRBs.txt
PRBs = [20, 40, 60, 90]

# Destroy UCB1: create a scenario of 10 UDP users of 1 Mbps each with PRBs = [24, 25, 90] and Q_target_value = 200
# PRBs = [24, 25, 90]

list_of_lists = []

# Considered Users, if it does not fit anywhere it goes to last element
# Users = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 21]
# Users = [5, 10, 15, 20]
Users = [2, 4, 6]
list_of_lists.append(Users)

# Considered MCS, see  3GPP 36.213 Table 7.1.7.1-1 (Downlink) and Table 8.6.1-1 (Uplink)
MCSs = [0, 12, 27, 28]
# MCSs = [28]
list_of_lists.append(MCSs)

# Considered BSRs, see 3GPP 36.213 Table 6.1.3.1-1
BSRs = [20, 40, 61, 62]
# BSRs = [10, 15, 20, 63]
list_of_lists.append(BSRs)

# List storing standard queue sizes
bsr_list = [
    0, 10, 12, 14, 17, 19, 22, 26, 31, 36, 42, 49, 57, 67, 78, 91, 107, 125, 146,
    171, 200, 234, 274, 321, 376, 440, 515, 603, 706, 826, 967, 1132, 1326, 1552,
    1817, 2127, 2490, 2915, 3413, 3995, 4677, 5476, 6411, 7505, 8787, 10287, 12043,
    14099, 16507, 19325, 22624, 26487, 31009, 36304, 42502, 49759, 58255, 68201,
    79846, 93479, 109439, 128125, 150000, 150000
]

# We consider that the QoS metric is a packet delay metric
possible_QoS = ["avg_packet_delay", "tail_packet_delay"]
desired_QoS = "tail_packet_delay"
Q_target_value = 100

# Destroy UCB1: create a scenario of 10 UDP users of 1 Mbps each with PRBs = [24, 25, 90] and Q_target_value = 200
# Q_target_value = 200

# Define maximum delay beyond which packets at the receiver are treated as lost
max_delay = 500  # milliseconds

# Deviating more than this from Q_target_value is too bad
DQmax = max_delay - Q_target_value

# Define number of arms
num_arms = len(PRBs)

# Number of simulated UEs
num_ue = len(Users)

# Maximum possible value of CQI
cqi_max = 16

# Define the dimensions of the context and the possible values of each of its components
# num of values that each context component may take, two components here
# we consider that the first component is the number of users and the total queue length
num_context_component_values = [len(Users), len(MCSs), len(BSRs)]

# Define idle time between selecting arm and estimating reward
round_interval = 10  # seconds

# Define number of samples
num_samples = 50 + 1
sampling_window = round_interval / num_samples  # seconds

# Define location of logs folder
logs = 'logs'

# Define location of logs from the UE side
ue_log = logs + '/ue0.log'

# Define location of logs from the enB side
enb_log = logs + '/mme.log'

# Callbox IP address
callbox_ip = "192.168.1.81"

# UEBox IP Address
uebox_ip = "192.168.1.80"

# Setting this to true will fetch logs from a dummy log server
testing = False

# Setting this to true will load statically specified log files
oldStyle = False

# Setting this to true will cause actual usage of the Amarisoft API
for_real = True

# Set this to true to look for received packets at transmitted logs
search_at_tx = True

# identifier for IP flows
# ip_id = "[IP]"
ip_id = "[IP] UL"

# RL parameters
epsilon = 0.01
gamma = 0.99
initial_rounds = 20
rounds_per_episode = 10

# If probability of QoS success for some action is smaller than the max prob by 'a', then do not prefer it
a = 0.01
QoS_cost_violation = (PRBs[-1] - PRBs[0])/a

debug_mode = False

possible_algorithms = ["UCB1_only", "policy_iteration", "value_iteration", "no_adaptation"]
algorithm = "policy_iteration"
arm_correlations = True  # consider arm correlations in UCB1
possible_costs = ["normal", "exponential"]
type_of_cost = "normal"
