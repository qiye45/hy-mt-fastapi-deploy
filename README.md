# Hy-MT1.5 1.25bit FastAPI 部署

这个目录提供一个 Linux 可部署的 FastAPI 服务，用于包装
[AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF](https://huggingface.co/AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF)。

该 1.25bit GGUF 依赖 AngelSlim 发布给 `llama.cpp` 的 STQ1_0 kernel，目前模型卡说明需要使用
[ggml-org/llama.cpp PR #22836](https://github.com/ggml-org/llama.cpp/pull/22836)。本项目会自动拉取该 PR、编译
`llama-server`，再由 FastAPI 通过 OpenAI-compatible 接口转发请求。

## 目录结构

```text
hy-mt-fastapi-deploy/
├── app/
│   └── main.py                 # FastAPI 服务
├── examples/
│   ├── openai_compatible.sh    # OpenAI-compatible 调用示例
│   └── translate.sh            # /translate 调用示例
├── scripts/
│   ├── download_model.sh       # 下载 GGUF 模型
│   ├── install_linux.sh        # Linux 一键安装
│   └── start.sh                # 启动 llama-server + FastAPI
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## 机器要求

- Linux x86_64，推荐 Ubuntu 22.04/24.04 或 Debian 12。
- CPU 部署即可，默认 `N_GPU_LAYERS=0`。
- 内存建议 4GB 以上，磁盘建议至少 6GB 可用空间，用于源码、编译产物、Python 环境和模型。
- 需要能访问 GitHub 和 Hugging Face。

## 方式一：Linux 一键部署

```bash
cd hy-mt-fastapi-deploy
cp .env.example .env
./scripts/install_linux.sh
source .venv/bin/activate
./scripts/start.sh
```

脚本会执行：

1. 安装 `git`、`cmake`、编译工具、Python venv 等依赖。
2. 克隆 `llama.cpp`。
3. 拉取并切换到 `pull/22836/head:pr-22836-stq_0`。
4. 编译 `llama-server`。
5. 创建 Python 虚拟环境并安装 FastAPI 依赖。
6. 下载 `Hy-MT1.5-1.8B-1.25bit.gguf`。

服务启动后：

- FastAPI: `http://127.0.0.1:8000`
- 内部 llama-server: `http://127.0.0.1:8080`

## 使用 Hugging Face GGUF 仓库部署示例

下面示例直接使用
[AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF](https://huggingface.co/AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF/tree/main)
里的 `Hy-MT1.5-1.8B-1.25bit.gguf` 文件部署。

### 1. 准备环境

```bash
cd hy-mt-fastapi-deploy
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. 编译支持 STQ1_0 的 llama.cpp

这个 1.25bit GGUF 需要 STQ1_0 kernel，按模型卡说明使用 `llama.cpp` PR #22836：

```bash
mkdir -p vendor
git clone https://github.com/ggml-org/llama.cpp.git vendor/llama.cpp
cd vendor/llama.cpp
git fetch origin pull/22836/head:pr-22836-stq_0
git checkout pr-22836-stq_0
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j"$(nproc)"
cd ../..
```

### 3. 下载 Hugging Face GGUF 模型

```bash
huggingface-cli download AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF \
  Hy-MT1.5-1.8B-1.25bit.gguf \
  --local-dir models/Hy-MT1.5-1.8B-1.25bit-GGUF \
  --local-dir-use-symlinks False
```

模型文件路径应为：

```text
models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf
```

### 4. 启动 FastAPI 服务

```bash
cat > .env <<'EOF'
MODEL_NAME=AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF
MODEL_PATH=./models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf
LLAMA_CPP_DIR=./vendor/llama.cpp
LLAMA_SERVER_URL=http://127.0.0.1:8080
LLAMA_PORT=8080
API_PORT=8000
CTX_SIZE=4096
THREADS=0
N_GPU_LAYERS=0
DEFAULT_MAX_TOKENS=512
DEFAULT_TEMPERATURE=0.0
EOF

./scripts/start.sh
```

### 5. 调用翻译接口

```bash
curl -sS http://127.0.0.1:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The weather is nice today.",
    "target_language": "Chinese",
    "max_tokens": 128
  }' | python -m json.tool
```

也可以调用 OpenAI-compatible 接口：

```bash
curl -sS http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Translate the following segment into Chinese, without additional explanation.\n\nThe weather is nice today."
      }
    ],
    "temperature": 0,
    "max_tokens": 128,
    "stream": false
  }' | python -m json.tool
```

## 方式二：Docker Compose

Docker 镜像会在构建阶段拉取 `llama.cpp` PR #22836 并编译 `llama-server`。容器启动后，如果挂载目录里没有
`Hy-MT1.5-1.8B-1.25bit.gguf`，会自动从
[AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF](https://huggingface.co/AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF/tree/main)
下载模型。

```bash
cd hy-mt-fastapi-deploy
docker compose up -d --build
```

首次启动时，如果 `./models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf`
不存在，容器会自动下载模型到挂载的 `./models` 目录。

查看日志：

```bash
docker compose logs -f
```

停止服务：

```bash
docker compose down
```

### Docker Compose 完整验证示例

```bash
cd hy-mt-fastapi-deploy
mkdir -p models
docker compose up -d --build
docker compose logs -f
```

另开一个终端测试：

```bash
curl -sS http://127.0.0.1:8000/health | python -m json.tool

