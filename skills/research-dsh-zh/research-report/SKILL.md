# Research Report - 汇总报告

## 触发方式
`/research-report [outline路径或topic目录]`

## Step 0: 模式选择
定位 outline（见 Step 1 规则），读取其 execution 配置：
- 若存在 `report_skeleton` 字段（指向章节式报告骨架md文件）→ 执行**骨架模式**（见下方"骨架模式"章节）
- 否则 → 执行**目录模式**（默认：item横评汇总）

---

## 目录模式（默认：item横评汇总）

### Step 1: 定位结果目录
按优先级定位：
1. 用户触发时显式给出的 outline 路径或 topic 目录，直接使用；
2. 否则在当前工作目录查找 `*/outline.yaml`：
   - 只找到 1 个 → 直接使用；
   - 找到多个 → 用 `ask_user_question` 工具列出候选 topic 目录让用户选择，禁止静默取第一个。

读取topic和output_dir配置。

### Step 2: 扫描可选摘要字段
读取所有JSON结果，提取适合在目录中显示的字段（数值型、简短指标），例如：
- github_stars
- google_scholar_cites
- swe_bench_score
- user_scale
- valuation
- release_date

使用 `ask_user_question` 工具询问用户：
- 目录中除了item名称外，还需要显示哪些字段？
- 提供动态选项列表（基于实际JSON中存在的字段）

### Step 3: 生成Python转换脚本
在 `{topic}/` 目录下生成 `generate_report.py`，脚本要求：
- 读取output_dir下所有JSON
- 读取fields.yaml获取字段结构
- 覆盖每个JSON的所有字段值
- 跳过值包含[不确定]或[待调研]的字段
- 跳过uncertain数组中列出的字段
- 生成markdown报告格式：目录（带锚点跳转+用户选择的摘要字段）+ 详细内容（按字段分类）
- 保存到 `{topic}/report.md`

**目录格式要求**：

- 必须包含每一个item
- 每个item显示：序号、名称（锚点链接）、用户选择的摘要字段
- 示例：`1. [GitHub Copilot](#github-copilot) - Stars: 10k | Score: 85%`

#### 脚本技术要点（必须遵循）

**1. JSON结构兼容**
支持两种JSON结构：
- 扁平结构：字段直接在顶层 `{"name": "xxx", "release_date": "xxx"}`
- 嵌套结构：字段在category子dict中 `{"basic_info": {"name": "xxx"}, "technical_features": {...}}`

字段查找顺序：顶层 -> category映射key -> 遍历所有嵌套dict

**2. Category多语言映射**
fields.yaml的category名与JSON的key可能是任意组合（中中、中英、英中、英英）。必须建立双向映射：
```python
CATEGORY_MAPPING = {
    "基本信息": ["basic_info", "基本信息"],
    "技术特性": ["technical_features", "technical_characteristics", "技术特性"],
    "性能指标": ["performance_metrics", "performance", "性能指标"],
    "里程碑意义": ["milestone_significance", "milestones", "里程碑意义"],
    "商业信息": ["business_info", "commercial_info", "商业信息"],
    "竞争与生态": ["competition_ecosystem", "competition", "竞争与生态"],
    "历史沿革": ["history", "历史沿革"],
    "市场定位": ["market_positioning", "market", "市场定位"],
}
```

**3. 复杂值格式化**
- list of dicts（如key_events, funding_history）：每个dict格式化为一行，用` | `分隔kv
- 普通list：短列表用逗号连接，长列表换行显示
- 嵌套dict：递归格式化，用分号或换行显示
- 长文本字符串（超过100字符）：添加换行符`<br>`或使用blockquote格式，提高可读性

**4. 额外字段收集**
收集JSON中有但fields.yaml中没定义的字段，放入"其他信息"分类。注意过滤：
- 内部字段：`_source_file`, `uncertain`, `sources`, `pending_research`
- 嵌套结构顶级key：`basic_info`, `technical_features`等
- `uncertain`数组：需要逐行显示每个字段名，不要压缩成一行
- `pending_research`数组：不逐条展开，仅在文末统计缺口数量与涉及items

**5. 不确定值跳过**
跳过条件：
- 字段值包含`[不确定]`或`[待调研]`字符串
- 字段名在`uncertain`数组中
- 字段值为None或空字符串

### Step 4: 执行脚本
用 `bash` 工具运行 `python3 {topic}/generate_report.py`

## 输出（目录模式）
- `{topic}/generate_report.py` - 转换脚本
- `{topic}/report.md` - 汇总报告

---

## 骨架模式（章节式报告，report_skeleton 驱动）

适用：报告需按用户给定的章节提纲组织（如政策/产业调研报告），而非item横评目录。典型工作流："多topic深度调研 → 骨架模式组装初步报告 → 实地调研 → 补充修订"。

### R1: 读取配置
- 骨架文件：outline.yaml 的 `execution.report_skeleton` 指向的md文件（章节结构：章/节/要点）；用户也可显式指定路径
- topic 范围：骨架报告通常横跨多个 topic 目录（如"对标地区""政策法规""基础设施""需求行业"各一个topic）——收集当前工作目录下所有含 `outline.yaml` 的 topic 目录；若用户指定子集则只取指定项
- 读取各 topic 的 fields.yaml 与 output_dir 下所有 item JSON

### R2: 建立数据索引
- 汇总所有JSON：字段值 + sources（URL/访问日期/文号）+ uncertain + pending_research
- 建立 章节↔topic↔item↔字段 映射（骨架各章要点通常已指明对应对象类型；无法映射到item数据的章节标记为"主控推演章"）

### R3: 逐章组装（主控撰写，非脚本生成）
按骨架顺序逐章成文：
- 正文 = 主控叙事 + item JSON 数据表（表后标注来源：URL/文号/访问日期，与该字段的 sources 对应）
- 字段值为[不确定]的数据：正文引用时显式标注"（待核验）"
- 字段值为[待调研]的数据：不得作为论据写入结论，正文中仅以"（待实地调研确认）"提示，明细归入 R4 缺口清单
- 综合推演类章节（测算、方案比选、风险分析等）：由主控基于多个item数据推演，显式列出假设与推论边界，与引用事实明确区分
- 数据密集的表格可生成python脚本从JSON抽取，叙事由主控完成
- 引语纪律沿用 `/root/.dsh/skills/research/deep_narrative_playbook.md` 第五节之二（引号内必须可回源；交付前跑 quotecheck.py）

### R4: 调研缺口清单（二阶段实地调研输入）
汇总所有JSON的 pending_research 数组，在报告末尾生成"调研缺口清单"章节：
- 按建议获取方式/访谈对象分组（如：经科局、公职局、高校、企业……）
- 每条：缺口字段 | 所属对象(item) | 原因 | 建议访谈问题（可直接并入调研问卷）
- 末尾统计：缺口总数、涉及对象数、按类型分布
- 同步输出独立文件 `{报告目录}/调研缺口清单.md`，供二阶段实地调研直接使用

### R5: 证据基座
报告头部注明：调研日期、数据截止时间、覆盖topic与item数量、来源URL总数；文末参考文献章节列出全部来源（对象.字段 → URL → 访问日期）

### 输出（骨架模式）
- 报告：用户指定路径，或骨架文件同目录下 `report.md`
- `{报告目录}/调研缺口清单.md`（二阶段实地调研输入）
