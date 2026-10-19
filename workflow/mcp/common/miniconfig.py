"""Minimal nested `key: value` reader for `git-dev.data/config.yaml`.

Not a YAML parser: supports only two-space-indented nesting of scalar `key: value` pairs,
`key:` block headers, and `- item` list lines directly under a header, one per line, no
flow-style. That is all the `backends`, `github`, `providers` and `auto` sections need. A `key:`
header with nothing nested under it parses as an empty dict. A value wrapped in matching single
or double quotes is unquoted. `#` starts a comment only at the start of a line or after
whitespace (as in YAML), so `repo: o/n#x` keeps its `#`.
"""
import re
from pathlib import Path

COMMENT = re.compile(r"(?:^|\s)#.*$")


def _scalar(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        return value[1:-1]
    return value


def load(path):
    """Parse the subset described above into a nested dict. Missing file -> {}."""
    p = Path(path)
    if not p.exists():
        return {}
    root = {}
    # (indent, container, owner dict, key in owner): owner/key let an empty `key:` header turn
    # into a list once its first `- item` line shows up.
    stack = [(-1, root, None, None)]
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = COMMENT.sub("", raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        while stack and indent <= stack[-1][0]:
            stack.pop()
        _, container, owner, owner_key = stack[-1]
        text = line.strip()
        if text == "-" or text.startswith("- "):
            if isinstance(container, dict) and not container and owner is not None:
                container = owner[owner_key] = []
                stack[-1] = (stack[-1][0], container, owner, owner_key)
            if isinstance(container, list):
                container.append(_scalar(text[1:].strip()))
            continue
        if not isinstance(container, dict):
            continue
        key, _, value = text.partition(":")
        key, value = key.strip(), value.strip()
        if value:
            container[key] = _scalar(value)
        else:
            child = {}
            container[key] = child
            stack.append((indent, child, container, key))
    return root


def get(config, dotted, default=None):
    """Look up a dotted path (e.g. "backends.req_tracker") in a `load()`-returned dict."""
    node = config
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node
