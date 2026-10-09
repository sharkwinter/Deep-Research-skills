---
name: research-kb
user-invocable: true
description: 澳门调研本体的读写面。立项前查「这家/这个议题查过没有、哪些字段已有证据」，收工后把带证据的结论经受控通道落进本体，并回看改动史与引用解析状态。是 /research 的 sub-skill。
---

# research-kb — 调研知识库的读写面

## 它解决什么

调研最贵的浪费不是没查到，是**重复查已经查过的东西**，以及**查完了下次找不到**。
本 skill 把「查重」放到立项之前、把「落盘」放在收工之时，中间不另造一套存储：
数据就在本体里，读写都走同一条受控通道。

## 触发方式

- 直接调用：`/research-kb lookup <名字>`
- 作为 `/research` 的 sub-skill：`/research` 的 **Step 1 之前查重**、
  **Step 5 之后落盘**（见文末「挂进 /research」）

## 前置条件（先确认，别猜）

```bash
# 1) 本体库在哪、有没有东西
/root/Working/Macao/macao_ontology/bin/onto plan --store sqlite

# 2) 证据面是否就绪（引用解析得住才有意义）
/root/Working/Macao/tools/evidence_archive.py  # 用 python3 跑 stats
```

若 `runtime/onto.db` 不存在：说明本体还没建。跑一次
`/root/Working/Macao/macao_ontology/bin/onto import` 建库（见 `P4_IMPORT_REPORT.md`）。

## 命令一览（全部只读，除 `import`）

| 目的 | 命令 |
|---|---|
| 查重：这家/这个议题查过没有 | `/root/Working/Macao/macao_ontology/bin/kb lookup <名字或 slug>` |
| 取带证据的断言 | `/root/Working/Macao/macao_ontology/bin/kb claims <entity-id> [--field F_算力]` |
| 已覆盖 / 空缺字段 | `/root/Working/Macao/macao_ontology/bin/kb fields <entity-id> [--against fields.json]` |
| 回看：改动史 + 引用解析状态 | `/root/Working/Macao/macao_ontology/bin/kb history <object-id>` |
| 落盘（**唯一写路径**） | `/root/Working/Macao/macao_ontology/bin/onto import [--dry-run]` |

## Step 1 · 立项前查重（**必做**）

```bash
/root/Working/Macao/macao_ontology/bin/kb lookup "$TARGET"
```

三种回答，**含义完全不同，不得混为一谈**：

| 回答 | 含义 | 动作 |
|---|---|---|
| 命中实体 + 断言数 + 覆盖章节 | **查过**，且知道查到哪一层 | 读 `claims` 复用，只补缺的章节 |
| `未登记：「X」` | **没查过** | 正常立项 |
| 命令报错 / 库为空 | **不可判定**（不是"没查过"） | 先修库，再说别的 |

> 「没查到」与「没查过」给同一个回答，是这套东西最不该犯的错。
> 故 `lookup` 对"没登记"与"库不可用"分开说。

**复用而不是重查**：命中之后先看 `fields <entity-id>`，只补空缺章节：

```bash
/root/Working/Macao/macao_ontology/bin/kb fields ent_amicro
/root/Working/Macao/macao_ontology/bin/kb claims ent_amicro --field F_算力
```

## Step 2 · 落盘（收工时）

**顺序不可换**：先经 `execute_action` 写本体，成功之后才落文件。

```bash
/root/Working/Macao/macao_ontology/bin/onto import --dry-run   # 先看要写什么
/root/Working/Macao/macao_ontology/bin/onto import             # 真写
```

落盘时被执行器强制的三件事（**不要试图绕过**）：

1. **`cause` 必填** —— 智能体发起必须与人工发起分得开。
   本通道署名 `{"kind": "pipeline", "ref": "importer:results-json"}`。
   你要用自己的 run id，就改 `channels/sources.py` 的 `IMPORTER_CAUSE`，
   **但不要留空**：分不开人与智能体，问责链就断在最要紧处。
2. **悬空引用拦整条写入** —— 证据地址必须解得开（`doc://`）。
   写不进去通常不是权限问题，是那条引用的出处不在。
3. **先查存在再选 Action** —— 已存在的 claim 走 `UpdateClaim`（版本 +1），
   不存在的才 `RecordClaim`。用 create 覆盖已存在对象，派生视图永远看不到更新。

## Step 3 · 回看（交付或复核时）

```bash
/root/Working/Macao/macao_ontology/bin/kb history clm_amicro__0001
```

它会给出三样东西：**改动史**（谁、何时、以什么 cause）、**证据分级**、
以及**每条引用解不解得开**（可解析 / 悬空 / 不可判定 —— 三值，不合并）。

> 「看不到」≠「没有」。审计为空时它会明说是查询没命中还是这个存储
> 接的是内存 sink。

## 数据现实（别指望它无所不知）

本库当前只覆盖**有逐字段证据**的那部分：38 份 `results/*.json` 里 4 份
（612 条带证据断言），其余 34 份是扁平结论、没有逐字段证据，
**没有硬造无据断言**。查不到的，很可能是那 34 份里的。

## 接口纪律

- **传输无关**：不依赖任何 MCP SDK；上面都是普通命令行。
- **每次调用都带 principal**：本 CLI 用 `kb-reader`（只读角色）；无匿名通道。
- **只读命令不写任何东西**；写只有 `entry.py import` 一条路。

## 挂进 `/research`

`/research` 的 SKILL.md 改两处即可（两行命令，不需要理解本体）：

| 位置 | 插入 |
|---|---|
| Step 1 之前 | 跑 `kb.py lookup <target>`；命中就只补空缺章节 |
| Step 5 之后 | 跑 `entry.py import --dry-run` 给人看一眼，再 `entry.py import` |

> 部署形态：本目录已在 Deep-Research-skills 仓内
> （`skills/research-dsh-zh/research-kb/`），`/root/.dsh/skills/research-kb`
> 是指向它的 symlink（与其余 skill 同款），`scripts/install-dsh.sh` 的
> 技能清单里也加了它。`/research` 的 SKILL.md 已在
> **Step 1 之前**插查重、**Step 5 之后**插落盘。
