#!/usr/bin/env python3
"""Tear down the worktree this agent runs in: branch, workspace/session, agent.

Works under herdr (HERDR_ENV=1) and under Rex (REX_SESSION set). herdr wins if both are set.

  clean_up_worktree.py                 check only: print SAFE or KEEP and why (deletes nothing)
  clean_up_worktree.py --execute       check, then delete the branch, remove the worktree,
                                       close the herdr workspace, and end this agent
  clean_up_worktree.py --execute --discard
                                       same, but skip the safety check (loses unmerged work)
  --keep-agent                         never signal the agent process (testing against another
                                       workspace by setting HERDR_WORKSPACE_ID and the cwd)

Order matters, because closing the workspace kills every pane in it, this agent included:
  1. detach HEAD (git refuses to delete a branch that is checked out)
  2. delete the local branch, and the remote one if it still exists and the work is merged
  3. hand the teardown to a detached process, then return. It removes the checkout and closes
     the workspace, which ends this agent; if the agent process is still alive afterwards it
     sends it SIGTERM.
       herdr: `herdr worktree remove --force --workspace <id>`
       Rex:   `git worktree remove --force <path>`, then `rex session kill $REX_SESSION`
              (the whole Rex session goes, every window in it; Rex has no worktree command)

SAFE means: a clean working tree (package-lock.json rewrites ignored), and the branch's work is
on the default branch: a merged PR whose head is this commit, or HEAD already in origin/<default>.

Exit codes: 0 SAFE (or done), 2 KEEP, 1 cannot run here.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

LOG = Path.home() / '.claude' / 'clean-up-worktree.log'


def run(*cmd, cwd=None, check=False):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise SystemExit(f"FAILED: {' '.join(cmd)}\n{p.stderr.strip() or p.stdout.strip()}")
    return p


def git(*args, cwd, check=False):
    return run('git', *args, cwd=cwd, check=check).stdout.strip()


def die(message):
    print(f'CANNOT RUN: {message}')
    sys.exit(1)


def herdr_worktree(workspace_id):
    """This workspace's entry in `herdr worktree list`, or None."""
    p = run('herdr', 'worktree', 'list', '--workspace', workspace_id)
    if p.returncode != 0:
        die(f'herdr worktree list failed: {p.stderr.strip()}')
    result = json.loads(p.stdout)['result']
    for wt in result['worktrees']:
        if wt.get('open_workspace_id') == workspace_id:
            return wt, result['source']['repo_root']
    return None, result['source']['repo_root']


def rex_worktree(top):
    """(worktree dict, repo_root) for a linked git worktree at `top`; used under Rex."""
    gitdir = git('rev-parse', '--path-format=absolute', '--git-dir', cwd=top)
    common = git('rev-parse', '--path-format=absolute', '--git-common-dir', cwd=top)
    wt = {'path': top, 'branch': git('branch', '--show-current', cwd=top) or None,
          'is_linked_worktree': gitdir != common}
    return wt, os.path.dirname(common)


def agent_pid():
    """The nearest ancestor process that is the Claude Code agent, or None."""
    pid = os.getppid()
    while pid > 1:
        p = run('ps', '-o', 'ppid=,comm=', '-p', str(pid))
        if p.returncode != 0 or not p.stdout.strip():
            return None
        ppid, comm = p.stdout.strip().split(None, 1)
        if 'claude' in os.path.basename(comm).lower():
            return pid
        pid = int(ppid)
    return None


def default_branch(cwd):
    ref = git('symbolic-ref', '--quiet', 'refs/remotes/origin/HEAD', cwd=cwd)
    return ref.rsplit('/', 1)[-1] if ref else 'main'


def merged_pr(branch, head, cwd):
    """(number, url) of a merged PR from this branch whose head is HEAD, or None."""
    p = run('gh', 'pr', 'list', '--head', branch, '--state', 'merged',
            '--json', 'number,url,headRefOid', cwd=cwd)
    if p.returncode != 0:
        return None
    for pr in json.loads(p.stdout or '[]'):
        if pr['headRefOid'] == head:
            return pr['number'], pr['url']
    return None


