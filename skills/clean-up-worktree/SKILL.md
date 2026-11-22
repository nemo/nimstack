---
name: clean-up-worktree
description: Tear down the herdr or Rex worktree this agent is running in once its work has merged. Deletes the branch (local, and remote if it still exists), removes the worktree and closes its herdr workspace or Rex session, which ends this agent process. Only when the user invokes /clean-up-worktree.
disable-model-invocation: true
---

# clean-up-worktree

Ends this session for good: the checkout is deleted and this agent's pane closes. Run it only when the user invoked `/clean-up-worktree`.

The script does the work: `~/.claude/skills/clean-up-worktree/scripts/clean_up_worktree.py`. Its docstring has the full contract.

## Steps

1. **Check.** Run it with no flags from the worktree root:

   ```bash
   python3 ~/.claude/skills/clean-up-worktree/scripts/clean_up_worktree.py
   ```

   It deletes nothing. It prints the workspace, branch, how the work reached the default branch, and a verdict:
   - `SAFE`: the tree is clean (package-lock.json rewrites ignored), and HEAD is either the head of a merged PR or already in `origin/<default>`.
   - `KEEP`: the reasons follow. Show them to the user and stop. Don't commit, push or stash to make it SAFE unless the user asks.
   - `CANNOT RUN`: not in a herdr pane or Rex session, the workspace isn't a linked worktree, or the shell is in a different checkout. Report it and stop.

2. **Say what is about to go, in one short message**, before running it, because nothing after step 3 reaches the user:
   - the branch (local, and `origin/<branch>` if it still exists),
   - the worktree path,
   - the herdr workspace id, or the Rex session id and label (the whole session is killed, every window in it),
   - that this session ends.

   Also name anything that matters for later, such as follow-ups still owed. This is the last thing the user will read from this agent.

3. **Execute** in the same response as that message:

   ```bash
   python3 ~/.claude/skills/clean-up-worktree/scripts/clean_up_worktree.py --execute
   ```

   The script works in this order, because closing the workspace kills this pane and nothing after it runs:
   1. It detaches HEAD and deletes the local branch.
   2. It deletes the remote branch if it still exists and the work is merged.
   3. It hands the teardown to a detached process and returns: under herdr, `herdr worktree remove --force --workspace <id>`; under Rex (`REX_SESSION` set), `git worktree remove --force <path>` then `rex session kill $REX_SESSION`.

   Three seconds later that process removes the checkout and closes the workspace or session, which ends this agent. If the agent is somehow still alive, it sends it SIGTERM.

   Make no further tool calls after this one.

## KEEP and `--discard`

Pass `--execute --discard` only when the user has said, in this conversation, that the unmerged or uncommitted work listed under KEEP may be lost. It skips the safety check. The branch is then deleted locally only; the remote branch is left alone.

## If something fails

- **Before step 3** (for example, the branch delete fails): the script stops with `FAILED:` and nothing else changes. Report it.
- **Teardown**: it logs to `~/.claude/clean-up-worktree.log`. If the workspace is still open afterwards, the log shows herdr's answer. Never run `herdr server stop`: every other workspace lives in that server.
