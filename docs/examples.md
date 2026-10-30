# Example Programs

All examples live in `examples/*.krak`. Run any of them with:

```bash
python3 cli.py run examples/<name>.krak
```

Or see every compiler stage for one of them with:

```bash
python3 cli.py all examples/<name>.krak
```

## hello.krak
The absolute basics, and the Mirror String Rule in one line:
```
SAY "olleH ,dlroW"!
```
Output: `World, Hello` — wait, that's what it *looks* like at a glance;
actually reversing `"olleH ,dlroW"` character-by-character gives
`World, Hello`. Try reading any KRAK string backwards to predict its
output before running it — it's a good exercise for a viva demo.

## variables.krak
Declaration, arithmetic with precedence, and reassignment.

## conditions.krak
`WHEN` / `OTHERWISE`.

## loops.krak
`REPEAT` (a `while`-style loop) counting 0 through 4.

## functions.krak
`FUNC` / `RETURN`, including a recursive `factorial`.

## optimizer_demo.krak
Written specifically to show the optimizer earning its keep. Run:
```
python3 cli.py ir examples/optimizer_demo.krak
```
and compare the "before" and "after" IR — you'll see constant folding
collapse `10 + 20 * 2` into `50` at compile time, and dead-store
elimination drop an assignment that gets immediately overwritten.
