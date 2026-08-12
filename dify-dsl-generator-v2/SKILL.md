---
name: dify-dsl-generator-v2
description: Dify 工作流 DSL 生成器（v2），基于实地验证的 DSL 规范，支持 Agent/MCP/LLM/Code 节点，包含调试方法论。
---

# Dify DSL Generator v2

基于对 Dify 实例的实战踩坑经验，提炼出的可靠 DSL 生成方法论。

---

## 核心原则

### 1. 永远不要手写 YAML

`Write` 工具写出的原始文本在编码、换行符、引号风格、缩进一致性上与 Dify 导出不一致，导入器对格式极其敏感。**始终用 Python yaml.dump 输出**。

经过验证的稳定输出参数：

```python
import yaml

with open('template.yml', encoding='utf-8') as f:
    app = yaml.safe_load(f)
# ... 修改 app 字典 ...
with open('output.yml', 'w', encoding='utf-8', newline='\n') as f:
    yaml.dump(app, f, allow_unicode=True, default_flow_style=False,
              sort_keys=False, indent=2, width=1000)
```

关键参数说明：
- `encoding='utf-8'`：防止非 ASCII 字符乱码
- `newline='\n'`：Unix 换行符。CRLF 可能导致导入失败
- `allow_unicode=True`：中文字符直接输出，不转义为 `\uXXXX`
- `default_flow_style=False`：块风格，结构清晰
- `sort_keys=False`：保持字段顺序（Dify 导入器对字段顺序可能敏感）
- `indent=2`：Dify 导出标准缩进
- `width=1000`：防止过长的行被自动折行

### 2. 从已验证的模板出发

不要从零构建。获取一个存在于目标 Dify 实例中、已验证可正常导入和运行的 DSL 文件作为模板。在 Python 中修改字段值后重新导出。

**模板选择标准**：
- 与目标模式相同（workflow / advanced-chat）
- 包含目标节点类型（Agent 带 MCP / LLM / Code 等）
- 已经过实际导入验证

### 3. 渐进式调试

手写 DSL 导入失败时，不要猜测。使用二分法定位：
1. 将模板只改 name，导入验证 → 确认模板本身兼容
2. 逐步增加修改，每次只改一类内容（prompt / tools / variables）
3. 用 Python 展开两个文件的全部字段路径做 diff，锁定具体差异字段

```python
def flatten(d, prefix=""):
    """递归展平为 field_path -> value 字典。"""
    result = {}
    if isinstance(d, dict):
        for k, v in d.items():
            path = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                result.update(flatten(v, path))
            else:
                result[path] = repr(v)[:100]
    elif isinstance(d, list):
        for i, v in enumerate(d):
            path = f"{prefix}[{i}]"
            if isinstance(v, (dict, list)):
                result.update(flatten(v, path))
            else:
                result[path] = repr(v)[:100]
    return result
```

---

## 模式选择

### Agent 模式（`mode: advanced-chat`）

适用场景：需要 LLM 自主决定何时调用工具、调用哪个工具。
- Agent 内嵌 MCP 工具，Agent 在对话循环中推理和调用
- 结构简单：Start → Agent → Answer
- MCP 工具放在 `agent_parameters.tools` 中

**必填字段**——以下任一缺失都会导致导入失败：

| 字段路径 | 示例值 | 说明 |
|---------|--------|------|
| `agent_strategy_label` | `FunctionCalling` | |
| `agent_strategy_name` | `function_calling` | |
| `agent_strategy_provider_name` | 实例特定，需从模板提取 | 决定策略插件 |
| `plugin_unique_identifier` | 含版本哈希的完整标识符 | **缺此字段报"不支持 MCP 工具"** |
| `output_schema` | `{}` | |
| `tool_node_version` | `2` | 整数 |
| `memory` | 完整结构 | |
| `meta.minimum_dify_version` | 实例特定 | |

**重要**：`plugin_unique_identifier` 必须包含精确的版本哈希。此字段无法编造——从已安装插件的实际导出中复制。

