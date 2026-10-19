"""Thin `gh` CLI wrapper shared by the github-backed providers. Stdlib only; shells out to the
`gh` binary (must be installed and authenticated) instead of talking MCP/HTTP directly, so these
providers keep the same subprocess-callable contract as the mock servers.
"""
import json
import re
import subprocess
import sys

# `--limit` for list calls; see `run_list`.
LIMIT = 1000

REF_RE = re.compile(r"#(\d+)")
# One or more refs joined by commas/"and"/"&"/"/", e.g. "#3, #4 and #5": every ref in the list
# belongs to the keyword, so none of them leaks into `first_ref` as a requirement link.
_REF_LIST = r"#\d+(?:\s*(?:,|\band\b|&|/)\s*#\d+)*"
BLOCKS_RE = re.compile(rf"\bblocks?\b\D{{0,10}}({_REF_LIST})", re.I)
BLOCKED_BY_RE = re.compile(rf"\bblocked\s+by\b\D{{0,10}}({_REF_LIST})", re.I)


class GhError(RuntimeError):
    pass


def run(args, repo=None, input_=None):
    cmd = ["gh", *args]
    if repo:
        cmd += ["--repo", repo]
    # gh writes UTF-8 regardless of the console code page (cp1252 on Windows would garble or fail).
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", input=input_)
    if res.returncode:
        raise GhError(res.stderr.strip() or f"gh {' '.join(args)} failed")
    return res.stdout


def run_json(args, repo=None):
    out = run(args, repo=repo).strip()
    return json.loads(out) if out else None


def run_list(args, repo=None, limit=LIMIT):
    """`gh <noun> list ...` with `--limit`. gh lists newest first, so a truncated list silently
    drops the *oldest* records (the ones `git-dev-target` prefers); warn on stderr when the limit
    is hit rather than returning a short list as if it were complete."""
    recs = run_json([*args, "--limit", str(limit)], repo=repo) or []
    if len(recs) >= limit:
        print(f"warning: `gh {' '.join(args[:2])}` hit --limit {limit}; older records are missing",
              file=sys.stderr)
    return recs


def mcp_served(tools, enabled):
    """Tool names a github-* provider exposes as live MCP tools: none unless the project's
    `backends.<kind>` selects it, and then only the read-only `list_*`/`get_*` ones. Real writes
    (`create_*`/`update_*`) run only through the CLI, which the skills call behind their gates."""
    return {n for n in tools if n.startswith(("list_", "get_"))} if enabled else set()


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

    def refs(pattern):
        out = []
        for group in pattern.findall(body):
            out += [f"#{n}" for n in REF_RE.findall(group) if f"#{n}" not in out]
        return out

    return refs(BLOCKS_RE), refs(BLOCKED_BY_RE)
