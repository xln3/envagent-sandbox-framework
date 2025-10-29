EnvAgent Sandbox Framework

这是一个基于 Docker, tmux, 和 Python (psutil/Pixi) 实现的自主环境交互框架。它允许宿主机 Agent 向 Docker 容器内的 Shell 发送命令，并可靠地检测命令的完成状态（IDLE）。

本项目旨在为需要远程、无头操作 Shell 环境的 Agent 系统提供稳定的底层执行和上下文记录能力。

核心技术栈

宿主机语言: Python 3 (用于控制逻辑)

容器环境: NVIDIA CUDA Base Image (Ubuntu 20.04)

进程隔离: Docker (--net=host, --gpus=all)

Shell 交互: Tmux (tmux send-keys / tmux capture-pane)

环境管理: Pixi (用于容器内的 Python 3.13 和 psutil)

状态检测: psutil 进程树分析（实现了包装器穿透逻辑，确保空闲 Shell 不会阻塞 IDLE 状态判断）

项目文件结构

| 文件名 | 描述 |
| Dockerfile | Docker 构建文件。包含系统依赖、Pixi 安装和 PS1 提示符配置。 |
| auto_env_framework.py | 宿主机 Agent 框架的核心 Python 脚本。负责 Docker/Tmux 启动、命令发送、IDLE 检测和日志记录。 |
| check_idle.py | 容器内部的 Python 辅助脚本。负责执行进程树分析，是 IDLE 状态判断的依据。 |
| pixi.toml | Pixi 环境配置文件，定义 Python 3.13 和 psutil 依赖。 |
| agent_context_raw.log | 每次交互的原始终端输出日志（包含 ANSI 颜色代码）。 |
| agent_context_clean.log | 每次交互的过滤后日志（移除了 ANSI 格式代码，适合作为 Agent 上下文输入）。 |

快速启动

1. 环境准备 (宿主机)

主机环境需要安装：

Docker (包含 NVIDIA Container Toolkit 以支持 --gpus=all)

Python 3

2. 初始化项目

将所有项目文件（Dockerfile, pixi.toml, check_idle.py, auto_env_framework.py）放在同一目录下。

3. 运行框架

直接运行 Python 框架脚本。它将自动完成 Docker 镜像的构建、容器的启动和 Tmux 会话的设置。

python3 auto_env_framework.py


4. 交互与日志

命令交互： 在框架命令行输入命令，框架会通过 tmux send-keys 将其发送至容器内 Shell。

静默旁观： 您可以连接到 Agent 正在操作的 Tmux 会话进行旁观，而不会干扰其 PID 检测逻辑（请勿在该窗口输入命令）：

docker exec -it envagent_container tmux attach -t env_agent_session



日志效果： 命令执行完毕后，框架会追加记录两种日志：

agent_context_raw.log: 包含原始终端格式。

agent_context_clean.log: 移除格式字符后的干净版本（用于后续 Agent 上下文）。

IDLE 检测原理简述 (关键机制)

框架通过监控 Tmux Pane 内的 Shell 进程 PID（例如 PID 43）及其进程树来判断命令是否完成。

为避免多层 Shell 嵌套的误判，check_idle.py 脚本实现了包装器穿透逻辑：

它递归检查 Shell 进程树上的所有子孙进程。

它将所有已知的环境 Shell 进程（如 pixi shell, bash -i, tmux new-session）定义为包装器。

只有当进程树中包含一个非包装器的进程（即实际运行的任务，如 git clone）时，环境才被判定为 BUSY。

当所有实际任务进程退出后，即使空闲 Shell 进程仍存在，框架也会正确返回 IDLE。