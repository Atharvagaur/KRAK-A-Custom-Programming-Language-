"""Structured error hierarchy for every compiler phase."""


class KrakError(Exception):
    """Base class for all KRAK compiler errors."""

    kind = "Error"

    def __init__(self, message, line=None, column=None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self.format())

    def format(self):
        loc = ""
        if self.line is not None:
            loc = f" (line {self.line}" + (f", column {self.column})" if self.column is not None else ")")
        return f"{self.kind}: {self.message}{loc}"

    def to_dict(self):
        return {"kind": self.kind, "message": self.message, "line": self.line, "column": self.column}


class LexicalError(KrakError):
    kind = "Lexical Error"


class SyntaxError_(KrakError):
    kind = "Syntax Error"


class SemanticError(KrakError):
    kind = "Semantic Error"


class KrakTypeError(KrakError):
    kind = "Type Error"


class RuntimeError_(KrakError):
    kind = "Runtime Error"
