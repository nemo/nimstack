#!/usr/bin/env bash
# Install nimstack: nimstack's own skills plus the upstream skills in skills.txt.
#
#   curl -fsSL https://raw.githubusercontent.com/nemo/nimstack/main/install.sh | bash
#   curl -fsSL .../install.sh | bash -s -- --project      # into the current project instead
#   NIMSTACK_AGENTS="claude-code cursor" ./install.sh     # choose agents (default: claude-code codex)
#
# Needs Node (npx). Re-running is safe; use `npx skills update -g` to pull upstream changes.
set -euo pipefail

REPO="nemo/nimstack"
RAW="https://raw.githubusercontent.com/${REPO}/main"
read -r -a AGENTS <<< "${NIMSTACK_AGENTS:-claude-code codex}"

SCOPE=(-g)
DRY=0
for arg in "$@"; do
  case "$arg" in
    --project|-p) SCOPE=() ;;
    --dry-run)    DRY=1 ;;
    -h|--help)    sed -n '2,9p' "$0" 2>/dev/null || true; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

command -v npx >/dev/null || { echo "nimstack needs Node.js (npx). Install it first." >&2; exit 1; }

# Use the local manifest when run from a checkout, otherwise fetch it.
here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [[ -n "$here" && -f "$here/skills.txt" ]]; then
  manifest="$(cat "$here/skills.txt")"
else
  manifest="$(curl -fsSL "$RAW/skills.txt")"
fi

run() {
  echo "+ npx skills $*"
  if [[ $DRY -eq 0 ]]; then npx -y skills "$@" </dev/null; fi
}

# 1. nimstack's own skills.
run add "$REPO" ${SCOPE[@]+"${SCOPE[@]}"} -y -a "${AGENTS[@]}" -s '*'

# 2. Upstream skills, one `skills add` per manifest line.
while IFS= read -r line; do
  line="${line%%#*}"
  read -r -a words <<< "$line"
  [[ ${#words[@]} -lt 2 ]] && continue
  source="${words[0]}"
  skills=(); extra=()
  for ((i = 1; i < ${#words[@]}; i++)); do
    if [[ "${words[i]}" == --* ]]; then extra=("${words[@]:i}"); break; fi
    skills+=("${words[i]}")
  done
  run add "$source" ${SCOPE[@]+"${SCOPE[@]}"} -y -a "${AGENTS[@]}" ${extra[@]+"${extra[@]}"} -s "${skills[@]}"
done <<< "$manifest"

echo "nimstack installed."
