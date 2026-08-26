#!/usr/bin/env bash
# Install deep-research-skills into DeepSeek Harness (DSH).
#
# Usage:
#   bash scripts/install-dsh.sh [zh]
#
# - VARIANT: language variant to install (currently only "zh").
# - Skills   -> $DSH_HOME/skills/   (default ~/.dsh/skills)
# - Agent    -> $DSH_HOME/agents/   (web-search-agent.md + web-search-modules/)
#
# DSH has no named-agent registry (no ~/.claude/agents equivalent consumed by the
# harness): the research skills read web-search-agent.md themselves and inline its
# full text as the preamble of every `subagent` prompt. Web search uses DSH's
# built-in `web_search` tool, so no extra env var is required (no OPENCODE_ENABLE_EXA).
#
# The installer also rewrites the literal "~/.dsh" in installed text files to the
# absolute $DSH_HOME path, because DSH's `read` tool does not expand "~".

set -euo pipefail

VARIANT="${1:-zh}"
if [ "$VARIANT" != "zh" ]; then
  echo "ERROR: unsupported variant '$VARIANT' (currently only 'zh')." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILLS_SRC="$REPO_ROOT/skills/research-dsh-$VARIANT"
AGENTS_SRC="$REPO_ROOT/agents-dsh"

if [ ! -d "$SKILLS_SRC" ]; then
  echo "ERROR: skill source not found: $SKILLS_SRC" >&2
  exit 1
fi
if [ ! -f "$AGENTS_SRC/web-search-agent.md" ]; then
  echo "ERROR: agent source not found: $AGENTS_SRC/web-search-agent.md" >&2
  exit 1
fi

DSH_HOME_INPUT="${DSH_HOME:-$HOME/.dsh}"
mkdir -p "$DSH_HOME_INPUT"
DSH_HOME="$(cd "$DSH_HOME_INPUT" && pwd)"

mkdir -p "$DSH_HOME/skills" "$DSH_HOME/agents"

# 1. Skills: research / research-add-items / research-add-fields / research-deep / research-report
cp -R "$SKILLS_SRC/." "$DSH_HOME/skills/"

# 2. Web-search subagent persona + strategy modules
cp "$AGENTS_SRC/web-search-agent.md" "$DSH_HOME/agents/"
rm -rf "$DSH_HOME/agents/web-search-modules"
cp -R "$AGENTS_SRC/web-search-modules" "$DSH_HOME/agents/"

# 2b. Normalize permissions to owner-only (matches DSH's own preset-copy convention)
chmod -R go-rwx "$DSH_HOME/skills" "$DSH_HOME/agents"

# 3. Rewrite "~/.dsh" literals to the absolute DSH home (DSH's read tool does not expand ~)
python3 - "$DSH_HOME" <<'PY'
import os
import sys

root = sys.argv[1]
old = "~/.dsh"
changed = []
for base in ("skills", "agents"):
    for dirpath, _, files in os.walk(os.path.join(root, base)):
        for fn in files:
            if not fn.endswith((".md", ".py")):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if old in text:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text.replace(old, root))
                changed.append(path)
print(f"Rewrote '~/.dsh' -> {root} in {len(changed)} file(s)")
PY

# 4. Python dependency check (validate_json.py needs python3 + pyyaml)
if command -v python3 >/dev/null 2>&1; then
  if python3 -c "import yaml" 2>/dev/null; then
    echo "python3 + pyyaml: OK"
  else
    echo "WARNING: pyyaml is missing. Install it with:  pip install pyyaml" >&2
  fi
else
  echo "WARNING: python3 not found; validate_json.py requires it." >&2
fi

echo ""
echo "Installed skills to $DSH_HOME/skills:"
ls -1 "$DSH_HOME/skills"
echo ""
echo "Installed agent files to $DSH_HOME/agents:"
ls -1 "$DSH_HOME/agents"
echo ""
echo "Done. Open (or refresh) a DSH session and type:  /research <topic>"
echo "Follow-ups: /research-add-items, /research-add-fields, /research-deep, /research-report"