curl -sS http://127.0.0.1:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The weather is nice today.",
    "target_language": "Chinese",
    "max_tokens": 128
  }' | python -m json.tool
```

### 纯 Docker 命令部署

不使用 Compose 时，可以直接构建并运行：

```bash
cd hy-mt-fastapi-deploy
mkdir -p models

docker build -t hy-mt-fastapi:latest .

docker run -d \
  --name hy-mt-fastapi \
  -p 8000:8000 \
  -v "$(pwd)/models:/app/models" \
  -e MODEL_PATH=/app/models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf \
  -e CTX_SIZE=4096 \
  -e THREADS=0 \
  -e N_GPU_LAYERS=0 \
  hy-mt-fastapi:latest
```

查看日志：

```bash
docker logs -f hy-mt-fastapi
```

测试服务：

```bash
curl -sS http://127.0.0.1:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you today?",
    "target_language": "Chinese",
    "max_tokens": 128
  }' | python -m json.tool
```

停止并删除容器：

```bash
docker rm -f hy-mt-fastapi
```

## API 调用

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 翻译接口

```bash
curl -sS http://127.0.0.1:8000/translate \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello, how are you today?",
    "target_language": "Chinese",
    "max_tokens": 128
  }' | python -m json.tool
```

也可以直接运行示例：

```bash
./examples/translate.sh
```

### OpenAI-compatible 接口

```bash
curl -sS http://127.0.0.1:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {
        "role": "user",
        "content": "Translate the following segment into Chinese, without additional explanation.\n\nHello, how are you today?"
      }
    ],
    "temperature": 0,
    "max_tokens": 128,
    "stream": false
  }' | python -m json.tool
```

## 常用配置

复制 `.env.example` 为 `.env` 后修改：

```bash
MODEL_PATH=./models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf
LLAMA_CPP_DIR=./vendor/llama.cpp
LLAMA_PORT=8080
API_PORT=8000
CTX_SIZE=4096
THREADS=0
N_GPU_LAYERS=0
DEFAULT_MAX_TOKENS=512
DEFAULT_TEMPERATURE=0.0
```

说明：

- `THREADS=0` 表示启动脚本自动使用机器 CPU 核心数。
- `CTX_SIZE` 可按业务文本长度调大，但会增加内存占用。
- `N_GPU_LAYERS=0` 是纯 CPU。需要 GPU 时先确认本地 `llama.cpp` 编译参数和驱动环境，再调整该值。
- `LLAMA_EXTRA_ARGS` 可以追加 `llama-server` 参数，例如 `LLAMA_EXTRA_ARGS="--verbose"`。

## 生产部署建议

### systemd 示例

将项目放到 `/opt/hy-mt-fastapi-deploy` 后，可创建：

```ini
[Unit]
Description=Hy-MT1.5 FastAPI Service
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/opt/hy-mt-fastapi-deploy
EnvironmentFile=/opt/hy-mt-fastapi-deploy/.env
ExecStart=/bin/bash -lc 'source /opt/hy-mt-fastapi-deploy/.venv/bin/activate && /opt/hy-mt-fastapi-deploy/scripts/start.sh'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 反向代理

如需公网访问，建议使用 Nginx/Caddy 代理到 `127.0.0.1:8000`，并增加鉴权、HTTPS、限流和日志。
这个示例没有内置 API key 校验，默认适合内网或本机使用。

## 故障排查

### `llama-server not found`

说明 `llama.cpp` 没有编译成功，重新运行：

```bash
./scripts/install_linux.sh
```

### `GGUF depends on STQ kernel`

这是模型限制。不要使用普通 release 版 `llama.cpp` 直接加载该 GGUF；需要模型卡指定的 PR #22836。

### 下载模型失败

确认可以访问 Hugging Face：

```bash
huggingface-cli download AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF Hy-MT1.5-1.8B-1.25bit.gguf
```

如果机器在国内网络环境，建议提前在可访问 Hugging Face 的机器下载模型，再把文件放到：

```text
models/Hy-MT1.5-1.8B-1.25bit-GGUF/Hy-MT1.5-1.8B-1.25bit.gguf
```

## 参考链接

- 模型权重：https://huggingface.co/AngelSlim/Hy-MT1.5-1.8B-1.25bit
- GGUF 模型：https://huggingface.co/AngelSlim/Hy-MT1.5-1.8B-1.25bit-GGUF
- `llama.cpp` STQ1_0 PR：https://github.com/ggml-org/llama.cpp/pull/22836
- HY-MT1.5 基座模型：https://huggingface.co/tencent/HY-MT1.5-1.8B
