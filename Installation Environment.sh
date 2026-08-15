#!/bin/bash
# Netease Music Downloader - One-Click Environment Setup (Linux/macOS)

set -e
set -u

echo "============================================"
echo "  Netease Music Downloader - One-Click Setup"
echo "============================================"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
NODE_DIR="${PROJECT_DIR}/nodejs"
NODE_EXE="${NODE_DIR}/node"
NPM_CLI="${NODE_DIR}/lib/node_modules/npm/bin/npm-cli.js"
API_PORT=3000
API_DIR="${PROJECT_DIR}/api-enhanced"
GLOBAL_BAT="${HOME}/.local/bin/netease-api"
ZIP_URL="https://codeload.github.com/xgxdmx/NeteaseMusic-API/zip/refs/heads/main"
EXE_NAME="MusicPlayer"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_ok() { echo -e "${GREEN}[OK]${NC} $1"; }
print_err() { echo -e "${RED}[XX]${NC} $1"; }
print_info() { echo -e "${YELLOW}[..]${NC} $1"; }

# ============================================================
#  1. Check Python environment
# ============================================================
echo "[1/7] Checking Python environment..."

if ! command -v python3 &> /dev/null; then
    print_err "Python3 not found. Please install Python 3.10 or later."
    echo "      Download: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$(python3 -V 2>&1)
print_ok "$PYTHON_VERSION"

if ! python3 -m pip -v &> /dev/null; then
    print_err "pip unavailable. Attempting to fix..."
    python3 -m ensurepip --upgrade || exit 1
fi
print_ok "pip ready"

# ============================================================
#  2. Install Python dependencies
# ============================================================
echo "[2/7] Installing Python dependencies..."

if [ -f "${PROJECT_DIR}/requirements.txt" ]; then
    print_info "Found requirements.txt, installing..."
    python3 -m pip install --upgrade pip -q
    if ! python3 -m pip install -r "${PROJECT_DIR}/requirements.txt" -q; then
        print_err "pip install failed. Trying mirror..."
        if ! python3 -m pip install -r "${PROJECT_DIR}/requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple -q; then
            print_err "Dependency installation still failed"
            exit 1
        fi
    fi
    print_ok "Python dependencies installed"
else
    print_info "requirements.txt not found, skipping Python dependencies"
fi

# ============================================================
#  3. Check Node.js
# ============================================================
echo "[3/7] Checking Node.js..."

if [ -f "${NODE_EXE}" ]; then
    print_ok "Bundled Node.js found"
    export PATH="${NODE_DIR}:$PATH"
    goto_verify_node=true
else
    if command -v node &> /dev/null; then
        print_ok "System Node.js found"
        NODE_VERSION=$(node -v)
        echo "    Version: $NODE_VERSION"
        NODE_EXE=$(which node)
        if command -v npm &> /dev/null; then
            NPM_CLI=$(which npm)
        else
            print_err "System npm not found"
            exit 1
        fi
        goto_verify_node=true
    else
        print_err "Node.js not found. Please install Node.js 18 or later."
        echo "      Download: https://nodejs.org/"
        exit 1
    fi
fi

# ============================================================
#  4. Verify Node.js / npm
# ============================================================
if [ -n "${goto_verify_node:-}" ]; then
    echo "[..] Verifying Node.js..."
    if ! "$NODE_EXE" -v &> /dev/null; then
        print_err "Node.js verification failed"
        exit 1
    fi
    print_ok "Node.js $(node -v)"

    echo "[..] Verifying npm..."
    if [ ! -f "$NPM_CLI" ] && [ ! -x "$NPM_CLI" ]; then
        print_err "npm not found: $NPM_CLI"
        exit 1
    fi

    if ! "$NPM_CLI" -v &> /dev/null; then
        print_err "npm verification failed"
        exit 1
    fi
    print_ok "npm $("$NPM_CLI" -v)"
fi

# ============================================================
#  5. Prepare api-enhanced
# ============================================================
echo "[4/7] Preparing api-enhanced..."

"$NPM_CLI" config set registry https://registry.npmmirror.com &> /dev/null || true

