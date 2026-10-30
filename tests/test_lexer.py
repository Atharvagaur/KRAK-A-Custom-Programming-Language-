from compiler.lexer.lexer import Lexer
from compiler.lexer.tokens import (
    MAKE, IDENTIFIER, ASSIGN, NUMBER, STATEMENT_END, EOF, STRING, SAY,
)


def types_of(source):
    return [t.type for t in Lexer(source).tokenize()]


def test_variable_declaration_tokens():
    result = types_of("MAKE $x = 10!")
    assert result == [MAKE, IDENTIFIER, ASSIGN, NUMBER, STATEMENT_END, EOF]


def test_float_number():
    tokens = Lexer("MAKE $pi = 3.14!").tokenize()
    num = [t for t in tokens if t.type == NUMBER][0]
    assert num.value == 3.14
    assert isinstance(num.value, float)


def test_mirror_string_rule_reverses_literal():
    tokens = Lexer('SAY "olleH"!').tokenize()
    str_tok = [t for t in tokens if t.type == STRING][0]
    assert str_tok.value == "Hello"


def test_comment_is_skipped():
    tokens = Lexer("# this is a comment\nMAKE $x = 1!").tokenize()
    assert tokens[0].type == MAKE


def test_line_and_column_tracking():
    tokens = Lexer("MAKE $x = 10!\nSAY $x!").tokenize()
    say_tok = [t for t in tokens if t.type == SAY][0]
    assert say_tok.line == 2
