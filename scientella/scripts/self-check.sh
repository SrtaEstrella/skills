#!/usr/bin/env bash
# scientella-knowledge 自检外壳脚本
# 用法: bash scripts/self-check.sh <vault路径> [卡片文件...]
# 若未提供卡片文件列表，自动检测 vault 下所有 .md 文件。
# 返回 0 表示全部通过，非 0 表示存在问题。

# Resolve script dir in a cross-compatible way (Git Bash on Windows produces /d/... style paths)
case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*)
        # Use pwd -W to get Windows-style path when in Git Bash
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -W 2>/dev/null || pwd)"
        ;;
    *)
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        ;;
esac
VAULT="$1"
shift

if [ -z "$VAULT" ] || [ ! -d "$VAULT" ]; then
    echo "Usage: bash scripts/self-check.sh <vault路径> [卡片文件...]"
    exit 2
fi

# Detect Python: prefer python3, fall back to python (Windows compat)
# 需支持 yaml 模块（knowledge-graph.py 依赖），逐一探测候选解释器
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        if "$cmd" -c "import yaml" >/dev/null 2>&1; then
            PYTHON="$cmd"
            break
        fi
    fi
done
# 回退：探测常见带 yaml 的虚拟环境解释器
if [ -z "$PYTHON" ]; then
    for candidate in \
        "$HOME/.workbuddy/binaries/python/envs/default/Scripts/python.exe" \
        "$HOME/.workbuddy/binaries/python/envs/default/bin/python"; do
        if [ -x "$candidate" ] && "$candidate" -c "import yaml" >/dev/null 2>&1; then
            PYTHON="$candidate"
            break
        fi
    done
fi
if [ -z "$PYTHON" ]; then
    echo "ERROR: 未找到可用的 Python（需支持 yaml 模块）。请安装 pyyaml 或配置虚拟环境。"
    exit 2
fi

HAS_ISSUES=0

# ── Step 1: 状态图同步 + 图检 ──
echo "=== Step 1: Knowledge Graph Sync & Check ==="
PYTHONIOENCODING=utf-8 "$PYTHON" "$SCRIPT_DIR/knowledge-graph.py" "$VAULT" || HAS_ISSUES=1
echo ""

# ── Step 2: 格式检测 ──
echo "=== Step 2: Format Check ==="
if [ $# -eq 0 ]; then
    # format-check.py 支持目录参数（递归收集全部 .md、跳过隐藏目录），无需 find 展开文件列表
    if [ -z "$(find "$VAULT" -name '*.md' -print -quit 2>/dev/null)" ]; then
        echo "No .md files found in vault."
    else
        PYTHONIOENCODING=utf-8 "$PYTHON" "$SCRIPT_DIR/format-check.py" "$VAULT" || HAS_ISSUES=1
    fi
else
    PYTHONIOENCODING=utf-8 "$PYTHON" "$SCRIPT_DIR/format-check.py" "$@" || HAS_ISSUES=1
fi
echo ""

# ── Summary ──
echo "=== Summary ==="
if [ $HAS_ISSUES -eq 0 ]; then
    echo "[OK] All checks passed."
    exit 0
else
    echo "[!!] Issues found (see above)."
    exit 1
fi
