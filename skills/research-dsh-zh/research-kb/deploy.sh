#!/usr/bin/env bash
# P5 部署：把 research-kb 装进 skill 仓与 DSH_HOME。
#
# **这个脚本会写本仓之外的两个位置**（skill 仓 + /root/.dsh），
# 故刻意做成一个可复核、可重跑、能自查的脚本，而不是一串手敲的命令：
#
#   1. skills/research-kb/  →  <skill repo>/skills/research-dsh-zh/research-kb/
#   2. /root/.dsh/skills/research-kb  →  symlink 到上面那个目录
#   3. <skill repo>/scripts/install-dsh.sh 的技能清单里加上 research-kb
#   4. <skill repo>/skills/research-dsh-zh/research/SKILL.md 插两处：
#        Step 1 之前查重 / Step 5 之后落盘
#
# 纪律：
#   * **只动上面这四处**，`git add` 也只加这几个路径 —— 目标仓里别人的
#     未提交改动一概不碰、不提交；
#   * 幂等：重复跑不会重复插入；`--check` 只报告不写。
#
# 用法：
#   bash skills/research-kb/deploy.sh --check     # 只看现状
#   bash skills/research-kb/deploy.sh             # 部署（写文件，不提交）
#   bash skills/research-kb/deploy.sh --commit    # 部署并提交（仅限本脚本改的路径）
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${SKILL_REPO:-/root/Working/Deep-Research-skills}"
DST_REL="skills/research-dsh-zh/research-kb"
DST="$REPO/$DST_REL"
DSH_HOME="${DSH_HOME:-/root/.dsh}"
LINK="$DSH_HOME/skills/research-kb"
RESEARCH_SKILL="$REPO/skills/research-dsh-zh/research/SKILL.md"
INSTALLER="$REPO/scripts/install-dsh.sh"

CHECK=0
COMMIT=0
for a in "$@"; do
  case "$a" in
    --check) CHECK=1 ;;
    --commit) COMMIT=1 ;;
    *) echo "未知参数：$a" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
ok()  { printf '  ✓ %s\n' "$*"; }
no()  { printf '  · %s\n' "$*"; }

[ -d "$REPO/.git" ] || { say "目标不是 git 仓：$REPO"; exit 1; }
say "skill 仓：$REPO"
say "DSH_HOME：$DSH_HOME"
say ""

# ---------------------------------------------------------------- 1 复制
say "1/4 复制 skill 内容"
if [ "$CHECK" = 1 ]; then
  if diff -rq "$SRC" "$DST" >/dev/null 2>&1; then ok "已是最新"; else no "需要同步（或尚无）"; fi
else
  mkdir -p "$DST"
  # 只同步本 skill 的文件；不用 rsync --delete，免得误删对方目录里的东西
  cp -f "$SRC/SKILL.md" "$DST/SKILL.md"
  [ -f "$SRC/deploy.sh" ] && cp -f "$SRC/deploy.sh" "$DST/deploy.sh"
  ok "已写入 $DST_REL/"
fi

# ---------------------------------------------------------------- 2 symlink
say "2/4 DSH_HOME symlink"
if [ -L "$LINK" ] && [ "$(readlink "$LINK")" = "$DST" ]; then
  ok "已是正确 symlink"
elif [ "$CHECK" = 1 ]; then
  no "需要建立：$LINK → $DST"
else
  mkdir -p "$DSH_HOME/skills"
  if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
    say "  [停止] $LINK 已存在且不是 symlink —— 不覆盖真实目录"; exit 1
  fi
  ln -sfn "$DST" "$LINK"
  ok "$LINK → $DST"
fi

# ---------------------------------------------------------------- 3 安装脚本
say "3/4 install-dsh.sh 技能清单"
if grep -q "research-kb" "$INSTALLER"; then
  ok "清单里已有 research-kb"
elif [ "$CHECK" = 1 ]; then
  no "清单里缺 research-kb"
else
  python3 - "$INSTALLER" <<'PY'
