# Research Deep - 深度调研

## 触发方式
`/research-deep [outline路径]`（可选参数：显式指定 outline.yaml 路径；多 topic 并行调研时必须提供）

## 执行流程

### Step 1: 定位Outline
按优先级定位 outline：
1. 用户触发时显式给出的路径（如 `/research-deep macau-policy/outline.yaml`），直接使用；
2. 否则在当前工作目录查找 `*/outline.yaml` 文件：
   - 只找到 1 个 → 直接使用；
   - 找到多个 → 用 `ask_user_question` 工具列出候选 topic 目录让用户选择，禁止静默取第一个。

读取items列表、execution配置（含items_per_agent）。

### Step 2: 断点续传检查
- 检查output_dir下已完成的JSON文件
- 跳过已完成的items

### Step 3: 分批执行
- 按batch_size分批（完成一批需要得到用户同意才可进行下一批）
- 每个子代理负责items_per_agent个项目
- 通过 `subagent` 工具后台并行启动 web-search 子代理（`run_in_background: true`；子代理文本回复无需收集，结果由输出文件承载）

**子代理启动方式（DSH）**：
1. 用 `read` 工具读取 `/root/.dsh/agents/web-search-agent.md` 全文，作为子代理 prompt 的 preamble（web-search 研究员人设与策略模块加载纪律）；
2. 子代理完整 prompt = preamble + 空行 + 下方 Prompt 模板渲染结果（仅替换变量，不改结构）；
3. 用 `subagent` 工具启动（`run_in_background: true`），description 填 `research-deep: {item_name}`。

**参数获取**：
- `{topic}`: outline.yaml中的topic字段
- `{item_name}`: item的name字段
- `{item_related_info}`: item的完整yaml内容（name + category + description等）
- `{output_dir}`: outline.yaml中execution.output_dir（默认./results）
- `{fields_path}`: {topic}/fields.yaml的绝对路径
- `{output_path}`: {output_dir}/{item_name_slug}.json的绝对路径（slugify处理item_name：空格替换为_，移除特殊字符）

**硬约束**：以下prompt必须严格复述，仅替换{xxx}中的变量，禁止改写结构或措辞。

**Prompt模板**：
```python
prompt = f"""## 任务
调研 {item_related_info}，输出结构化JSON到 {output_path}

## 字段定义
读取 {fields_path} 获取所有字段定义

## 输出要求
1. 按fields.yaml定义的字段输出JSON
2. 网络检索无法确认的字段值标注[不确定]
3. 需要实地调研（访谈/问卷/内部数据）才能获得的字段值标注[待调研]——如机构年度预算、内部使用率、采购计划、支付意愿等网络上不存在的信息
4. JSON末尾添加uncertain数组（列出所有标注[不确定]的字段名）和pending_research数组（每个元素为{{"field": 字段名, "reason": 为何需实地调研, "suggested_method": 建议获取方式，如访谈某机构/发放问卷/调取内部数据}}）
5. 所有字段值必须使用中文输出（调研过程可用英文，但最终JSON值为中文）
6. JSON顶层添加sources对象，为每个有网络来源支撑的字段记录来源：{{"<字段名>": {{"url": 来源URL, "access_date": "YYYY-MM-DD", "note": 关键数据或文号摘录(可选)}}}}；政策、法规、统计类字段须在note中记录文号与发布日期

## 输出路径
{output_path}

## 验证
完成JSON输出后，运行验证脚本确保字段完整覆盖：
python3 /root/.dsh/skills/research/validate_json.py -f {fields_path} -j {output_path}
验证通过后才算完成任务。
"""
```

**One-shot示例**（假设调研GitHub Copilot）：
```
## 任务
调研 name: GitHub Copilot
category: 国际产品
description: Microsoft/GitHub开发，首个主流AI编程助手，市场份额约40%，输出结构化JSON到 {project_dir}/results/GitHub_Copilot.json

## 字段定义
读取 {project_dir}/fields.yaml 获取所有字段定义

## 输出要求
1. 按fields.yaml定义的字段输出JSON
2. 网络检索无法确认的字段值标注[不确定]
3. 需要实地调研（访谈/问卷/内部数据）才能获得的字段值标注[待调研]——如机构年度预算、内部使用率、采购计划、支付意愿等网络上不存在的信息
4. JSON末尾添加uncertain数组（列出所有标注[不确定]的字段名）和pending_research数组（每个元素为{"field": 字段名, "reason": 为何需实地调研, "suggested_method": 建议获取方式，如访谈某机构/发放问卷/调取内部数据}）
5. 所有字段值必须使用中文输出（调研过程可用英文，但最终JSON值为中文）
6. JSON顶层添加sources对象，为每个有网络来源支撑的字段记录来源：{"<字段名>": {"url": 来源URL, "access_date": "YYYY-MM-DD", "note": 关键数据或文号摘录(可选)}}；政策、法规、统计类字段须在note中记录文号与发布日期

## 输出路径
{project_dir}/results/GitHub_Copilot.json

## 验证
完成JSON输出后，运行验证脚本确保字段完整覆盖：
python3 /root/.dsh/skills/research/validate_json.py -f {project_dir}/fields.yaml -j {project_dir}/results/GitHub_Copilot.json
验证通过后才算完成任务。
```

### Step 4: 等待与监控
- 等待当前批次完成（DSH 会在每个后台子代理完成时向父代理发送完成通知，无需轮询）
- 启动下一批
- 显示进度

### Step 5: 汇总报告
全部完成后输出：
- 完成数量
- 失败/[不确定]标记的items
- [待调研]缺口统计：缺口总数、涉及items、按建议获取方式分布（该清单将在 `/research-report` 骨架模式中汇总为二阶段实地调研缺口清单）
- 输出目录

## Agent配置
- 后台执行: 是（`subagent` 工具，`run_in_background: true`）
- 子代理文本输出: 无需收集（子代理有明确输出文件，父代理通过完成通知与输出文件监控）
- 断点续传: 是