### Workflow 模式（`mode: workflow`）

适用场景：工具调用顺序固定、不需要 LLM 动态决策。
- MCP 工具必须作为独立 Tool 节点（不能嵌入 Agent）
- Tool 节点需：`provider_type: mcp`、`is_team_authorization: true`、`tool_node_version: '2'`
- LLM 节点无法动态调用工具——需要预编排固定的工具调用序列

---

## 节点速查

### Start 节点变量

```python
{'default': '20', 'hint': '', 'label': '变量标签',
 'max_length': 10, 'options': [], 'placeholder': '',
 'required': False, 'type': 'number', 'variable': 'var_name'}
```

类型：`number` | `text-input` | `paragraph` | `select` | `checkbox`

### Agent 节点结构

```python
{
    'agent_parameters': {
        'instruction': {'type': 'constant', 'value': 'system prompt'},
        'maximum_iterations': {'type': 'constant', 'value': 15},
        'model': {'type': 'constant', 'value': {
            'completion_params': {'temperature': 0.3, ...},
            'mode': 'chat',
            'model': '<model_name>',
            'model_type': 'llm',
            'provider': '<marketplace_provider>',
            'type': 'model-selector',
        }},
        'query': {'type': 'constant', 'value': '用户输入'},
        'tools': {'type': 'constant', 'value': [...]},
    },
    'agent_strategy_label': 'FunctionCalling',
    'agent_strategy_name': 'function_calling',
    'agent_strategy_provider_name': '<从模板提取>',
    'plugin_unique_identifier': '<从模板提取，含版本哈希>',
    'output_schema': {},
    'tool_node_version': 2,
    'memory': {
        'query_prompt_template': '{{#sys.query#}}',
        'role_prefix': {'assistant': '', 'user': ''},
        'window': {'enabled': False, 'size': None},
    },
    'meta': {'minimum_dify_version': '<实例版本>'},
}
```

**Provider 格式规则**：
- Agent 节点内模型 provider 使用 marketplace 版本（路径含 `-mx` 后缀，如 `xxx-mx/yyy-mx/zzz-mx`）
- 独立 LLM 节点使用非 marketplace 版本（路径不含 `-mx`，如 `xxx/yyy/zzz`）
- 具体值因 Dify 实例配置而异，从模板中提取

### MCP 工具定义

```python
tool = {
    'enabled': True,
    'extra': {'description': '工具描述（会传给 LLM）'},
    'parameters': {
        'paramName': {'auto': 1, 'value': None},
    },
    'provider_name': '<mcp_provider>',
    'provider_show_name': '<显示名>',
    'schemas': [{
        'auto_generate': None, 'default': None, 'form': 'llm',
        'human_description': {'en_US': 'desc', 'zh_Hans': '描述'},
        'label': {'en_US': 'paramName', 'zh_Hans': 'paramName'},
        'llm_description': 'LLM-facing description',
        'name': 'paramName', 'type': 'string',
        'required': True, 'options': [],
        'placeholder': None, 'max': None, 'min': None,
        'precision': None, 'scope': None, 'template': None,
    }],
    'settings': {},
    'tool_description': '简短描述',  # 容易遗漏
    'tool_label': 'display_name',
    'tool_name': 'actual_tool_name',
    'type': 'mcp',
}
```

**注意**：`tool_description` 字段容易遗漏。缺失不会导致导入失败，但可能导致 LLM 无法正确理解工具用途。

### LLM 节点（Workflow 模式）

```python
llm_node = {
    'model': {
        'completion_params': {'temperature': 0.7, ...},
        'mode': 'chat',
        'name': '<model_name>',
        'provider': '<non_marketplace_provider>',
    },
    'prompt_template': [
        {'id': '<uuid>', 'role': 'system', 'text': '系统提示词'},
        {'id': '<uuid>', 'role': 'user', 'text': '{{#node_id.text#}}'},
    ],
    'type': 'llm',
    'vision': {'enabled': False},
    'context': {'enabled': False, 'variable_selector': []},
}
```

