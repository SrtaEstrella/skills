"""
Dify DSL 生成器 v2
=================
基于已验证模板的程序化 DSL 生成。

用法：
    1. 置顶 TEMPLATE_PATH 指向一个已验证可导入的 DSL 文件
    2. 修改 main() 中的配置
    3. python generate.py

依赖：pip install pyyaml
"""

import yaml
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATE_PATH = HERE.parent / "your_template.yml"  # ← 替换为你的模板路径


def load_template(path: Path = None) -> dict:
    """加载模板 DSL 文件。"""
    p = path or TEMPLATE_PATH
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def save(app: dict, filepath: str) -> None:
    """以 Dify 兼容格式输出 DSL 文件。"""
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        yaml.dump(app, f,
                  allow_unicode=True,
                  default_flow_style=False,
                  sort_keys=False,
                  indent=2,
                  width=1000)


# ── 节点操作 ──────────────────────────────────

def get_start(app: dict) -> tuple[str, dict]:
    """返回 (node_id, node_data)"""
    for n in app["workflow"]["graph"]["nodes"]:
        if n["data"]["type"] == "start":
            return n["id"], n
    raise ValueError("找不到 Start 节点")


def get_agents(app: dict) -> list[tuple[str, dict]]:
    """返回所有 Agent 节点 [(node_id, node_data), ...]"""
    return [(n["id"], n) for n in app["workflow"]["graph"]["nodes"]
            if n["data"]["type"] == "agent"]


def filter_tools(agent: dict, keep: set[str]):
    """只保留指定名称的工具，禁用其余。完成后 agent['tools']['value'] 只含 keep 中的工具。"""
    tools = agent["data"]["agent_parameters"]["tools"]["value"]
    kept = [t for t in tools if t["tool_name"] in keep]
    for t in tools:
        t["enabled"] = t["tool_name"] in keep
    agent["data"]["agent_parameters"]["tools"]["value"] = kept


def make_answer(agent_id: str, node_id: str = "ans1") -> dict:
    """创建一个 Answer 节点，引用指定 Agent 的输出。"""
    return {
        "data": {
            "answer": "{{#" + agent_id + ".text#}}",
            "selected": False,
            "title": "输出",
            "type": "answer",
            "variables": [],
        },
        "id": node_id,
        "position": {"x": 700, "y": 282},
        "positionAbsolute": {"x": 700, "y": 282},
        "selected": False, "sourcePosition": "right", "targetPosition": "left",
        "type": "custom", "width": 242, "height": 103,
    }


def make_edge(src: str, tgt: str, src_type: str, tgt_type: str) -> dict:
    """创建一条连接边。"""
    return {
        "data": {"isInLoop": False, "sourceType": src_type, "targetType": tgt_type},
        "id": f"{src}-source-{tgt}-target",
        "source": src, "sourceHandle": "source",
        "target": tgt, "targetHandle": "target",
        "selected": False, "type": "custom", "zIndex": 0,
    }


# ── 变量引用 ──────────────────────────────────

def var_ref(node_id: str, var: str) -> str:
    """生成 Dify 变量引用字符串。"""
    return f"{{{{#{node_id}.{var}}}}}"


# ── 示例 ──────────────────────────────────────
if __name__ == "__main__":
    app = load_template()

    # 修改元数据
    app["app"]["name"] = "我的应用"
    app["app"]["description"] = "从模板生成"
    app["app"]["icon"] = "🤖"
    app["app"]["icon_type"] = "emoji"
    app["app"]["use_icon_as_answer_icon"] = False

    # 修改 Start 变量
    sid, start = get_start(app)
    start["data"]["variables"] = [{
        "default": "20", "hint": "", "label": "题目数量",
        "max_length": 10, "options": [], "placeholder": "",
        "required": False, "type": "number", "variable": "num_questions",
    }]

    # 修改 Agent
    aid, agent = get_agents(app)[0]
    agent["data"]["title"] = "我的Agent"
    agent["data"]["agent_parameters"]["instruction"]["value"] = (
        f"你是助手。生成 {var_ref(sid, 'num_questions')} 道题目。"
    )
    agent["data"]["agent_parameters"]["query"]["value"] = "开始工作"
    filter_tools(agent, {"tool_a", "tool_b"})  # ← 替换为实际工具名

    # 精简节点
    ans = make_answer(aid)
    app["workflow"]["graph"]["nodes"] = [start, agent, ans]
    app["workflow"]["graph"]["edges"] = [
        make_edge(sid, aid, "start", "agent"),
        make_edge(aid, ans["id"], "agent", "answer"),
    ]

    save(app, str(HERE.parent / "outputs" / "generated.yml"))
    print("Done: outputs/generated.yml")