def main():
    args = set(sys.argv[1:])
    unknown = args - {'--execute', '--discard', '--keep-agent'}
    if unknown or ('--discard' in args and '--execute' not in args):
        raise SystemExit(__doc__)
    execute, discard = '--execute' in args, '--discard' in args

    herdr = os.environ.get('HERDR_ENV') == '1' and os.environ.get('HERDR_WORKSPACE_ID')
    rex = not herdr and os.environ.get('REX_SESSION')
    if not herdr and not rex:
        die('not running inside a herdr pane or a Rex session '
            '(HERDR_ENV / HERDR_WORKSPACE_ID and REX_SESSION all unset)')
    workspace_id = os.environ['HERDR_WORKSPACE_ID'] if herdr else os.environ['REX_SESSION']
    kind = 'workspace' if herdr else 'rex session'

    top = git('rev-parse', '--show-toplevel', cwd=os.getcwd())
    if not top:
        die(f'{os.getcwd()} is not inside a git checkout')
    if herdr:
        wt, repo_root = herdr_worktree(workspace_id)
        if wt is None:
            die(f'herdr workspace {workspace_id} is not a worktree workspace')
    else:
        wt, repo_root = rex_worktree(top)
    if not wt.get('is_linked_worktree'):
        die(f"{kind} {workspace_id} is the main checkout ({wt['path']}); only linked worktrees are removed")
    if os.path.realpath(wt['path']) != os.path.realpath(top):
        die(f"this shell is in {top}, but {kind} {workspace_id} is {wt['path']}")
    path = wt['path']

    branch = wt.get('branch')  # absent when HEAD is already detached
    head = git('rev-parse', 'HEAD', cwd=path)
    base = default_branch(path)
    run('git', 'fetch', '-q', 'origin', cwd=path)

    changes = [l for l in git('status', '--porcelain', cwd=path).splitlines() if l.strip()]
    real_changes = [l for l in changes if not l.rstrip().endswith('package-lock.json')]
    pr = merged_pr(branch, head, path) if branch else None
    on_base = run('git', 'merge-base', '--is-ancestor', head, f'origin/{base}', cwd=path).returncode == 0
    merged = pr is not None or on_base

    reasons = []
    if real_changes:
        reasons.append(f'{len(real_changes)} uncommitted change(s): {real_changes[:8]}')
    if not merged:
        reasons.append(f'HEAD {head[:9]} is in no merged PR and not in origin/{base}')
    safe = not reasons

    print(f'{kind}: {workspace_id}  path: {path}')
    print(f"branch:    {branch or '(detached HEAD)'}  head: {head[:9]}")
    if pr:
        print(f'merged:    PR #{pr[0]} {pr[1]}')
    elif on_base:
        print(f'merged:    HEAD is in origin/{base}')
    print(f"verdict:   {'SAFE' if safe else 'KEEP'}" + ('' if safe else ' - ' + '; '.join(reasons)))

    if not execute:
        sys.exit(0 if safe else 2)
    if not safe and not discard:
        print('Nothing deleted. Re-run with --execute --discard only if the user agreed to lose this work.')
        sys.exit(2)

    # 1-2. Branch first: once the workspace closes, nothing after it runs.
    if branch:
        git('checkout', '--quiet', '--detach', cwd=path, check=True)
        git('branch', '-D', branch, cwd=repo_root, check=True)
        print(f'deleted local branch {branch}')
        if merged and run('git', 'ls-remote', '--exit-code', '--heads', 'origin', branch, cwd=repo_root).returncode == 0:
            git('push', '--quiet', 'origin', '--delete', branch, cwd=repo_root, check=True)
            print(f'deleted remote branch origin/{branch}')

    # 3. Last step, detached so it outlives this pane. The pause lets this tool call return.
    pid = None if '--keep-agent' in args else agent_pid()
    if herdr:
        teardown = (
            f'sleep 3; '
            f'echo "$(date) removing {workspace_id} {shlex.quote(path)}"; '
            f'herdr worktree remove --force --workspace {shlex.quote(workspace_id)}; '
            f'echo "herdr exit $?"; '
        )
    else:
        rex_bin = shutil.which('rex')
        if not rex_bin:
            raise SystemExit('FAILED: rex not on PATH; branch already deleted, worktree left in place')
        teardown = (
            f'sleep 3; '
            f'echo "$(date) removing {workspace_id} {shlex.quote(path)}"; '
            f'cd {shlex.quote(repo_root)} && git worktree remove --force {shlex.quote(path)}; '
            f'echo "git exit $?"; git worktree prune; '
            f'{shlex.quote(rex_bin)} session kill {shlex.quote(workspace_id)}; '
            f'echo "rex exit $?"; '
        )
    if pid:
        teardown += f'sleep 2; kill -0 {pid} 2>/dev/null && kill -TERM {pid} && echo "sent SIGTERM to agent {pid}"; '
    with open(LOG, 'a') as log:
        subprocess.Popen(['sh', '-c', teardown], cwd=repo_root, stdin=subprocess.DEVNULL,
                         stdout=log, stderr=log, start_new_session=True)
    what = ('herdr worktree remove' if herdr else 'git worktree remove + rex session kill')
    print(f'scheduled: {what} for {workspace_id} in 3s '
          f"(closes the {kind} and this agent{f', pid {pid}' if pid else ''}); log: {LOG}")


if __name__ == '__main__':
    main()
