from compiler.pipeline import compile_and_run
from compiler.bytecode.instructions import PUSH_CONST, STORE, PRINT, HALT


def test_bytecode_has_main_chunk():
    r = compile_and_run("MAKE $x = 10!\nSAY $x!")
    assert "__main__" in r["bytecode"]


def test_bytecode_ends_with_halt():
    r = compile_and_run("MAKE $x = 10!\nSAY $x!")
    ops = [i["op"] for i in r["bytecode"]["__main__"]]
    assert ops[-1] == HALT


def test_bytecode_contains_push_and_store_for_declaration():
    r = compile_and_run("MAKE $x = 10!")
    ops = [i["op"] for i in r["bytecode"]["__main__"]]
    assert PUSH_CONST in ops
    assert STORE in ops


def test_function_gets_its_own_chunk():
    r = compile_and_run("FUNC add(a, b) { RETURN a + b! }\nMAKE $s = add(1, 2)!")
    assert "add" in r["bytecode"]
