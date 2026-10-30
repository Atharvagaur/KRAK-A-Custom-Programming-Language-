# KRAK Architecture

## Why not compile to machine code?

Unnecessary complexity for a lab project. Instead, KRAK compiles to its
own bytecode instruction set and runs on its own stack-based virtual
machine. This gives almost every important Compiler Design concept
(lexing, parsing, AST, symbol tables, type checking, IR, optimization,
code generation, and an execution model) without needing to touch
register allocation, calling conventions, or a real target ISA.

## Pipeline

```
KRAK source
    |
    v
 Lexer            source -> tokens (incl. the Mirror String Rule)
    |
    v
 Parser           tokens -> AST (recursive descent, precedence climbing)
    |
    v
 Semantic         AST -> validated AST + symbol table
 Analyzer         (scoping, undefined-name checks, type checking)
    |
    v
 IR Generator     AST -> three-address code (KRAK IR)
    |
    v
 Optimizer        IR -> optimized IR
                  (local passes, then CFG constant propagation, branch
                   folding, unreachable removal, and jump cleanup)
    |
    v
 Bytecode         optimized IR -> stack bytecode, one chunk per function
 Compiler         plus a "__main__" chunk
    |
    v
 Virtual Machine  bytecode -> program output
```

`compiler/pipeline.py::compile_and_run(source)` remains the entry point for
normal execution. The debugger calls `compile_source(source)` to produce the
same artifacts and bytecode without starting the program, then steps that
bytecode through the same `VirtualMachine` dispatcher. The VM's ordinary
`run()` method also uses that dispatcher, so trace mode does not simulate a
second instruction set.

The debug VM keeps exact snapshots at each instruction boundary. Rewind
restores the active frames, local variables, operand stacks, arrays, output,
instruction pointers, and frame-id counter. Snapshot history is bounded to
2,000 attempted instructions; debug sessions expire after 30 minutes and the
web process holds at most four at a time. The 20 KB source limit and history
cap bound memory use for browser-submitted programs.

The compile result includes intermediate artifacts:

```python
{
    "tokens": [...],
    "ast": {...},
    "symbols": [...],
    "ir_before": [...],
    "ir_after": [...],
    "optimizer_notes": [...],
    "bytecode": {"__main__": [...], "add": [...], ...},
    "output": [...],
    "errors": [...],
    "stage_reached": "vm" | "lexer" | "parser" | ...,
}
```

The standard compile endpoint renders this result. Debug routes also use the
pipeline's compile-only entry point and the VM's debugger methods, while the
template and frontend render the returned bytecode and execution snapshots.

## Control-flow graph and optimization

`compiler/ir/cfg.py` splits the existing labeled IR at function entries,
labels, and instructions after branches or returns. It resolves branch
targets within each function and records true/false, jump, and fall-through
edges. Each function and `__main__` has a separate entry; the visualizer maps
bytecode addresses to source IR instruction indices and then to their basic
blocks. Synthetic function returns and the main halt map to the final block,
or to an empty entry/exit block for an empty chunk.

The control-flow optimizer follows the existing local optimizer. Its value
domain is `UNDEFINED` (iteration bottom), a constant, or `OVERDEFINED`.
Reachable predecessor facts are joined and block transfer functions iterate
to a fixed point, with a convergence guard. Mutable arrays are never treated
as constants. Constant branches are folded, unreachable blocks are removed
within each function, and safe jump threading and fall-through jump removal
run last. The CFG is validated before and after these transformations.

The web toolbar can disable all optimization or only the new control-flow
passes. The graph switches between original and optimized IR; runtime
highlighting uses actual VM chunk/address history and appears on the graph
that matches the optimized bytecode. The graph supports block inspection,
scrolling, zoom, pan, and fit-to-view.

General liveness-based dead-code elimination is not implemented. The existing
dead-store pass is limited to constant/copy assignments because removing
arithmetic, indexing, array construction, or calls can suppress runtime
errors or observable effects. The IR has no exception-handling structure.

## The compiler/UI boundary

```
web/app.py  ---calls--->  compiler/pipeline.py  ---calls--->  compiler/{lexer,parser,...}
```

Not:

```
HTML -> directly calls lexer -> directly calls parser -> ...   (never do this)
```

Keeping this boundary strict is what let the web UI, the CLI, and the
test suite all be built independently against the same pipeline output
without duplicating compiler logic anywhere.

## Design decisions worth defending in a viva

- **Three-address code IR** — every instruction has at most one operator
  and writes to a fresh temporary (`t1`, `t2`, ...) or a named variable.
  This is what makes constant folding/propagation and dead-store
  elimination tractable: each instruction is small enough to reason
  about in isolation.
- **Separate local and global analyses** — the original local passes remain
  in place; the CFG layer adds a conservative fixed-point analysis instead
  of replacing the existing three-address representation with SSA.
- **Bytecode chunks per function** — instead of one flat instruction
  stream with computed offsets for every function, each function
  compiles to its own named chunk (`chunks["add"]`, `chunks["__main__"]`).
  `CALL` instructions just look up the chunk by name at runtime. Simpler
  to implement and to display in the UI than a single flat stream with
  a call stack of raw addresses.
- **Dynamic typing for function parameters** — fully static typing
  through function calls would need real type inference (or mandatory
  type annotations on every `FUNC`), which was cut deliberately per the
  scope below. Parameters are `ANY` and checked at runtime instead.

## What NOT to implement (scope discipline)

Left out on purpose, to keep this a compiler-design project instead of a
production-language project:

- Classes / objects / inheritance
- Generics
- Async / await, threads
- Garbage collection (Python's own GC is riding along for free; KRAK
  itself never allocates anything that needs a real collector)
- Modules / imports
- Networking
- Complex type inference
- Native machine-code generation / a real ISA backend
- A full LLVM backend
- A package manager
- An IDE

## Development order actually followed

1. Language specification (`docs/language-spec.md`) and grammar
   (`docs/grammar.md`)
2. Lexer + tests
3. Parser + tests
4. AST node definitions
5. Semantic analysis (symbol table, scoping, type checking) + tests
6. IR generation + tests
7. Optimizer (folding, propagation, algebraic simplification, dead-store
   elimination) + tests
8. Bytecode compiler + tests
9. Virtual machine + tests
10. CLI (`cli.py`)
11. Web UI (Flask + vanilla JS, calling only `compiler/pipeline.py`)
12. Docs + example programs + final pass
