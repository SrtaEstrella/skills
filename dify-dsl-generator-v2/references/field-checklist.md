# Agent 节点 MCP 兼容性 —— 必填字段清单

基于已验证 DSL 导出，以下字段是导入器验证 MCP 支持的关键项：

## data 层（与 agent_parameters 同级）

| 字段 | 值 | 备注 |
|------|-----|------|
| `agent_strategy_label` | `FunctionCalling` | |
| `agent_strategy_name` | `function_calling` | |
| `agent_strategy_provider_name` | `langgenius/agent/agent` | |
| `plugin_unique_identifier` | `langgenius/agent:0.0.37@a5dcc6ea...` | **关键**：含版本哈希，缺失则报"不支持 MCP" |
| `output_schema` | `{}` | |
| `tool_node_version` | `2` | 整数 |
| `memory` | `{query_prompt_template, role_prefix, window}` | |
| `meta` | `{minimum_dify_version: '1.7.0'}` | |

## agent_parameters 层

| 字段 | 类型 |
|------|------|
| `instruction` | `{type: constant, value: '...'}` |
| `maximum_iterations` | `{type: constant, value: 15}` |
| `model` | `{type: constant, value: {...}}` |
| `query` | `{type: constant, value: '...'}` |
| `tools` | `{type: constant, value: [...]}` |

## model.value 内部

```yaml
completion_params:
  enable_thinking: false
  temperature: 0.3
mode: chat
model: alb_model_2601
model_type: llm
provider: langgenius-mx/openai_api_compatible-mx/openai_api_compatible-mx
type: model-selector
```

## MCP 工具定义必填字段

每个工具对象：
- `enabled` (bool)
- `extra` (dict, 至少含 `description`)
- `parameters` (dict, 每个参数 `{auto: 1, value: null}`)
- `provider_name` (string)
- `provider_show_name` (string)
- `schemas` (list, 每个参数一个 schema 对象)
- `settings` (dict, 可为 `{}`)
- `tool_description` (string) **← 容易遗漏**
- `tool_label` (string)
- `tool_name` (string)
- `type` (string, `"mcp"`)

## Schema 对象

每个参数：
```yaml
- auto_generate: null
  default: null
  form: llm
  human_description: {en_US: ..., zh_Hans: ...}
  label: {en_US: param_name, zh_Hans: param_name}
  llm_description: ...
  name: param_name
  type: string  # 或 boolean, number
  required: true  # 或 false
  options: []
  placeholder: null
  max: null
  min: null
  precision: null
  scope: null
  template: null
```

---

## Python f-string 花括号陷阱

Prompt 中包含 JSON 示例时，不要在 f-string 内转义多层花括号：

```python
# ❌ f-string: {{{{ 输出为 {{ 而非 {
# ❌ Agent 读到语法错误的 JSON 会退回到插件默认行为

# ✅ 正确：独立 Python 变量
json_example = '{"question":"...", "correct":"A"}'
prompt = f"格式：{json_example}"
```

生成后用 `assert` 校验 JSON 子串确实存在于 prompt 中。
