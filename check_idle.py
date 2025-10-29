import psutil
import sys
import os

# --- 配置：需要排除的持久化环境包装器命令 ---
# 这些命令在执行完子进程（实际任务）后，自身会保持运行，等待用户交互或子shell退出。
ENVIRONMENT_WRAPPERS = [
    "pixi shell",
    "conda run",
    "mamba run",
    "uv run",
    "poetry run",
    "uv shell",
    "conda shell",
    "mamba shell",
    "bash",  # <-- 排除空闲的 Bash 进程
    "sh",    # <-- 排除空闲的 Sh 进程
    # 新增基础设施排除项
    "tmux new-session -d -s", # Tmux 服务器启动命令
    "tmux attach",            # Tmux 客户端连接命令
    "/usr/bin/tmux server",   # Tmux 服务器进程
]
# ---------------------------------------------

def print_process_tree(proc, level=0):
    """递归打印进程树信息"""
    try:
        cmdline = " ".join(proc.cmdline())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        cmdline = "<Access Denied or Exited>"

    print(f"{'  ' * level}|-- PID {proc.pid} ({proc.status()}): {cmdline}")
    
    # 打印孙子进程
    for child in proc.children(recursive=False):
        print_process_tree(child, level + 1)

def is_wrapper_command(cmdline_list):
    """检查给定的命令行是否属于可忽略的包装器进程。"""
    if not cmdline_list:
        return False

    cmdline = " ".join(cmdline_list)
    command = cmdline_list[0].split('/')[-1]

    # Check for bash/sh command names
    if command in ["bash", "sh"]:
        return True
    
    # Check for other wrappers
    for wrapper_cmd in ENVIRONMENT_WRAPPERS:
        if wrapper_cmd in ["bash", "sh"]:
            continue
        if wrapper_cmd in cmdline:
            return True
            
    return False

def has_active_task_descendant(proc, current_script_name):
    """递归检查一个包装器进程是否拥有非包装器的子孙进程（即实际任务）。"""
    try:
        # 1. 排除 Agent 自身的检测脚本
        cmdline = " ".join(proc.cmdline())
        if current_script_name in cmdline:
            return False # Agent's own script is not an active task
        
        # 2. 如果当前进程不是包装器，它就是活跃任务
        if not is_wrapper_command(proc.cmdline()):
            return True 
        
        # 3. 递归检查子进程
        for child in proc.children(recursive=False):
            if has_active_task_descendant(child, current_script_name):
                return True
                
        return False
        
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    except Exception:
        return True # Default to True (BUSY) on exception

def is_active_task(child, current_script_name):
    """判断一个子进程是否是一个需要等待的、非包装器的活跃任务。"""
    try:
        if current_script_name in " ".join(child.cmdline()):
            return False
            
        # 核心逻辑：如果当前进程不是包装器，它必须是活跃的
        if not is_wrapper_command(child.cmdline()):
            return True
        
        # 如果当前进程是包装器，它只有在其子孙进程中存在非包装器任务时才算活跃
        return has_active_task_descendant(child, current_script_name)
            
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    except Exception:
        # 捕获其他异常，安全起见返回 True
        return True

def check_process_tree_for_children(pid):
    """
    检查给定 PID (即 Shell) 下是否还有任何活跃的子进程。
    """
    try:
        bash_proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return "IDLE"

    try:
        # 仅获取直接子进程，因为 is_active_task 内部会递归
        all_children = bash_proc.children(recursive=True) 
    except psutil.AccessDenied:
        return "BUSY"
    except Exception:
        return "BUSY"

    # --- 关键逻辑：检查是否有任何需要等待的“活跃任务” ---
    active_children_procs = []
    current_script_name = os.path.basename(__file__)
    
    # 遍历所有子进程
    for child in all_children:
        # 只有 is_active_task 返回 True 的才会被视为活跃
        if is_active_task(child, current_script_name):
            active_children_procs.append(child)

    # 检查是否有任何非排除的子进程存在
    if active_children_procs:
        # 存在非排除的子进程，说明 Shell 的前台命令还在运行
        print("--- BUSY: Active Children Found ---")
        # 打印根进程 (bash_proc) 及其子进程树
        print_process_tree(bash_proc)
        print("-----------------------------------")
        return "BUSY"
    
    # 如果子进程列表为空，则认为所有前台命令已完成
    return "IDLE"

try:
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print("BUSY")
        sys.exit(1)
        
    bash_pid = int(sys.argv[1])
    print(check_process_tree_for_children(bash_pid))

except Exception as e:
    # 捕获所有意外错误，假设仍在 BUSY
    print("BUSY")
    sys.exit(1)
