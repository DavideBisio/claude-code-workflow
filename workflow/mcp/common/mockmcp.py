"""Tiny stdlib-only mock MCP framework (stdio JSON-RPC) with a scriptable CLI.

Per resource it generates: list_<plural>, get_<singular>, create_<singular>, update_<singular>.
fetch -> sample data; create/update -> ack ok, no effect.

Usage of a server script:
  server.py                      run as MCP stdio server
  server.py tools                list tools (JSON)
  server.py call TOOL [JSON]     call a tool, print JSON result
  server.py TOOL [JSON]          shorthand for `call`
"""
import json
import sys


def make_tools(resources):
    """resources: {singular: (plural, [sample records])} -> {tool name: (description, handler)}"""
    tools = {}
    for singular, (plural, data) in resources.items():
        def list_(args, data=data):
            flt = args.get("filter") or {}
            return [r for r in data if all(r.get(k) == v for k, v in flt.items())]

        def get_(args, data=data, singular=singular):
            for r in data:
                if str(r.get("id")) == str(args.get("id")):
                    return r
            return {"error": f"{singular} not found", "id": args.get("id")}

        def create_(args, singular=singular):
            return {"ok": True, "mock": True, "note": "acknowledged, no effect", "created": singular, "data": args}

        def update_(args, singular=singular):
            return {"ok": True, "mock": True, "note": "acknowledged, no effect", "updated": singular, "data": args}

        tools[f"list_{plural}"] = (f"List {plural} (sample data). Optional exact-match `filter` object.", list_)
        tools[f"get_{singular}"] = (f"Get one {singular} by `id` (sample data).", get_)
        tools[f"create_{singular}"] = (f"Create a {singular} (mock: acknowledged, no effect).", create_)
        tools[f"update_{singular}"] = (f"Update a {singular} by `id` (mock: acknowledged, no effect).", update_)
    return tools


SCHEMA = {"type": "object", "additionalProperties": True}


def _call(tools, name, args):
    if name not in tools:
        raise KeyError(f"unknown tool: {name}")
    return tools[name][1](args or {})


def _serve(server_name, tools):
    def reply(msg_id, result=None, error=None):
        msg = {"jsonrpc": "2.0", "id": msg_id}
        msg["error" if error else "result"] = error or result
        sys.stdout.write(json.dumps(msg) + "\n")
        sys.stdout.flush()

    # MCP stdio is UTF-8 JSON-RPC; don't let the console code page (cp1252 on Windows) decode it.
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = json.loads(line)
        method, mid = req.get("method"), req.get("id")
        if mid is None:  # notification
            continue
        if method == "initialize":
            reply(mid, {"protocolVersion": req.get("params", {}).get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": server_name, "version": "0.0.0"}})
        elif method == "ping":
            reply(mid, {})
        elif method == "tools/list":
            reply(mid, {"tools": [{"name": n, "description": d, "inputSchema": SCHEMA}
                                  for n, (d, _) in tools.items()]})
        elif method == "tools/call":
            p = req.get("params", {})
            try:
                out = _call(tools, p.get("name"), p.get("arguments"))
                reply(mid, {"content": [{"type": "text", "text": json.dumps(out, indent=2)}]})
            except Exception as e:  # tool error, reported in-band
                reply(mid, {"isError": True, "content": [{"type": "text", "text": str(e)}]})
        else:
            reply(mid, error={"code": -32601, "message": f"method not found: {method}"})


def run(server_name, resources, argv=None):
    return run_tools(server_name, make_tools(resources), argv)


def run_tools(server_name, tools, argv=None, served=None):
    """Same stdio-server + CLI harness as `run()`, for a pre-built `{name: (description, handler)}`
    dict rather than one generated from static `resources` (used by the non-mock providers).

    `served`, if given, is the subset of tool names exposed when running as an MCP stdio server;
    the CLI (what the skills call, behind their own gates) always gets every tool."""
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        if served is not None:
            tools = {n: t for n, t in tools.items() if n in served}
        return _serve(server_name, tools)
    if argv[0] == "tools":
        print(json.dumps([{"name": n, "description": d} for n, (d, _) in tools.items()], indent=2))
        return
    rest = argv[1:] if argv[0] == "call" else argv
    if not rest:
        sys.exit(__doc__)
    try:
        args = json.loads(rest[1]) if len(rest) > 1 else {}
        print(json.dumps(_call(tools, rest[0], args), indent=2))
    except Exception as e:  # unknown tool, bad JSON, or a provider failure (e.g. `gh` not authenticated)
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