if [ ! -f "${API_DIR}/package.json" ]; then
    print_info "Downloading api-enhanced..."
    [ -d "$API_DIR" ] && rm -rf "$API_DIR"
    rm -f /tmp/api-enhanced.zip

    RETRY=0
    while [ $RETRY -lt 3 ]; do
        if curl -L --progress-bar -o /tmp/api-enhanced.zip "$ZIP_URL" --connect-timeout 180; then
            break
        else
            RETRY=$((RETRY + 1))
            if [ $RETRY -lt 3 ]; then
                print_info "Download failed, retry $RETRY/3..."
                sleep 3
            else
                print_err "Download failed"
                exit 1
            fi
        fi
    done

    print_ok "Download complete"
    print_info "Extracting..."
    mkdir -p "${API_DIR}_tmp"
    if ! unzip -q /tmp/api-enhanced.zip -d "${API_DIR}_tmp"; then
        print_err "Extraction failed"
        exit 1
    fi

    if [ -d "${API_DIR}_tmp/NeteaseMusic-API-main" ]; then
        mv "${API_DIR}_tmp/NeteaseMusic-API-main"/* "${API_DIR}_tmp/"
        rmdir "${API_DIR}_tmp/NeteaseMusic-API-main"
    fi
    for d in "${API_DIR}_tmp"/*; do
        if [ -d "$d" ] && [ -f "$d/package.json" ]; then
            mv "$d"/* "$API_DIR"
            rmdir "$d"
            break
        fi
    done
    rm -rf "${API_DIR}_tmp"
    rm -f /tmp/api-enhanced.zip

    if [ ! -f "${API_DIR}/package.json" ]; then
        print_err "package.json not found after extraction"
        exit 1
    fi
    print_ok "api-enhanced ready"
else
    print_ok "api-enhanced already exists"
fi

# ============================================================
#  6. Install Node.js dependencies (pnpm)
# ============================================================
echo "[5/7] Installing Node.js dependencies..."

cd "$API_DIR"

if command -v pnpm &> /dev/null; then
    print_ok "pnpm ready"
else
    if [ -f "$HOME/.local/bin/pnpm" ]; then
        export PATH="$HOME/.local/bin:$PATH"
        if command -v pnpm &> /dev/null; then
            print_ok "pnpm ready"
        fi
    fi
fi

if ! command -v pnpm &> /dev/null; then
    print_info "pnpm not found. Installing..."
    if ! "$NPM_CLI" install -g pnpm; then
        print_err "pnpm installation failed"
        exit 1
    fi
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v pnpm &> /dev/null; then
        print_err "pnpm still unavailable after installation"
        exit 1
    fi
    print_ok "pnpm installed"
fi

export HUSKY=0
print_info "Running pnpm install..."
if ! pnpm install --dangerously-allow-all-builds; then
    print_err "pnpm install failed"
    exit 1
fi

if [ -d "node_modules/express" ]; then
    print_ok "Dependencies installed"
else
    print_err "Dependency installation failed"
    exit 1
fi

# ============================================================
#  7. Create startup command
# ============================================================
echo "[6/7] Creating startup command..."
mkdir -p "$(dirname "$GLOBAL_BAT")"
cat > "$GLOBAL_BAT" << EOF
#!/bin/bash
cd "$API_DIR"
pnpm start
EOF
chmod +x "$GLOBAL_BAT"
print_ok "Startup command created: $GLOBAL_BAT"

# ============================================================
#  8. Start API service
# ============================================================
print_info "Starting API service..."

if lsof -i :$API_PORT -t &> /dev/null; then
    PID=$(lsof -i :$API_PORT -t)
    print_info "Port $API_PORT occupied by PID $PID, releasing..."
    kill -9 $PID 2>/dev/null || true
    sleep 1
fi
print_ok "Port $API_PORT ready"

nohup "$GLOBAL_BAT" &> /dev/null &

# ============================================================
#  9. Wait for API to be ready
# ============================================================
echo "[7/7] Waiting for API to be ready..."
RETRY=0
while [ $RETRY -lt 20 ]; do
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:$API_PORT/search?keywords=test" | grep -q 200; then
        print_ok "API ready"
        sleep 2
        break
    fi
    RETRY=$((RETRY + 1))
    echo "    Retry $RETRY/20..."
    sleep 2
done
if [ $RETRY -ge 20 ]; then
    print_err "API startup timeout (waited ~40 seconds)"
    exit 1
fi

# ============================================================
#  10. Start downloader
# ============================================================
print_info "Starting downloader..."

EXE_PATH="${PROJECT_DIR}/${EXE_NAME}"
if [ ! -f "$EXE_PATH" ]; then
    print_err "$EXE_NAME not found"
    echo "      Please run PyInstaller first, or update EXE_NAME in this script"
    exit 1
fi

chmod +x "$EXE_PATH"
"$EXE_PATH" &

echo ""
echo "============================================"
echo "  Startup complete!"
echo "  API: http://127.0.0.1:$API_PORT"
echo "  Project: $PROJECT_DIR"
echo "============================================"
sleep 3
exit 0