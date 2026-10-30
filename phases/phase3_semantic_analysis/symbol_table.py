"""Symbol table with lexical scoping (a stack of dict scopes)."""


class Symbol:
    __slots__ = ("name", "type", "value")

    def __init__(self, name, type_, value=None):
        self.name = name
        self.type = type_
        self.value = value

    def to_dict(self):
        return {"name": self.name, "type": self.type, "value": self.value}


class FunctionSymbol:
    __slots__ = ("name", "params")

    def __init__(self, name, params):
        self.name = name
        self.params = params


class SymbolTable:
    def __init__(self):
        self.scopes = [{}]          # variable scopes, stack
        self.functions = {}         # global function table
        self._all_declared = []     # ordered log for display (global scope only)

    # ---- scope management ----
    def push_scope(self):
        self.scopes.append({})

    def pop_scope(self):
        self.scopes.pop()

    # ---- variables ----
    def declare(self, name, type_, value=None):
        scope = self.scopes[-1]
        scope[name] = Symbol(name, type_, value)
        if len(self.scopes) == 1:
            self._all_declared.append(name)

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        return None

    def is_declared_in_current_scope(self, name):
        return name in self.scopes[-1]

    # ---- functions ----
    def declare_function(self, name, params):
        self.functions[name] = FunctionSymbol(name, params)

    def lookup_function(self, name):
        return self.functions.get(name)

    # ---- display helpers (global scope snapshot, for the UI) ----
    def snapshot(self):
        rows = []
        seen = set()
        for name in self._all_declared:
            sym = self.scopes[0].get(name)
            if sym and name not in seen:
                rows.append(sym.to_dict())
                seen.add(name)
        return rows
