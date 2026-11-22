# nimstack

My agent skills, installable on any machine with the [`skills` CLI](https://github.com/vercel-labs/skills).

## Install

Everything, for Claude Code and Codex, user-wide:

```sh
curl -fsSL https://raw.githubusercontent.com/nemo/nimstack/main/install.sh | bash
```

Options:

```sh
curl -fsSL .../install.sh | bash -s -- --project     # into the current project only
curl -fsSL .../install.sh | bash -s -- --dry-run     # print the commands, install nothing
NIMSTACK_AGENTS="claude-code cursor" bash install.sh # other agents
```

Just the skills that live in this repo:

```sh
npx skills add nemo/nimstack -g --all
```

Into a project from the lock file (pinned to exact commits): copy `skills-lock.json` into the project root, then run `npx skills install`.

Update later with `npx skills update -g`.

## What's in it

| Where | Skills |
| --- | --- |
| `skills/` (mine) | `arena` (my version of pstack's), `pstack-claude-code` (maps pstack's Cursor names to Claude Code) |
| [pstack](https://github.com/cursor/plugins/tree/main/pstack) | architect, how, why, blast-radius, correct, bro, ketchup, ketchup-video, unslop, statechart, principle-separate-before-serializing-shared-state, create/maintain-verification-skill, create/maintain-formal-verification-skill |
| [mattpocock/skills](https://github.com/mattpocock/skills) | implement, tdd, codebase-design, domain-modeling, grill-me, grilling, wayfinder, matt-code-review (`code-review`, renamed) |
| other | goalcraft (grp06/goalcraft), find-skills (vercel-labs/skills) |

## Changing the set

- **Add or remove an upstream skill:** edit `skills.txt`, then regenerate `skills-lock.json` (see below).
- **Make one of my own, or fork an upstream one:** put it in `skills/<name>/SKILL.md` and drop it from `skills.txt`.
- **Regenerate the lock file:** in an empty directory, run `bash /path/to/nimstack/install.sh --project`, then copy its `skills-lock.json` here.
