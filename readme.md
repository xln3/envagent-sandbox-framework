### EnvAgent Sandbox Framework

This is an autonomous environment interaction framework implemented based on Docker, tmux, and Python (psutil/Pixi). It enables host-side Agents to send commands to Shell environments within Docker containers and reliably detects command completion status (IDLE). This project aims to provide stable underlying execution and context recording capabilities for Agent systems that require remote, headless Shell environment operations.

- Host Language: Python 3 (for control logic)
- Container Environment: NVIDIA CUDA Base Image (Ubuntu 20.04)
- Process Isolation: Docker (--net=host, --gpus=all)
- Shell Interaction: Tmux (tmux send-keys / tmux capture-pane)
- In-Container Environment Management: Pixi
- State Detection: psutil process tree analysis (implemented wrapper penetration logic to ensure idle shells do not block IDLE state determination)

#### Project File Structure

| Filename | Description |
|:-|:-|
| Dockerfile | Docker build file. Contains system dependencies, Pixi installation, and PS1 prompt configuration. |
| auto_env_framework.py | Core Python script of the framework. Responsible for Docker/Tmux startup, command transmission, IDLE detection, and logging. |
| check_idle.py | Python auxiliary script within the container. Responsible for executing process tree analysis, serving as the basis for IDLE state determination. |
| pixi.toml | Pixi environment configuration file.|
| agent_context_raw.log | Raw terminal output log (containing ANSI color codes). |
| agent_context_clean.log | Filtered logs from each interaction (ANSI format codes removed, suitable for input as Agent context). |

#### Quick Start

1. Preparation (Host Machine)
    - Docker
    - Python

2. Run

    Run the Python framework script directly. It will automatically complete the construction of Docker images, the startup of containers, and the setup of Tmux sessions.
    
    ```bash
        python3 auto_env_framework.py
    ```

3. Interaction and Logging

    - Command Interaction: Input commands in the framework command line, and the framework will send them to the Shell inside the container via tmux send-keys.

    - Silent observation: You can connect to the Tmux session that the Agent is operating on to observe without interfering with its PID detection logic (please do not enter commands in this window):
    ```bash
        docker exec -it envagent_container tmux attach -t env_agent_session
    ```

#### Brief Overview of IDLE Detection Principle (Key Mechanism)

The framework determines whether a command has completed by monitoring the Shell process PID within the Tmux Pane and its process tree. To avoid misjudgments caused by multi-layer Shell nesting, the check_idle.py script implements wrapper penetration logic: it recursively checks all descendant processes in the Shell process tree. It defines all known environment Shell processes (such as pixi shell, bash -i, tmux new-session) as wrappers. Only when the process tree contains a non-wrapper process (i.e., an actual running task, such as git clone) is the environment determined to be BUSY. After all actual task processes exit, even if idle Shell processes remain, the framework correctly returns IDLE.