# Bandwidth Demand Estimator (BDE)

The Bandwidth Demand Estimator (BDE) is a network function designed to efficiently manage bandwidth allocation in a Network Slice (NS) to meet packet delay requirements while minimizing Quality of Service (QoS) violations. This repository contains the implementation of the BDE along with tools for scenario generation using the Amarisoft testbed.

## Overview

The BDE utilizes a data-driven approach, incorporating QoS feedback to dynamically adjust bandwidth allocation at the base station (AMARI Callbox). It employs reinforcement learning techniques to learn the optimal bandwidth allocation policy while considering the future impact of its actions on packet queues and QoS metrics.

## Key Features

- **Reinforcement Learning Approach**: The BDE employs reinforcement learning, where actions represent allocated bandwidth, states describe traffic conditions, wireless channel status, and packet queue information, and the cost function is a weighted sum of bandwidth allocation and QoS violations.

- **Transition Matrix Estimation**: Periodic estimation of the transition matrix facilitates value iteration to find the optimal policy. Multi-armed bandits are utilized for initial estimation, leveraging the monotonicity of the cost function with respect to actions.

- **Integration with Amarisoft Testbed**: The implementation interfaces with the Amarisoft API, providing tools for scenario generation and performance evaluation.

## Components

### 1. BDE Implementation
   - Algorithms for bandwidth allocation based on reinforcement learning.
   - Transition matrix estimation and value iteration.
   - Integration with QoS feedback mechanisms.

### 2. Scenario Generation Tool (`amarify.py`)
   - Generates test scenarios using the Amarisoft testbed.
   - Configures parameters for LTE cell settings, traffic types, and UE behaviors.
   - Utilizes JavaScript Object Notation (JSON) configuration files for scenario definition.

## Amarisoft Testbed Integration

The Amarisoft testbed consists of the AMARI Callbox Ultimate and the AMARI UE Simbox, facilitating over-the-air LTE communication with SDRs. The BDE implementation runs on an Ubuntu PC connected to the testbed, enabling configuration, traffic monitoring, and scenario execution via SSH commands.

## Usage

To utilize the BDE and generate test scenarios:
1. Configure scenarios using `amarify.py`.
2. Execute the BDE implementation `bandwidth-bandits.py` on the Ubuntu PC connected to the Amarisoft testbed.

## Citation

If you use this implementation, please cite the following paper:
[P. Nikolaidis, A. Zoulkarni, J. Baras, "Data-driven Bandwidth Adaptation for Radio Access Network Slices," arXiv:2311.17347, 2023]

## Contributors

- Panagiotis Nikolaidis (nikolaid@umd.edu)
- Asim Zoulkarni (asimz@umd.edu)
