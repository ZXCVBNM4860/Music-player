#!/bin/bash
# 网易云下载器 - 一键环境初始化 (Linux/macOS 版)

set -e
set -u

# 显示标题
echo "============================================"
echo "  网易云下载器 - 一键环境初始化"
echo "============================================"
echo ""

# 获取脚本所在目录
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
NODE_DIR="${PROJECT_DIR}/nodejs"
NODE_EXE="${NODE_DIR}/node"
NPM_CLI="${NODE_DIR}/lib/node_modules/npm/bin/npm-cli.js"
API_PORT=3000
API_DIR="${PROJECT_DIR}/api-enhanced"
GLOBAL_BAT="${HOME}/.local/bin/netease-api"   # 启动脚本存放位置
ZIP_URL="https://codeload.github.com/xgxdmx/NeteaseMusic-API/zip/refs/heads/main"
EXE_NAME="MusicPlayer"   # Linux/macOS 下没有 .exe 后缀

# 颜色输出（可选）
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 辅助输出函数
print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_err() { echo -e "${RED}[XX]${NC} $1"; }
print_info() { echo -e "${YELLOW}[..]${NC} $1"; }

# ============================================================
#  1. 检测 Python 环境
# ============================================================
echo "[1/7] 检测 Python 环境..."

if ! command -v python3 &> /dev/null; then
    print_err "未找到 Python3，请先安装 Python 3.10 或更高版本"
    echo "      下载地址: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 -V 2>&1)
print_ok "$PYTHON_VERSION"

# 检查 pip
if ! python3 -m pip -v &> /dev/null; then
    print_err "pip 不可用，尝试修复..."
    python3 -m ensurepip --upgrade || exit 1
fi
print_ok "pip 已就绪"

# ============================================================
#  2. 安装 Python 依赖
# ============================================================
echo "[2/7] 安装 Python 依赖..."

if [ -f "${PROJECT_DIR}/requirements.txt" ]; then
    print_info "检测到 requirements.txt，正在安装..."
    python3 -m pip install --upgrade pip -q
    if ! python3 -m pip install -r "${PROJECT_DIR}/requirements.txt" -q; then
        print_err "pip 依赖安装失败，尝试镜像源..."
        if ! python3 -m pip install -r "${PROJECT_DIR}/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple -q; then
            print_err "依赖安装仍然失败"
            exit 1
        fi
    fi
    print_ok "Python 依赖安装完成"
else
    print_info "未找到 requirements.txt，跳过依赖安装"
fi

# ============================================================
#  3. 检测 Node.js
# ============================================================
echo "[3/7] 检测 Node.js..."

if [ -f "${NODE_EXE}" ]; then
    print_ok "内置 Node.js 已存在"
    export PATH="${NODE_DIR}:$PATH"
    goto_verify_node=true
else
    if command -v node &> /dev/null; then
        print_ok "系统 Node.js 已安装"
        NODE_VERSION=$(node -v)
        echo "    版本: $NODE_VERSION"
        NODE_EXE=$(which node)
        # 定位 npm
        if command -v npm &> /dev/null; then
            NPM_CLI=$(which npm)
        else
            print_err "系统 npm 未找到"
            exit 1
        fi
        goto_verify_node=true
    else
        print_err "未找到 Node.js，请先安装 Node.js 18 或更高版本"
        echo "      下载地址: https://nodejs.org/"
        exit 1
    fi
fi

# ============================================================
#  4. 验证 Node.js / npm
# ============================================================
if [ -n "${goto_verify_node:-}" ]; then
    echo "[..] 验证 Node.js..."
    if ! "$NODE_EXE" -v &> /dev/null; then
        print_err "Node.js 验证失败"
        exit 1
    fi
    print_ok "Node.js $(node -v)"

    echo "[..] 验证 npm..."
    if [ ! -f "$NPM_CLI" ] && [ ! -x "$NPM_CLI" ]; then
        print_err "npm 未找到: $NPM_CLI"
        exit 1
    fi

    if ! "$NPM_CLI" -v &> /dev/null; then
        print_err "npm 验证失败"
        exit 1
    fi
    print_ok "npm $("$NPM_CLI" -v)"
fi

# ============================================================
#  5. 准备 api-enhanced
# ============================================================
echo "[4/7] 准备 api-enhanced..."

# 设置 npm 镜像
"$NPM_CLI" config set registry https://registry.npmmirror.com &> /dev/null || true

