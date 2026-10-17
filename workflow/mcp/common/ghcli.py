"""Thin `gh` CLI wrapper shared by the github-backed providers. Stdlib only; shells out to the
`gh` binary (must be installed and authenticated) instead of talking MCP/HTTP directly, so these
providers keep the same subprocess-callable contract as the mock servers.
"""
import json
import re
import subprocess

REF_RE = re.compile(r"#(\d+)")
BLOCKS_RE = re.compile(r"\bblocks?\b\D{0,10}#(\d+)", re.I)
BLOCKED_BY_RE = re.compile(r"\bblocked\s+by\b\D{0,10}#(\d+)", re.I)


class GhError(RuntimeError):
    pass


def run(args, repo=None, input_=None):
    cmd = ["gh", *args]
    if repo:
        cmd += ["--repo", repo]
    res = subprocess.run(cmd, capture_output=True, text=True, input=input_)
    if res.returncode:
        raise GhError(res.stderr.strip() or f"gh {' '.join(args)} failed")
    return res.stdout


def run_json(args, repo=None):
    out = run(args, repo=repo).strip()
    return json.loads(out) if out else None


def first_ref(*texts, exclude=()):
    """First `#<number>` reference found across the given strings, as `"#<number>"`, skipping any
    in `exclude` (e.g. numbers already claimed by a Blocks/Blocked-by relationship, so a "Blocks
    #18" mention isn't mistaken for a requirement link), or None."""
    exclude = set(exclude)
    for text in texts:
        for m in REF_RE.finditer(text or ""):
            ref = f"#{m.group(1)}"
            if ref not in exclude:
                return ref
    return None


def blocking_refs(body):
    """`#<number>` refs following "Blocks"/"Blocked by" text in an issue body, as `(blocks,
    blocked_by)` lists of `"#<number>"` strings. A text heuristic over the issue body, not
    GitHub's native sub-issue/blocked-by relationship."""
    body = body or ""
    return ([f"#{n}" for n in BLOCKS_RE.findall(body)],
            [f"#{n}" for n in BLOCKED_BY_RE.findall(body)])