### Edge 连接

```python
edge = {
    'data': {'isInLoop': False, 'sourceType': '<type>', 'targetType': '<type>'},
    'id': '<f"{src}-source-{tgt}-target">',
    'source': '<src_id>', 'sourceHandle': 'source',
    'target': '<tgt_id>', 'targetHandle': 'target',
    'selected': False, 'type': 'custom', 'zIndex': 0,
}
```

`sourceType` / `targetType` 取值：`start` | `agent` | `llm` | `code` | `tool` | `answer`

### Answer 节点

```python
answer_node = {
    'data': {
        'answer': '{{#<agent_id>.text#}}',
        'selected': False,
        'title': '输出',
        'type': 'answer',
        'variables': [],  # 必须存在，即使为空
    },
    'id': '<id>',
    'position': {'x': 700, 'y': 282},
    'positionAbsolute': {'x': 700, 'y': 282},
    'type': 'custom', 'width': 242, 'height': 103,
}
```

---

## 变量引用规范

### 基本格式

```
{{#节点ID.变量名#}}
```

**Python f-string 生成**：

```python
# ❌ 缺少闭合 #}}——产出的引用不会被解析
f"{{{{#{sid}.var}}}}"     # → {{#id.var}}
# ✅ 正确
f"{{{{#{sid}.var#}}}}"    # → {{#id.var#}}
```

**YAML 注意事项**：`{{` 会被解析为 flow mapping。非 block scalar 的值需加引号包裹。

### 系统变量

```
{{#sys.query#}}              # 用户输入
{{#sys.files#}}              # 上传文件
{{#sys.conversation_id#}}    # 对话ID
{{#sys.user_id#}}            # 用户ID
```

### 节点输出变量

```
{{#node_id.text#}}           # LLM/Agent 文本输出
{{#code_node.result#}}       # Code 节点输出变量
{{#param_node.param_name#}}  # Parameter Extractor 提取结果
```

### 数组与对象访问

```
{{#node_id.array.0#}}        # 数组第一个元素
{{#node_id.object.key#}}     # 对象属性
```

---

## 补充节点类型

### Code 节点

```python
code_node = {
    'data': {
        'code': "def main(arg1: str) -> dict:\n    return {'result': arg1}",
        'code_language': 'python3',
        'outputs': {
            'result': {'children': None, 'type': 'string'},
        },
        'title': '代码执行',
        'type': 'code',
        'variables': [{
            'value_selector': ['source_node_id', 'var_name'],
            'value_type': 'string',
            'variable': 'arg1',
        }],
    },
    # ... standard node fields ...
}
```

输出类型：`string` | `number` | `object` | `array[string]` | `array[number]` | `array[object]`

### If-Else 条件节点

```python
if_node = {
    'data': {
        'cases': [{
            'case_id': 'true',
            'conditions': [{
                'comparison_operator': 'contains',  # is / is not / contains / empty / >
                'id': '<uuid>',
                'value': '期望值',
                'variable_selector': ['node_id', 'var_name'],
            }],
            'id': 'true',
            'logical_operator': 'and',  # 多条件之间: and / or
        }],
        'logical_operator': 'or',  # 多 case 之间
        'title': '条件判断',
        'type': 'if-else',
    },
}
```

比较运算符：`is` | `is not` | `contains` | `not contains` | `start with` | `end with` | `empty` | `not empty` | `>` | `<` | `>=` | `<=`

### HTTP Request 节点（Workflow 模式）

```python
http_node = {
    'data': {
        'authorization': {'config': None, 'type': 'no-auth'},  # or 'bearer', 'api-key'
        'body': {'data': '{"key": "value"}', 'type': 'json'},
        'headers': '',
        'method': 'post',  # get / post / put / patch / delete
        'timeout': {'max_connect_timeout': 0, 'max_read_timeout': 0, 'max_write_timeout': 0},
        'title': 'HTTP请求',
        'type': 'http-request',
        'url': 'https://api.example.com/endpoint',
    },
}
```