if [ ! -f "${API_DIR}/package.json" ]; then
    print_info "下载 api-enhanced..."
    [ -d "$API_DIR" ] && rm -rf "$API_DIR"
    rm -f /tmp/api-enhanced.zip

    # 下载（带重试）
    RETRY=0
    while [ $RETRY -lt 3 ]; do
        if curl -L --progress-bar -o /tmp/api-enhanced.zip "$ZIP_URL" --connect-timeout 180; then
            break
        else
            RETRY=$((RETRY + 1))
            if [ $RETRY -lt 3 ]; then
                print_info "下载失败，重试 $RETRY/3..."
                sleep 3
            else
                print_err "下载失败"
                exit 1
            fi
        fi
    done

    print_ok "下载完成"
    print_info "解压..."
    mkdir -p "${API_DIR}_tmp"
    if ! unzip -q /tmp/api-enhanced.zip -d "${API_DIR}_tmp"; then
        print_err "解压失败"
        exit 1
    fi

    # 寻找实际的解压目录
    if [ -d "${API_DIR}_tmp/NeteaseMusic-API-main" ]; then
        mv "${API_DIR}_tmp/NeteaseMusic-API-main"/* "${API_DIR}_tmp/"
        rmdir "${API_DIR}_tmp/NeteaseMusic-API-main"
    fi
    # 将内容移出
    for d in "${API_DIR}_tmp"/*; do
        if [ -d "$d" ] && [ -f "$d/package.json" ]; then
            mv "$d"/* "$API_DIR"
            rmdir "$d"
            break
        fi
    done
    # 清理
    rm -rf "${API_DIR}_tmp"
    rm -f /tmp/api-enhanced.zip

    if [ ! -f "${API_DIR}/package.json" ]; then
        print_err "解压后未找到 package.json"
        exit 1
    fi
    print_ok "api-enhanced 准备完成"
else
    print_ok "api-enhanced 已就绪"
fi

# ============================================================
#  6. 安装 Node.js 依赖（pnpm）
# ============================================================
echo "[5/7] 安装 Node.js 依赖..."

cd "$API_DIR"

# 检测 pnpm
if command -v pnpm &> /dev/null; then
    print_ok "pnpm 已就绪"
else
    # 检测全局 pnpm（~/.local/bin）
    if [ -f "$HOME/.local/bin/pnpm" ]; then
        export PATH="$HOME/.local/bin:$PATH"
        if command -v pnpm &> /dev/null; then
            print_ok "pnpm 已就绪"
        fi
    fi
fi

if ! command -v pnpm &> /dev/null; then
    print_info "未检测到 pnpm，正在安装..."
    # 判断 npm 是 .js 还是可执行文件（统一用 npm 命令即可）
    if ! "$NPM_CLI" install -g pnpm; then
        print_err "pnpm 安装失败"
        exit 1
    fi
    # 添加 ~/.local/bin 到 PATH
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v pnpm &> /dev/null; then
        print_err "pnpm 安装后仍不可用"
        exit 1
    fi
    print_ok "pnpm 安装完成"
fi

# 执行 pnpm install
export HUSKY=0
print_info "执行 pnpm install..."
if ! pnpm install --dangerously-allow-all-builds; then
    print_err "pnpm install 失败"
    exit 1
fi

if [ -d "node_modules/express" ]; then
    print_ok "依赖安装完成"
else
    print_err "依赖安装失败"
    exit 1
fi

# ============================================================
#  7. 创建启动命令
# ============================================================
echo "[6/7] 创建启动命令..."
mkdir -p "$(dirname "$GLOBAL_BAT")"
cat > "$GLOBAL_BAT" << EOF
#!/bin/bash
cd "$API_DIR"
pnpm start
EOF
chmod +x "$GLOBAL_BAT"
print_ok "启动命令已创建: $GLOBAL_BAT"

# ============================================================
#  8. 启动 API 服务
# ============================================================
print_info "启动 API 服务..."

# 检查端口占用
if lsof -i :$API_PORT -t &> /dev/null; then
    PID=$(lsof -i :$API_PORT -t)
    print_info "发现端口 $API_PORT 被 PID $PID 占用，正在释放..."
    kill -9 $PID 2>/dev/null || true
    sleep 1
fi
print_ok "端口 $API_PORT 已就绪"

# 后台启动
nohup "$GLOBAL_BAT" &> /dev/null &

# ============================================================
#  9. 等待 API 就绪
# ============================================================
echo "[7/7] 等待 API 就绪..."
RETRY=0
while [ $RETRY -lt 20 ]; do
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$API_PORT/search?keywords=test" | grep -q 200; then
        print_ok "API 已就绪"
        sleep 2
        break
    fi
    RETRY=$((RETRY + 1))
    echo "    第 $RETRY 次重试..."
    sleep 2
done
if [ $RETRY -ge 20 ]; then
    print_err "API 启动超时（已等待约 40 秒）"
    exit 1
fi

# ============================================================
#  10. 启动下载器
# ============================================================
print_info "启动下载器..."

EXE_PATH="${PROJECT_DIR}/${EXE_NAME}"
if [ ! -f "$EXE_PATH" ]; then
    print_err "未找到 $EXE_NAME"
    echo "      请确保已运行 PyInstaller 打包，或修改脚本中的 EXE_NAME 变量"
    exit 1
fi

chmod +x "$EXE_PATH"
"$EXE_PATH" &

echo ""
echo "============================================"
echo "  启动完成！"
echo "  API: http://127.0.0.1:$API_PORT"
echo "  项目: $PROJECT_DIR"
echo "============================================"
sleep 3
exit 0