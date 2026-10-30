# KRAK — A Custom Programming Language Compiler with Visual Compilation Pipeline

KRAK is a small, purpose-built language and a full compiler for it — lexer,
recursive-descent parser, AST, semantic analyzer with a typed symbol table,
a three-address-code IR, a peephole optimizer (constant folding, constant
propagation, algebraic simplification, dead-store elimination), a custom
bytecode instruction set, and a stack-based virtual machine. A Flask web UI
exposes every stage so you can *watch* a program compile, not just run it.

Built as a Compiler Design lab project. Scope is intentionally small —
see `docs/architecture.md` §"What NOT to implement" for what was cut on
purpose.

---

## The weird rule (as requested)

**The Mirror String Rule.** Every string literal in KRAK source must be
written **backwards**. The lexer un-reverses it before anything else ever
sees it:

```
SAY "olleH"!            # prints: Hello
SAY "!dlrow olleH"!     # prints: Hello world!
```

Zero practical benefit, 100% intentional, and a genuinely useful talking
point in a viva: it shows the lexer doing more than just chopping up
characters — it's already transforming literal values before parsing even
starts.

---

## Code structure — organized by compiler phases

All compiler code lives under `phases/`, one numbered folder per pipeline
stage. Each phase is self-contained: it knows its input, produces its
output, and imports only from earlier phases (plus `phase0_common`).

```
phases/
  phase0_common/          # shared code used by every phase
    errors.py             # structured error hierarchy (all phases)
    types.py              # type system (semantic, optimizer)
  phase1_lexical_analysis/# source text -> Token stream
    tokens.py             # Token type constants + Token class
    lexer.py              # Lexer (Mirror String Rule)
  phase2_parsing/         # Token stream -> AST
    nodes.py              # AST node dataclasses
    parser.py             # recursive-descent parser
  phase3_semantic_analysis/# AST -> validated program + symbol table
    symbol_table.py       # scoped symbol table
    analyzer.py           # semantic analysis + type checking
  phase4_ir_generation/   # AST -> three-address-code IR + CFG
    instructions.py       # IR instruction dataclasses
    generator.py          # AST -> IR translator
    cfg.py                # control-flow graph construction
  phase5_optimization/    # IR -> optimized IR
    optimizer.py          # constant folding, propagation, DSE, CFG opts
  phase6_bytecode_generation/# IR -> stack bytecode chunks
    instructions.py       # bytecode opcodes + Instr dataclass
    compiler.py           # IR -> bytecode compiler (per-function chunks)
  phase7_virtual_machine/ # bytecode -> program output
    virtual_machine.py    # stack-based VM with debugger snapshots
```

The thin `compiler/` package remains as the public entry point:

```
compiler/
  pipeline.py             # single orchestrator: chains phases 1..7 together
  cli.py                  # command-line driver (delegates to pipeline.py)
  lexer/, parser/, ast/, semantic/, ir/, optimizer/, bytecode/, vm/, errors/
    # backward-compat shims that re-export from phases/*
```

Other top-level folders:

```
web/                      # Flask visual compiler UI (REST API + debugger)
examples/                 # sample .krak programs
tests/                    # pytest suite, one file per compiler phase
benchmarks/               # optimizer comparison harness + results
docs/                     # grammar, architecture notes, language spec, examples
```

---

## Complete code flow — how source moves through folders/files

Every KRAK program travels through the pipeline in strict phase order.
Both the CLI (`cli.py`) and the web UI (`web/app.py`) enter through the
single orchestrator `compiler/pipeline.py`; nothing else touches compiler
internals directly.

```
SOURCE FILE (.krak)
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  compiler/pipeline.py  (orchestrator — calls every phase below) │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1 — Lexical Analysis                                     │
│  phases/phase1_lexical_analysis/lexer.py                        │
│  phases/phase1_lexical_analysis/tokens.py                       │
│  Input : raw source text                                        │
│  Output: stream of Token objects (Mirror String Rule applied)   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2 — Parsing                                              │
│  phases/phase2_parsing/parser.py                                │
│  phases/phase2_parsing/nodes.py                                 │
│  Input : Token stream                                           │
│  Output: AST (Program node tree of AST dataclasses)             │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3 — Semantic Analysis                                    │
│  phases/phase3_semantic_analysis/analyzer.py                    │
│  phases/phase3_semantic_analysis/symbol_table.py                │
│  phases/phase0_common/types.py                                  │
│  Input : AST                                                    │
│  Output: validated program + symbol table snapshot              │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 4 — IR Generation                                        │
│  phases/phase4_ir_generation/generator.py                       │
│  phases/phase4_ir_generation/instructions.py                    │
│  phases/phase4_ir_generation/cfg.py                             │
│  Input : AST                                                    │
│  Output: linear three-address-code IR + control-flow graph      │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 5 — Optimization                                         │
│  phases/phase5_optimization/optimizer.py                        │
│  Input : IR + CFG                                               │
│  Output: optimized IR + optimized CFG                           │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 6 — Bytecode Generation                                  │
│  phases/phase6_bytecode_generation/compiler.py                  │
│  phases/phase6_bytecode_generation/instructions.py              │
│  Input : optimized IR                                           │
│  Output: stack bytecode chunks (one per function, __main__ too) │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 7 — Virtual Machine                                      │
│  phases/phase7_virtual_machine/virtual_machine.py               │
│  Input : bytecode chunks                                        │
│  Output: program stdout output (and runtime errors if any)      │
└─────────────────────────────────────────────────────────────────┘
```

