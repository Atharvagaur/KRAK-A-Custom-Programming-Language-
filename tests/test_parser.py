import pytest
from compiler.lexer.lexer import Lexer
from compiler.parser.parser import Parser
from compiler.ast.nodes import VarDecl, IfStatement, WhileStatement, FunctionDeclaration
from compiler.errors.errors import SyntaxError_


def parse(source):
    tokens = Lexer(source).tokenize()
    return Parser(tokens).parse()


def test_variable_declaration_ast():
    prog = parse("MAKE $x = 10!")
    assert len(prog.statements) == 1
    assert isinstance(prog.statements[0], VarDecl)
    assert prog.statements[0].name == "$x"


def test_if_otherwise_ast():
    prog = parse('WHEN ($x > 1) { SAY "a"! } OTHERWISE { SAY "b"! }')
    stmt = prog.statements[0]
    assert isinstance(stmt, IfStatement)
    assert stmt.else_block is not None


def test_while_ast():
    prog = parse("REPEAT ($x < 10) { $x = $x + 1! }")
    assert isinstance(prog.statements[0], WhileStatement)


def test_function_declaration_ast():
    prog = parse("FUNC add(a, b) { RETURN a + b! }")
    fn = prog.statements[0]
    assert isinstance(fn, FunctionDeclaration)
    assert fn.params == ["a", "b"]


def test_missing_statement_end_raises_syntax_error():
    with pytest.raises(SyntaxError_):
        parse("MAKE $x = 10")


def test_operator_precedence():
    prog = parse("MAKE $x = 2 + 3 * 4!")
    expr = prog.statements[0].value
    # multiplication should bind tighter -> top node is '+'
    assert expr.op == "+"
    assert expr.right.op == "*"
