"""
KRAK Lexer
==========

Turns raw source text into a flat stream of Token objects.
The lexer has no idea what the program *means* -- it only answers
"what are these pieces?".

WEIRD GRAMMAR RULE -- The Mirror String Rule
---------------------------------------------
Every string literal in KRAK source must be written BACKWARDS.
The lexer un-reverses it while tokenizing, so:

    SAY "olleH"!      ->   prints: Hello
    SAY "!dlrow olleH"!  -> prints: Hello world!

This is 100% intentional lunacy for the lab demo -- it forces the
lexer to actually transform literal values (not just chop them out),
which is a nice talking point in a viva ("look, the lexer already
does semantic-adjacent work here").
"""

from .tokens import (
    Token, KEYWORDS,
    IDENTIFIER, NUMBER, STRING,
    PLUS, MINUS, STAR, SLASH,
    ASSIGN, EQUAL, NOT_EQUAL, LESS, GREATER, LESS_EQUAL, GREATER_EQUAL,
    LPAREN, RPAREN, LBRACE, RBRACE, COMMA, LBRACKET, RBRACKET,
    STATEMENT_END, EOF,
)
from phases.phase0_common.errors import LexicalError


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    # ---- low level helpers ----------------------------------------
    def _peek(self, offset=0):
        i = self.pos + offset
        if i >= len(self.source):
            return "\0"
        return self.source[i]

    def _advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def _at_end(self):
        return self.pos >= len(self.source)

    def _add(self, type_, value, line, col):
        self.tokens.append(Token(type_, value, line, col))

    # ---- main entry point -------------------------------------------
    def tokenize(self):
        while not self._at_end():
            self._skip_whitespace_and_comments()
            if self._at_end():
                break
            start_line, start_col = self.line, self.col
            ch = self._peek()

            if ch.isdigit():
                self._number(start_line, start_col)
            elif ch == '"':
                self._string(start_line, start_col)
            elif ch == "$" or ch.isalpha() or ch == "_":
                self._identifier_or_keyword(start_line, start_col)
            else:
                self._symbol(start_line, start_col)

        self._add(EOF, None, self.line, self.col)
        return self.tokens

    def _skip_whitespace_and_comments(self):
        while not self._at_end():
            ch = self._peek()
            if ch in " \t\r\n":
                self._advance()
            elif ch == "#":  # line comment
                while not self._at_end() and self._peek() != "\n":
                    self._advance()
            else:
                break

    def _number(self, line, col):
        start = self.pos
        is_float = False
        while self._peek().isdigit():
            self._advance()
        if self._peek() == "." and self._peek(1).isdigit():
            is_float = True
            self._advance()
            while self._peek().isdigit():
                self._advance()
        text = self.source[start:self.pos]
        value = float(text) if is_float else int(text)
        self._add(NUMBER, value, line, col)

    def _string(self, line, col):
        self._advance()  # opening quote
        start = self.pos
        while not self._at_end() and self._peek() != '"':
            if self._peek() == "\n":
                raise LexicalError("Unterminated string literal", line, col)
            self._advance()
        if self._at_end():
            raise LexicalError("Unterminated string literal", line, col)
        raw = self.source[start:self.pos]
        self._advance()  # closing quote

        # --- THE MIRROR STRING RULE ---
        # Source text is written backwards; the lexer flips it back
        # to the "real" string value used everywhere downstream.
        value = raw[::-1]
        self._add(STRING, value, line, col)

    def _identifier_or_keyword(self, line, col):
        start = self.pos
        if self._peek() == "$":
            self._advance()
            if not (self._peek().isalpha() or self._peek() == "_"):
                raise LexicalError("Expected identifier name after '$'", line, col)
        while self._peek().isalnum() or self._peek() == "_":
            self._advance()
        text = self.source[start:self.pos]

        if text.startswith("$"):
            self._add(IDENTIFIER, text, line, col)
        elif text in KEYWORDS:
            self._add(KEYWORDS[text], text, line, col)
        else:
            # bare identifiers (function/param names) without '$'
            self._add(IDENTIFIER, text, line, col)

    _TWO_CHAR = {
        "==": EQUAL, "!=": NOT_EQUAL,
        "<=": LESS_EQUAL, ">=": GREATER_EQUAL,
    }
    _ONE_CHAR = {
        "+": PLUS, "-": MINUS, "*": STAR, "/": SLASH,
        "=": ASSIGN, "<": LESS, ">": GREATER,
        "(": LPAREN, ")": RPAREN, "{": LBRACE, "}": RBRACE,
        ",": COMMA, "!": STATEMENT_END,
        "[": LBRACKET, "]": RBRACKET,
    }

    def _symbol(self, line, col):
        two = self._peek() + self._peek(1)
        if two in self._TWO_CHAR:
            self._advance()
            self._advance()
            self._add(self._TWO_CHAR[two], two, line, col)
            return
        one = self._peek()
        if one in self._ONE_CHAR:
            self._advance()
            self._add(self._ONE_CHAR[one], one, line, col)
            return
        raise LexicalError(f"Unexpected character {one!r}", line, col)
