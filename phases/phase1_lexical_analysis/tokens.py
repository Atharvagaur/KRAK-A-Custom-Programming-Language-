"""Token type definitions for the KRAK language."""

# --- Keywords ---
MAKE = "MAKE"
WHEN = "WHEN"
OTHERWISE = "OTHERWISE"
REPEAT = "REPEAT"
FUNC = "FUNC"
RETURN = "RETURN"
SAY = "SAY"

KEYWORDS = {
    "MAKE": MAKE,
    "WHEN": WHEN,
    "OTHERWISE": OTHERWISE,
    "REPEAT": REPEAT,
    "FUNC": FUNC,
    "RETURN": RETURN,
    "SAY": SAY,
}

# --- Literals / identifiers ---
IDENTIFIER = "IDENTIFIER"
NUMBER = "NUMBER"
STRING = "STRING"

# --- Operators ---
PLUS = "PLUS"
MINUS = "MINUS"
STAR = "STAR"
SLASH = "SLASH"

ASSIGN = "ASSIGN"
EQUAL = "EQUAL"
NOT_EQUAL = "NOT_EQUAL"
LESS = "LESS"
GREATER = "GREATER"
LESS_EQUAL = "LESS_EQUAL"
GREATER_EQUAL = "GREATER_EQUAL"

# --- Punctuation ---
LPAREN = "LPAREN"
RPAREN = "RPAREN"
LBRACE = "LBRACE"
RBRACE = "RBRACE"
COMMA = "COMMA"
LBRACKET = "LBRACKET"
RBRACKET = "RBRACKET"

STATEMENT_END = "STATEMENT_END"   # the mandatory '!'
EOF = "EOF"


class Token:
    """A single lexical token, carrying its source position for diagnostics."""

    __slots__ = ("type", "value", "line", "column")

    def __init__(self, type_, value, line, column):
        self.type = type_
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, line={self.line}, col={self.column})"

    def to_dict(self):
        return {"type": self.type, "value": self.value, "line": self.line, "column": self.column}
