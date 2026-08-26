---
name: research-add-items
user-invocable: true
description: 向现有调研outline补充items（调研对象）。
---

# Research Add Items - 补充调研对象

## 触发方式
`/research-add-items`

## 执行流程

### Step 1: 自动定位Outline
在当前工作目录查找 `*/outline.yaml` 文件，自动读取。

### Step 2: 并行获取补充来源
同时进行：
- **A. 询问用户**：用 `ask_user_question` 工具询问需要补充哪些items？有具体名称吗？
- **B. 询问是否需要Web Search**：是否启动 web-search 子代理搜索更多items？（启动方式同 `/research`：用 `read` 工具读取 `~/.dsh/agents/web-search-agent.md` 全文作为子代理 prompt preamble，`subagent` 工具后台启动）

### Step 3: 合并更新
- 将新items追加到outline.yaml
- 展示给用户确认
- 避免重复
- 保存更新后的outline

## 输出
更新后的 `{topic}/outline.yaml` 文件（原地修改）
