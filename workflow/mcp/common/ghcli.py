"""Thin `gh` CLI wrapper shared by the github-backed providers. Stdlib only; shells out to the
`gh` binary (must be installed and authenticated) instead of talking MCP/HTTP directly, so these
providers keep the same subprocess-callable contract as the mock servers.
"""
import json
import re
import subprocess

REF_RE = re.compile(r"#(\d+)")


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


def first_ref(*texts):
    """First `#<number>` reference found across the given strings, as `"#<number>"`, or None."""
    for text in texts:
        m = REF_RE.search(text or "")
        if m:
            return f"#{m.group(1)}"
    return None
