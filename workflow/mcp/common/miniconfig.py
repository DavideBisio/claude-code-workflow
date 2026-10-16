"""Minimal nested `key: value` reader for `git-dev.data/config.yaml`.

Not a YAML parser: supports only two-space-indented nesting of scalar `key: value` pairs and
`key:` block headers, one pair per line, no lists/quotes/flow-style. That is all the `backends`
and `github` sections need; anything else in config.yaml (prose, `test_command`, comments) is
read directly by the skills, not by this module.
"""
from pathlib import Path


def load(path):
    """Parse the subset described above into a nested dict. Missing file -> {}."""
    p = Path(path)
    if not p.exists():
        return {}
    root = {}
    stack = [(-1, root)]
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, _, value = line.strip().partition(":")
        key, value = key.strip(), value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value:
            parent[key] = value
        else:
            child = {}
            parent[key] = child
            stack.append((indent, child))
    return root


def get(config, dotted, default=None):
    """Look up a dotted path (e.g. "backends.req_tracker") in a `load()`-returned dict."""
    node = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