---

## 坐标布局

Dify 画布使用笛卡尔坐标系，节点位置由 `position` 和 `positionAbsolute` 双字段定义（值相同即可）。

**推荐间距**：
- 水平间距：300-400px
- 垂直间距：保持同一水平线（如 y=282），分支节点 ±150px

**基本布局**：
```
Start(60, 282) → Agent(380, 282) → Answer(700, 282)
```

**分支布局**：
```
                   → Branch1(700, 150)
If-Else(380, 282) →
                   → Branch2(700, 450)
```

**节点尺寸参考**：

| 节点类型 | 宽度 | 高度 |
|---------|------|------|
| Start | 242 | 54-150 |
| Agent | 242 | 100 |
| LLM | 242 | 88-90 |
| Code | 242 | 54 |
| Tool | 242 | 84-90 |
| If-Else | 242 | 120-170 |
| Answer | 242 | 103 |
| HTTP | 242 | 90 |

---

## 完整示例

```python
import yaml

with open('template.yml', encoding='utf-8') as f:
    app = yaml.safe_load(f)

# 改元数据
app['app']['name'] = '我的应用'
app['app']['description'] = '描述'
app['app']['icon'] = '🤖'
app['app']['icon_type'] = 'emoji'

# 找节点
for n in app['workflow']['graph']['nodes']:
    if n['data']['type'] == 'start':
        sid = n['id']
        n['data']['variables'] = [{...}]
    if n['data']['type'] == 'agent':
        aid = n['id']
        n['data']['title'] = '我的Agent'
        n['data']['agent_parameters']['instruction']['value'] = 'system prompt'
        n['data']['agent_parameters']['tools']['value'] = [...]
        n['data']['agent_parameters']['query']['value'] = '用户输入'

# 精简为 Start → Agent → Answer
app['workflow']['graph']['nodes'] = [start, agent, answer]
app['workflow']['graph']['edges'] = [
    make_edge(sid, aid, 'start', 'agent'),
    make_edge(aid, 'ans1', 'agent', 'answer'),
]

with open('output.yml', 'w', encoding='utf-8', newline='\n') as f:
    yaml.dump(app, f, allow_unicode=True, default_flow_style=False,
              sort_keys=False, indent=2, width=1000)
```

---

## 踩坑记录

| 现象 | 根因 | 修复 |
|------|------|------|
| 导入后报 "不支持 MCP 工具" | 缺 `plugin_unique_identifier` / `output_schema` / `tool_node_version` | 从模板拷贝这三个字段 |
| 导入无明确错误信息直接失败 | `Write` 工具写出的 YAML 格式不兼容 | 用 Python yaml.dump 输出 |
| Workflow 模式 Agent 无法使用 MCP | 该模式下 Agent 内嵌 MCP 工具不支持 | 切到 advanced-chat 模式，或改为独立 Tool 节点 |
| 变量引用解析失败 | prompt 中 `{{#node_id.var#}}` 的 node_id 写错 | 从模板提取真实 ID |
| 导入成功但 Agent 行为异常 | tools 缺 `tool_description` 或 `extra.description` 为空 | 补充描述字段 |
| 环境变量在 prompt 中引用失效 | `{{#sys.query#}}` 需配合 Agent 的 `query` 字段使用 | 确保 prompt 变量来源正确 |
| 多次编辑后文件编码损坏 | Write + Edit 多次操作累积编码问题 | 最终文件用 Python yaml.dump 重写 |
| JSON 示例花括号被转义 | Python f-string 中 `{{{{}}}}` 输出为 `{{}}` 而非 `{}` | 将 JSON 字符串定义为独立 Python 变量再传入 f-string |
| Agent 忽略 JSON 格式约束 | prompt 中的 JSON 示例因转义错误而语法无效 | 生成后用 assert 校验 `{"question"` 等子串存在于 prompt 中 |

---

