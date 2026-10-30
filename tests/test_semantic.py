import pytest
from compiler.lexer.lexer import Lexer
from compiler.parser.parser import Parser
from compiler.semantic.analyzer import SemanticAnalyzer
from compiler.errors.errors import SemanticError, KrakTypeError


def analyze(source):
    tokens = Lexer(source).tokenize()
    prog = Parser(tokens).parse()
    return SemanticAnalyzer().analyze(prog)


def test_undefined_variable_raises():
    with pytest.raises(SemanticError):
        analyze("SAY $y!")


def test_redeclaration_in_same_scope_raises():
    with pytest.raises(SemanticError):
        analyze("MAKE $x = 1!\nMAKE $x = 2!")


def test_type_mismatch_raises():
    with pytest.raises(KrakTypeError):
        analyze('MAKE $x = 10!\nMAKE $y = "olleh"!\nMAKE $z = $x + $y!')


def test_valid_program_populates_symbol_table():
    symtab = analyze("MAKE $x = 10!\nMAKE $y = 20!")
    names = {s["name"] for s in symtab.snapshot()}
    assert names == {"$x", "$y"}


def test_return_outside_function_raises():
    with pytest.raises(SemanticError):
        analyze("RETURN 5!")


def test_function_call_wrong_arity_raises():
    with pytest.raises(SemanticError):
        analyze("FUNC add(a, b) { RETURN a + b! }\nMAKE $x = add(1)!")
