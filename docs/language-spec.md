# KRAK Language Specification (v1)

## Overview

KRAK is a small, statically-typed-where-it-matters scripting language
built to demonstrate a full compiler pipeline. It is not meant to be a
"real" language — see `architecture.md` for what was intentionally left
out.

## Lexical rules

- Every statement ends with `!`.
- Variables are written `$name` (letters, digits, underscore after the
  first letter).
- Bare identifiers (no `$`) are used for function names and parameters.
- Comments start with `#` and run to end of line.
- Numbers: `123` (INT) or `123.45` (FLOAT).
- Strings: double-quoted, **and must be written backwards** — see below.

### The Mirror String Rule

Every string literal in KRAK source is written **backwards**. The lexer
reverses it back to the real value before the parser ever sees it:

```
SAY "olleH"!            # prints: Hello
MAKE $name = "nayaS"!   # $name == "Sayan"
SAY "!dlrow olleH"!     # prints: Hello world!
```

This is a deliberately weird, purely cosmetic grammar rule added for lab
flavor. It has one real side effect worth knowing for the viva: it proves
the lexer already performs a transformation on literal *values*, not just
a mechanical split into tokens — a nice example that "what are these
pieces" (lexing) and "what do they mean" (semantics) aren't always a
perfectly clean split in a real implementation.

## Types

| Type   | Example      |
|--------|--------------|
| INT    | `10`         |
| FLOAT  | `3.14`       |
| STRING | `"olleH"` (-> "Hello") |
| BOOL   | result of a comparison, e.g. `$x < $y` |

Function parameters are dynamically typed (`ANY`) — type errors inside a
function body involving a parameter are only caught at runtime, not at
compile time. Everything else is checked statically during semantic
analysis.

Type coercion: `INT op FLOAT -> FLOAT` for arithmetic. `STRING + STRING`
is allowed (concatenation is left to the runtime). All other
cross-type arithmetic is a compile-time `Type Error`.

## Statements

### Variable declaration
```
MAKE $x = 10!
```
Declares `$x` in the current scope. Redeclaring an already-declared name
in the same scope is a `Semantic Error`.

### Assignment
```
$x = $x + 1!
```
`$x` must already be declared (in the current or an enclosing scope).
Reassigning to an incompatible type is a `Type Error`.

### Print
```
SAY $x!
SAY "olleH"!
```

### Conditional
```
WHEN ($x > 10) {
    SAY "egral"!
} OTHERWISE {
    SAY "llams"!
}
```
`OTHERWISE` is optional. The condition must evaluate to `BOOL`.

### Loop
```
REPEAT ($x < 10) {
    $x = $x + 1!
}
```
A `while`-style loop. Condition must be `BOOL`.

### Functions
```
FUNC add(a, b) {
    RETURN a + b!
}

MAKE $sum = add(3, 4)!
```
`RETURN` outside a function body is a `Semantic Error`. Calling a
function with the wrong number of arguments is a `Semantic Error`.
Recursion is supported.

## Operators

| Category   | Operators                  |
|------------|-----------------------------|
| Arithmetic | `+ - * /`                   |
| Comparison | `< > <= >=`                  |
| Equality   | `== !=`                      |
| Unary      | `-` (negation)               |

Standard precedence: `* /` bind tighter than `+ -`, which bind tighter
than comparisons, which bind tighter than equality. Parentheses override.

## Errors

Every phase raises a distinct, structured error type (see
`compiler/errors/errors.py`):

- `Lexical Error` — bad characters, unterminated strings
- `Syntax Error` — grammar violations (e.g. missing `!`)
- `Semantic Error` — undefined variables/functions, redeclaration,
  wrong arg count, `RETURN` outside a function
- `Type Error` — incompatible operand types
- `Runtime Error` — division by zero, undefined variable at runtime,
  call to an undefined function, excessive recursion depth

Every error carries a source line (and column, where available) for
diagnostics.
# Arrays

KRAK supports mutable one-dimensional arrays. Array literals use square
brackets and comma-separated expressions; an empty literal is supported.

```krak
MAKE $values = [10, 20, 30]!
MAKE $empty = []!
SAY $values[0]!
$values[1] = 99!
SAY $values!
```

Indices are zero-based integers. Negative indices and indices outside the
array bounds produce runtime errors. Indexing a non-array or using a
non-integer index also produces a runtime error when the value is dynamically
typed (for example, a function parameter).
