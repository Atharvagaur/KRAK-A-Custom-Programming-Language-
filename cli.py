#!/usr/bin/env python3
"""
KRAK CLI
========
Usage:
    python3 cli.py run <file.krak>              # compile & execute
    python3 cli.py tokens <file.krak>            # show token stream
    python3 cli.py ast <file.krak>                # show AST (json)
    python3 cli.py ir <file.krak>                 # show IR before/after optimization
    python3 cli.py bytecode <file.krak>           # show bytecode
    python3 cli.py all <file.krak>                # show every stage
"""

import sys
import json
from compiler.pipeline import compile_and_run


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _print_errors(result):
    for err in result["errors"]:
        loc = f" (line {err['line']})" if err.get("line") else ""
        print(f"\n{err['kind']}{loc}: {err['message']}", file=sys.stderr)


def cmd_run(path):
    result = compile_and_run(_read(path))
    for line in result["output"]:
        print(line)
    _print_errors(result)
    sys.exit(1 if result["errors"] else 0)


def cmd_tokens(path):
    result = compile_and_run(_read(path))
    for t in result["tokens"]:
        print(f"{t['type']:<16} {t['value']!r:<20} line={t['line']} col={t['column']}")
    _print_errors(result)


def cmd_ast(path):
    result = compile_and_run(_read(path))
    print(json.dumps(result["ast"], indent=2))
    _print_errors(result)


def cmd_ir(path):
    result = compile_and_run(_read(path))
    print("--- IR (before optimization) ---")
    for i in result["ir_before"]:
        print(" ", i["text"])
    print("\n--- IR (after optimization) ---")
    for i in result["ir_after"]:
        print(" ", i["text"])
    if result["optimizer_notes"]:
        print("\n--- optimizer notes ---")
        for n in result["optimizer_notes"]:
            print(" -", n)
    _print_errors(result)


def cmd_bytecode(path):
    result = compile_and_run(_read(path))
    for chunk_name, instrs in result["bytecode"].items():
        print(f"\n=== {chunk_name} ===")
        for idx, i in enumerate(instrs):
            arg = f" {i['arg']}" if i["arg"] is not None else ""
            print(f"  {idx:03d}  {i['op']}{arg}")
    _print_errors(result)


def cmd_all(path):
    src = _read(path)
    result = compile_and_run(src)

    print("=" * 60)
    print("SOURCE")
    print("=" * 60)
    print(src.strip())

    print("\n" + "=" * 60)
    print("TOKENS")
    print("=" * 60)
    for t in result["tokens"]:
        print(f"{t['type']:<16} {t['value']!r}")

    print("\n" + "=" * 60)
    print("SYMBOL TABLE")
    print("=" * 60)
    for s in result["symbols"]:
        print(f"{s['name']:<10} {s['type']:<8} {s['value']}")

    print("\n" + "=" * 60)
    print("IR (before optimization)")
    print("=" * 60)
    for i in result["ir_before"]:
        print(" ", i["text"])

    print("\n" + "=" * 60)
    print("IR (after optimization)")
    print("=" * 60)
    for i in result["ir_after"]:
        print(" ", i["text"])

    print("\n" + "=" * 60)
    print("BYTECODE")
    print("=" * 60)
    for chunk_name, instrs in result["bytecode"].items():
        print(f"\n--- {chunk_name} ---")
        for idx, i in enumerate(instrs):
            arg = f" {i['arg']}" if i["arg"] is not None else ""
            print(f"  {idx:03d}  {i['op']}{arg}")

    print("\n" + "=" * 60)
    print("OUTPUT")
    print("=" * 60)
    for line in result["output"]:
        print(line)

    _print_errors(result)
    sys.exit(1 if result["errors"] else 0)


COMMANDS = {
    "run": cmd_run,
    "tokens": cmd_tokens,
    "ast": cmd_ast,
    "ir": cmd_ir,
    "bytecode": cmd_bytecode,
    "all": cmd_all,
}


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        sys.exit(1)
    COMMANDS[sys.argv[1]](sys.argv[2])


if __name__ == "__main__":
    main()
