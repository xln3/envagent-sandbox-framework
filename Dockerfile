FROM nvidia/cuda:12.4.1-devel-ubuntu20.04

# --- 接收构建参数 ---
ARG PROMPT_SUFFIX_ARG="(ง •_•)ง " 
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    wget \
    curl \
    ca-certificates \
    vim \
    tmux \
    procps \
    libxml2-dev \
    libxslt1-dev \
    tar \
    gzip \
    locales \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装 Pixi
RUN PIXI_VERSION="v0.58.0" && \
    PIXI_URL="https://github.com/prefix-dev/pixi/releases/download/${PIXI_VERSION}/pixi-x86_64-unknown-linux-musl.tar.gz" && \
    mkdir -p /usr/local/bin && \
    mkdir -p /tmp/pixi_download && \
    curl -fsSL ${PIXI_URL} | tar xz -C /tmp/pixi_download && \
    mv /tmp/pixi_download/pixi /usr/local/bin/pixi && \
    rm -rf /tmp/pixi_download && \
    chmod +x /usr/local/bin/pixi


ENV PATH="/usr/local/bin:$PATH"

WORKDIR /workspace

# 复制配置文件和检测脚本
COPY pixi.toml /workspace/pixi.toml
COPY check_idle.py /root/check_idle.py

# 安装 Python 3.13 和 psutil
RUN pixi install

# 生成 Pixi hook 脚本
RUN pixi shell-hook > /root/pixi-hook.sh

# RUN source /root/pixi-hook.sh

# RUN export PS1="\u@\h:\w (ง •_•)ง "

# CMD ["/bin/bash"]
RUN printf '\n# EnvAgent Pixi Activation\nsource /root/pixi-hook.sh\n\n' >> /root/.bashrc && \
    printf 'export PS1="${debian_chroot:+($debian_chroot)}(envagent)\\u@\\h:\\w %s"\n' "${PROMPT_SUFFIX_ARG}" >> /root/.bashrc

CMD ["/bin/bash"]