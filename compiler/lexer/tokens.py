"""Backward-compat shim: re-exports from phases.phase1_lexical_analysis.tokens."""
from phases.phase1_lexical_analysis.tokens import (  # noqa: F401
    MAKE, WHEN, OTHERWISE, REPEAT, FUNC, RETURN, SAY,
    KEYWORDS,
    IDENTIFIER, NUMBER, STRING,
    PLUS, MINUS, STAR, SLASH,
    ASSIGN, EQUAL, NOT_EQUAL, LESS, GREATER, LESS_EQUAL, GREATER_EQUAL,
    LPAREN, RPAREN, LBRACE, RBRACE, COMMA, LBRACKET, RBRACKET,
    STATEMENT_END, EOF,
    Token,
)
