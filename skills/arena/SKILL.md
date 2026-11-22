---
name: arena
description: "Spawn N parallel candidates at the same task, pick a base, graft the strongest parts of the losers into it. Use for /arena, 'arena this', 'throw it in the arena', or when one attempt at a non-trivial artifact would lock in the wrong shape."
disable-model-invocation: true
---

# Arena

Track the six phases (Frame, Fan out, Cross-judge, Pick, Graft, Verify) with `TodoWrite` or the task tools if the session has them. Otherwise keep the list in your reply and update it at each phase. Open the list before launching anything.

## Phase A: Frame

Every candidate gets the same prompt, so the prompt is the contract.

1. State the artifact each candidate is producing.
2. Derive the rubric: 3-6 concrete, gradeable criteria for what success looks like on *this* task. It is the picker's tool in Phase D. Candidates see only the task, never the rubric.
3. Pick the runners. Spawn them with the `Agent` tool, `subagent_type: "general-purpose"`, and a `model` from the values the tool schema accepts (`fable`, `opus`, `sonnet`, `haiku`). The default panel is three seats, `fable`, `opus` and `sonnet`, so the candidates come from different models. If the schema rejects a value, drop that seat, keep at least two runners, and say so. Add seats for more design directions. When the work is about producing volume rather than judgment, you can give the same model several seats.
4. Set each seat's effort so the panel is Pareto optimal: no seat costs more than it adds to the quality of the result. Before choosing, look for a skill that covers effort or reasoning levels, first in the project (`.claude/skills/`, `CLAUDE.md`, `AGENTS.md`), then in the user's skills (`~/.claude/skills/`). If you find one, follow it. Otherwise, use the lowest effort that can still produce a strong candidate. Go higher only for subtle or hard judgment, and lower for routine generation. Pass the level as `effort` on each `Agent` call. This skill asks for it, so setting it is allowed. State the level you picked for each seat and why.
5. Give each candidate its own output location, per the **principle-separate-before-serializing-shared-state** skill. Inside a git repo, use `isolation: "worktree"` and name the branch or commit each worker starts from. Otherwise, use `<scratchpad>/arena-<slug>/candidate-<n>/`, where `<scratchpad>` is the session scratchpad.

## Phase B: Fan out

Spawn all N subagents in a single message, so they run in parallel in the background. Each brief contains:
- the task
- paths to the shared grounding (file paths, not pasted contents)
- its own output path
- instructions to produce the artifact and a short rationale that names the alternatives it considered and what it rejected

Subagents start with no context from this session, so make each brief stand alone. Wait for the completion notifications, and don't poll. Never guess or summarize a candidate before its result arrives.

If a candidate produces no output, go on with N-1 and note the dropout.

## Phase C: Cross-judge

Once every Phase B candidate is done, start one independent judge. Give it the rubric and the candidate paths, labeled `candidate-1..N` with no model names. It scores each candidate on each rubric criterion and recommends a base. You do your own Phase D reading while it runs.

Choose the judge in this order:
1. **Another vendor, when available.** If `codex` is on PATH, run it from a `general-purpose` agent or directly with Bash: `codex exec --sandbox read-only "<judge brief>"`. A different vendor's model is the strongest guard against bias toward Claude's own style.
2. **Otherwise, a different Claude model.** Spawn a `general-purpose` `Agent` whose `model` differs from this session's model and from as many runner seats as possible. Say that the judge is the same vendor as the runners.

Tell the judge not to edit any files. Afterward, check `git status` (or list the candidate directories) to confirm it didn't. Pick the judge's effort with the same Pareto rule as in Phase A. If no judge can run, skip this phase and say so.

## Phase D: Pick a base

Read every candidate end to end before picking. Score each one against the rubric, one criterion at a time, not on overall feel. If Phase C ran, compare your scores with the judge's. If you agree on the base, that confirms the pick. If you disagree, one of you is biased or the rubric was ambiguous, so read both rationales before deciding.

Pick the base that a future maintainer can extend most easily without breaking invariants. If two seem tied, prefer the one with the cleaner boundary or the smaller API: the smallest thing that solves the problem, with each decision made in one place.

## Phase E: Graft

Go through each losing candidate once more for anything worth porting into the base. Expect one or two things per candidate, not most of it. Work each graft in by hand: ask what the base would look like if that idea had been part of the design from the start, then carry the change through every reference, including types, docs and examples. Don't paste mechanically. The result should stay coherent under one mental model.

If the candidates converge on one shape, that is strong agreement. Note it and ship the shared shape, with no graft needed. If they diverge wildly, Phase A was under-specified, so reframe and re-run instead of averaging the divergence.

## Phase F: Verify

Verify the synthesized artifact against the real thing: run it, read the actual values, inspect the diff. Proxies such as a self-report or "it compiles" don't count, and a scripted check beats a one-time look. If verification finds a problem the arena missed, either Phase A was wrong (reframe and re-run) or a candidate caught it and you missed the graft (go back to Phase E). Don't paper over it.

Clean up worktrees and scratch directories you no longer need. Keep any the user might want to inspect, and say where they are.

## Outputs

One synthesized artifact, plus a short synthesis note alongside it that names:
- the base and why it was picked
- each seat's model and effort
- the cross-judge's model and verdict, or that Phase C was skipped
- each graft and the candidate it came from
- what was rejected and why
- any convergence or dropouts
- the verification result