### Result dictionary shape (`compile_and_run`)

Each stage appends its artifact to the result dict so a UI can render it:

| Key | Populated by | Contents |
|-----|-------------|----------|
| `tokens` | Phase 1 | list of token dicts |
| `ast` | Phase 2 | Program.to_dict() tree |
| `symbols` | Phase 3 | symbol table snapshot rows |
| `ir_before` | Phase 4 | IR instructions before optimization |
| `cfg_before` | Phase 4 | control-flow graph before optimization |
| `ir_after` | Phase 5 | IR instructions after optimization |
| `cfg_after` | Phase 5 | control-flow graph after optimization |
| `optimizer_notes` / `optimizer_remarks` | Phase 5 | human-readable optimization log |
| `bytecode_before` | Phase 6 | unoptimized IR -> bytecode chunks |
| `bytecode` | Phase 6 | optimized IR -> bytecode chunks |
| `bytecode_to_block` | Phase 6 | bytecode instruction -> CFG block map |
| `instruction_counts` | Phase 6 | counts at each stage |
| `output` | Phase 7 | program stdout lines |
| `errors` | any phase | structured error dicts |
| `stage_reached` | pipeline | deepest phase completed |

---

## Quick start

```bash
pip install -r requirements.txt --break-system-packages   # flask, pytest

# run a program
python3 cli.py run examples/hello.krak

# see every compiler stage for one program
python3 cli.py all examples/functions.krak

# individual stages
python3 cli.py tokens examples/variables.krak
python3 cli.py ast examples/conditions.krak
python3 cli.py ir examples/optimizer_demo.krak
python3 cli.py bytecode examples/loops.krak

# run the test suite
python3 -m pytest tests/ -v

# launch the visual web compiler
python3 web/app.py
# then open http://localhost:5000
```

The web compiler includes an interactive VM debugger. Edit a KRAK program,
select **compile**, then use **step**, **play/pause**, **step back**, **run**,
**reset**, or **stop**. The bytecode table, operand stack, active frame
locals, output, and event timeline all come from the same VM used by the
normal compiler path. Clicking a timeline event views its recorded state;
clicking an instruction only inspects it. Debug sessions are process-local,
expire after 30 minutes of inactivity, and are bounded to four concurrent
sessions, 20 KB of source, and 2,000 recorded instruction steps per session.
These debugger limits do not apply to normal CLI or compile-and-run execution.
The CFG panel displays the original or optimized graph and maps debugger
addresses to blocks from compiler metadata. The toolbar can disable all
optimization or only the control-flow-aware passes.

Compare the existing optimizer with the CFG passes using the reproducible
benchmark suite (medians are reported; instruction counts are not speed
claims):

```bash
python3 benchmarks/benchmark_control_flow.py --repeat 7
```

## Language at a glance

```
MAKE $x = 10!
MAKE $y = 20!

WHEN ($x < $y) {
    SAY "!aidem eht si egassem ehT"!
} OTHERWISE {
    SAY "esiwrehtO"!
}

REPEAT ($x < 15) {
    SAY $x!
    $x = $x + 1!
}

FUNC factorial(n) {
    WHEN (n <= 1) { RETURN 1! }
    RETURN n * factorial(n - 1)!
}

SAY factorial(5)!
```

Every statement ends with `!`. Variables are `$`-prefixed. Types are
`INT`, `FLOAT`, `STRING`, `BOOL` and are checked at compile time (function
parameters are dynamically typed). Full grammar: `docs/grammar.md`.

## What was deliberately left out

Classes, generics, async/threads, GC, modules, a package manager, a real
IDE, and machine-code / LLVM backends. This is a Compiler Design project
about the pipeline, not an attempt to build a production language.
