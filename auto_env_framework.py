import os
import subprocess
import time
import sys
import re
# --- 配置参数 ---
CONTAINER_NAME = "envagent_container"  # 容器名称
IMAGE_NAME = "envagent-cuda-pixi"      # 镜像名称
TMUX_SESSION = "env_agent_session"
TMUX_WINDOW = "main"
TMUX_PANE = f"{TMUX_SESSION}:{TMUX_WINDOW}.0"

LOG_FILE_RAW = "agent_context_raw.log"
LOG_FILE_CLEAN = "agent_context_clean.log"
PROMPT_SUFFIX = "(ง •_•)ง"
IDLE_PROMPT_PATTERN = PROMPT_SUFFIX

# --- 辅助函数：过滤 ANSI 代码 ---
def strip_ansi_codes(text):
    """移除文本中的 ANSI 颜色和格式化代码"""
    # 正则表达式匹配 ANSI 逃逸序列：\x1b[...m
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    return ansi_escape.sub('', text)

# --- 辅助函数：执行 Shell 命令 ---
def run_command(cmd, capture=False, check=True):
    """在宿主机上执行 shell 命令。"""
    try:
        result = subprocess.run(cmd, shell=True, check=check, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error executing command: {e.cmd}")
            # print(f"Stdout: {e.stdout}") # 调试时启用
            # print(f"Stderr: {e.stderr}") # 调试时启用
            sys.exit(1)
        return None
    except FileNotFoundError:
        print(f"Error: Command not found or required tool is missing (docker or tmux).")
        sys.exit(1)

# --- 框架启动函数 ---
def setup_docker_image():
    # """构建 Docker 镜像并启动容器，包含 net=host 和 gpus=all 参数。"""
    # print("--- 1. 检查和构建 Docker 镜像 ---")
    
    # # 检查 Dockerfile 和配置文件是否存在
    # if not all(os.path.exists(f) for f in ['Dockerfile', 'pixi.toml', 'check_idle.py']):
    #     print("错误: 缺少 Dockerfile, pixi.toml 或 check_idle.py 文件。请确保它们在当前目录下。")
    #     sys.exit(1)

    # # 1. 构建镜像 (传递 PROMPT_SUFFIX 作为 ARG)
    # print(f"构建镜像 {IMAGE_NAME}...")
    # build_cmd = f'docker build -t {IMAGE_NAME} --build-arg PROMPT_SUFFIX_ARG="{PROMPT_SUFFIX}" .'
    # run_command(build_cmd)
    
    # 2. 停止并移除同名旧容器
    run_command(f"docker stop {CONTAINER_NAME}", check=False)
    run_command(f"docker rm {CONTAINER_NAME}", check=False)

    # 3. 启动新容器 (新增 --net=host 和 --gpus=all 参数)
    print(f"启动容器 {CONTAINER_NAME} (使用 --net=host, --gpus=all)...")
    docker_run_cmd = (
        f"docker run -itd --name {CONTAINER_NAME} --net=host --gpus=all "
        f"-e http_proxy=$http_proxy -e https_proxy=$https_proxy "
        f"{IMAGE_NAME} /bin/bash"
    )
    run_command(docker_run_cmd)

def setup_tmux_session():
    """在容器内启动 Tmux Session，使用 Shell 内部的后台执行确保同步创建。"""
    print("--- 2. 启动容器内 Tmux 会话 ---")
    
    # 1. 检查会话是否存在并清理
    run_command(f"docker exec {CONTAINER_NAME} tmux kill-session -t {TMUX_SESSION}", check=False)
    
    # 2. 启动新的 tmux 会话
    print(f"在容器内创建 Tmux Session: {TMUX_SESSION} (Window: {TMUX_WINDOW})...")
    
    # FIX: 明确指定窗口名称，确保与 TMUX_PANE 变量匹配 (session:window.pane)
    tmux_start_cmd = (
        f"docker exec {CONTAINER_NAME} tmux new-session -d -s {TMUX_SESSION} -n {TMUX_WINDOW}"
    )
    # 允许 check=False，因为 tmux new-session -d 成功但终端输出可能有警告
    run_command(tmux_start_cmd, check=False)
    
    # 3. 增加延迟以确保 Shell 在 pane 中完全初始化
    print("  等待 Shell 初始化...")
    time.sleep(2) # 增加初始延迟

# --- 辅助函数：获取 bash PID ---
def get_bash_pid():
    """获取 tmux pane 内部的 bash 进程 PID。（增加重试机制）"""
    # 进一步增加最大重试次数和每次重试的等待时间，以应对慢速启动的 Shell
    max_retries = 15
    sleep_time = 3
    
    for attempt in range(max_retries):
        tmux_pid_cmd = (
            f"docker exec {CONTAINER_NAME} tmux list-panes -t {TMUX_PANE} -F \"#{{pane_pid}}\" "
        )
        
        # 允许失败，不立即退出
        pid_str = run_command(tmux_pid_cmd, capture=True, check=False) 

        print(f"  Retrieved pane PID string: '{pid_str}'")
        # 检查返回的字符串是否为有效的 PID (可能是多行，但我们只需要第一个)
        first_pid = pid_str.split('\n')[0].strip()
        
        if first_pid and first_pid.isdigit() and int(first_pid) > 0:
            return int(first_pid)
        
        print(f"  [PID Retrieval Attempt {attempt + 1}/{max_retries}] Waiting for pane PID...")
        time.sleep(sleep_time)
        
    print("Error: Could not retrieve bash PID from tmux pane in container after multiple retries. Check if tmux session was created and is accessible.")
    sys.exit(1)


# --- 辅助函数：检查 IDLE 状态 (通过 docker exec 调用容器内脚本) ---
def check_idle_status(bash_pid):
    """
    通过 docker exec 在容器内运行 check_idle.py。
    显式 source pixi-hook.sh 以确保 python 可用。
    """
    cmd = (
        f'docker exec {CONTAINER_NAME} /bin/bash -c "source /root/pixi-hook.sh && python /root/check_idle.py {bash_pid}"'
    )
    status = run_command(cmd, capture=True)
    # print(f"check_idle.py returned status: '{status}'")
    return status.strip()

# --- 辅助函数：检测提示符 ---
def check_prompt_in_last_line(capture_output):
    """检查捕获的输出的最后一行是否包含自定义提示符。"""
    lines = capture_output.split('\n')
    if not lines:
        return False
    return IDLE_PROMPT_PATTERN in lines[-1]

# --- 主循环 ---
def main_loop():
    print("--- EnvAgent 交互框架启动 ---")
    
    # 自动化设置
    setup_docker_image()
    setup_tmux_session()
    
    # 1. PID 检查
    try:
        # 获取容器内 bash 进程的 PID
        bash_pid = get_bash_pid()
    except Exception as e:
        print(f"初始化 PID 失败: {e}")
        return
        
    print(f"--- Agent 框架初始化成功。监控容器内 PID: {bash_pid} ---")
    
    # 方便用户查看实时 Tmux 输出（可选）
    print(f"您可以通过运行 'docker exec -it {CONTAINER_NAME} tmux attach -t {TMUX_SESSION}' 来实时查看容器内终端。")
    print("-" * 30)


    while True:
        try:
            user_cmd = input("请输入要执行的命令 (输入 'exit' 退出): ")
        except EOFError:
            print("\nReceived EOF. Exiting.")
            break
        
        if user_cmd.lower() == "exit":
            print("--- 框架退出 ---")
            # 退出时停止容器
            run_command(f"docker stop {CONTAINER_NAME}", check=False)
            break
        
        if not user_cmd:
            continue

        # 1. 发送命令到 tmux pane
        # C-m 是回车键
        run_command(f"docker exec {CONTAINER_NAME} tmux send-keys -t {TMUX_PANE} '{user_cmd}' C-m")
        print(f"-> 命令已发送: {user_cmd}")

        
        print(f"-> 正在监控 PID {bash_pid} 及其子进程 IDLE...", end='', flush=True)
        while True:
            status = check_idle_status(bash_pid)
            # print(f"status: {status}")
            if status == "IDLE":
                print(" IDLE 状态确认。")
                break
            elif "No server is running" in status:
                print("\n错误：Tmux Server 已停止。请检查容器状态。")
                sys.exit(1)
            else:
                print(".", end='', flush=True)
                time.sleep(1)

        # 3. IDLE 状态下的提示符检测与回车触发机制
        idle_prompt_wait_counter = 0
        while True:
            # 捕获当前 pane 内容
            capture_output = run_command(f"docker exec {CONTAINER_NAME} tmux capture-pane -t {TMUX_PANE} -p -e", capture=True)
            if check_prompt_in_last_line(capture_output):
                print("-> **检测到 Shell 提示符，命令执行完成。**")
                break
            else:
                # IDLE 但没检测到提示符，强制输入回车以触发提示符显示
                print("[P:发送回车触发提示符]", end='', flush=True)
                
                # 发送回车 C-m
                run_command(f"docker exec {CONTAINER_NAME} tmux send-keys -t {TMUX_PANE} C-m")
                
                time.sleep(1) # 等待终端渲染
                
                idle_prompt_wait_counter += 1
            
            # 安全退出机制
            if idle_prompt_wait_counter >= 10:
                print("\n-> 警告：已尝试发送 10 次回车仍未见提示符，强制继续...")
                break

        # 4. 记录和清理
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"-> 记录当前窗口历史到 '{LOG_FILE_RAW}' 和 '{LOG_FILE_CLEAN}'...")
        
        # 再次捕获，确保包含最后一次回车后的内容
        final_capture_raw = run_command(f"docker exec {CONTAINER_NAME} tmux capture-pane -t {TMUX_PANE} -S - -p -e", capture=True)
        final_capture_clean = strip_ansi_codes(final_capture_raw) # 过滤 ANSI 代码
        # --- 写入 RAW Log ---
        with open(LOG_FILE_RAW, 'a') as f:
            f.write(f"\n\n======================================================\n")
            f.write(f"SESSION START: {timestamp}\n")
            f.write(f"COMMAND EXECUTED: {user_cmd}\n")
            f.write(f"======================================================\n\n")
            f.write(final_capture_raw)
            f.write("\n")

        # --- 写入 CLEAN Log ---
        with open(LOG_FILE_CLEAN, 'a') as f:
            f.write(f"\n\n======================================================\n")
            f.write(f"SESSION START: {timestamp}\n")
            f.write(f"COMMAND EXECUTED: {user_cmd} (CLEANED)\n")
            f.write(f"======================================================\n\n")
            f.write(final_capture_clean)
            f.write("\n")


        # 清空窗口 (Ctrl-L 快捷键)
        print("-> 清空窗口内容和历史...")
        run_command(f"docker exec {CONTAINER_NAME} tmux send-keys -t {TMUX_PANE} C-l")
        run_command(f"docker exec {CONTAINER_NAME} tmux clear-history -t {TMUX_PANE}")

        print("--- 等待下一条命令 ---\n")

if __name__ == "__main__":
    main_loop()