import re, sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding='utf-8')
m = re.search(r'^(\s*)for d in ([^;]+); do$', t, re.M)
assert m, "找不到安装脚本里的技能清单循环"
names = m.group(2).split()
if "research-kb" not in names:
    names.append("research-kb")
t = t[:m.start(2)] + " ".join(names) + t[m.end(2):]
p.write_text(t, encoding='utf-8')
print("  已加入:", " ".join(names))
PY
  ok "已加进清单"
fi

# ---------------------------------------------------------------- 4 /research
say "4/4 /research 的 SKILL.md"
MARK_A="<!-- kb:lookup -->"
MARK_B="<!-- kb:persist -->"
if grep -q "$MARK_A" "$RESEARCH_SKILL"; then
  ok "两处插入都已在"
elif [ "$CHECK" = 1 ]; then
  no "需要在 Step 1 之前与 Step 5 之后各插一段"
else
  python3 - "$RESEARCH_SKILL" <<'PY'
import sys, pathlib
p = pathlib.Path(sys.argv[1]); t = p.read_text(encoding='utf-8')

LOOKUP = '''<!-- kb:lookup -->
### Step 0.9: 查重（澳门调研本体，若本机存在）

立项之前先问一句「这家/这个议题查过没有」。命中就**只补空缺**，别重查已有证据的字段。

```bash
/root/Working/Macao/macao_ontology/bin/kb lookup "<item 名字>"
/root/Working/Macao/macao_ontology/bin/kb fields <entity-id>   # 已覆盖 / 空缺
```

三种回答**含义不同**：命中=查过；`未登记：「X」`=没查过；报错/库为空=**不可判定**
（不等于没查过）。非澳门调研话题可跳过本步。

'''

PERSIST = '''<!-- kb:persist -->
### Step 5.5: 落盘进本体（澳门调研本体，若本步产出属于它）

结论收工后经受控通道写进本体 —— **先看要写什么，再真写**：

```bash
/root/Working/Macao/macao_ontology/bin/onto import --dry-run
/root/Working/Macao/macao_ontology/bin/onto import
```

写入只走 `execute_action`（唯一写路径），须署名 `cause`；悬空引用会拦住整条写入；
已存在的断言走 `UpdateClaim`（版本 +1），不会用 create 覆盖。

'''

anchor_a = "## 模式 A：表格模式\n"
assert anchor_a in t, "找不到「## 模式 A：表格模式」"
t = t.replace(anchor_a, anchor_a + "\n" + LOOKUP, 1)

anchor_b = "## 输出路径\n"
assert anchor_b in t, "找不到「## 输出路径」"
t = t.replace(anchor_b, PERSIST + anchor_b, 1)

p.write_text(t, encoding='utf-8')
print("  已插入 Step 0.9 与 Step 5.5")
PY
  ok "已插入两处"
fi

# ---------------------------------------------------------------- 提交
say ""
if [ "$CHECK" = 1 ]; then
  say "[check] 未写任何东西。"
  exit 0
fi

cd "$REPO"
say "改动（只列本脚本涉及的路径）："
git status --porcelain -- "$DST_REL" scripts/install-dsh.sh \
  skills/research-dsh-zh/research/SKILL.md

if [ "$COMMIT" = 1 ]; then
  git add "$DST_REL" scripts/install-dsh.sh skills/research-dsh-zh/research/SKILL.md
  git commit -q -F - <<'MSG'
feat(dsh): 新增 research-kb skill（澳门调研本体的读写面）

- research-kb：立项前查重（lookup/fields）、收工落盘（经 execute_action）、
  回看改动史与引用解析状态（history，三值：可解析/悬空/不可判定）
- research/SKILL.md：Step 1 之前插查重、Step 5 之后插落盘
- install-dsh.sh：技能清单加入 research-kb
- 命令走 /root/Working/Macao/macao_ontology/bin/{kb,onto} 薄包装，
  解释器与路径固化，任何 cwd 下都能跑

注：本提交只含上面三个路径；仓内 docx-report 的未提交改动未触碰。
MSG
  say ""
  say "已提交："
  git log --oneline -1
else
  say ""
  say "未提交（加 --commit 提交；只提交上面这几个路径）。"
fi
