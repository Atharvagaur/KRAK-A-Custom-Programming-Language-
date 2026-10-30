"""Compiles linear IR into stack-based bytecode.

Functions are compiled into separate named chunks (dict: name -> [Instr]);
the main program is its own chunk called "__main__". CALL instructions in
bytecode reference a function name; the VM looks the chunk up at runtime.
"""

from phases.phase4_ir_generation.instructions import (
    IRConst, IRCopy, IRBinOp, IRUnaryOp, IRPrint, IRLabel,
    IRJump, IRJumpIfFalse, IRFuncBegin, IRFuncEnd, IRReturn, IRCall,
    IRArray, IRGetIndex, IRSetIndex,
)
from .instructions import (
    Instr, PUSH_CONST, LOAD, STORE, ADD, SUB, MUL, DIV, NEG,
    CMP_LT, CMP_GT, CMP_LE, CMP_GE, CMP_EQ, CMP_NEQ,
    JUMP, JUMP_IF_FALSE, PRINT, CALL, RETURN, POP, HALT,
    MAKE_ARRAY, GET_INDEX, SET_INDEX,
)

_BIN_OP_MAP = {
    "+": ADD, "-": SUB, "*": MUL, "/": DIV,
    "<": CMP_LT, ">": CMP_GT, "<=": CMP_LE, ">=": CMP_GE,
    "==": CMP_EQ, "!=": CMP_NEQ,
}


class BytecodeCompiler:
    def __init__(self):
        self.chunks = {}          # name -> list[Instr]  (labels still symbolic)
        self.functions = {}       # name -> params list
        self.bytecode_to_ir = {}

    def compile(self, ir_code):
        main_chunk = []
        current_chunk = main_chunk
        current_name = "__main__"
        last_ir_by_chunk = {"__main__": None}

        for ir_index, instr in enumerate(ir_code):
            if isinstance(instr, IRFuncBegin):
                self.chunks[current_name] = current_chunk
                current_name = instr.name
                current_chunk = []
                last_ir_by_chunk[current_name] = None
                self.functions[instr.name] = instr.params
                continue
            if isinstance(instr, IRFuncEnd):
                current_chunk.append(Instr(RETURN, None, ir_index=last_ir_by_chunk.get(current_name)))
                self.chunks[current_name] = current_chunk
                current_name = "__main__"
                current_chunk = main_chunk
                continue
            self._translate(instr, current_chunk, ir_index)
            last_ir_by_chunk[current_name] = ir_index

        current_chunk.append(Instr(HALT, ir_index=last_ir_by_chunk.get("__main__")))
        self.chunks[current_name] = current_chunk

        self.chunks = self._resolve_labels(self.chunks)
        self.bytecode_to_ir = {name: [instr.ir_index for instr in chunk]
                               for name, chunk in self.chunks.items()}
        return self.chunks

    def _translate(self, instr, out, ir_index):
        start = len(out)
        self._translate_inner(instr, out)
        for emitted in out[start:]:
            emitted.source_line = getattr(instr, "source_line", None)
            emitted.ir_index = ir_index

    def _translate_inner(self, instr, out):
        if isinstance(instr, IRArray):
            for element in instr.elements:
                out.append(Instr(LOAD, element))
            out.append(Instr(MAKE_ARRAY, len(instr.elements)))
            out.append(Instr(STORE, instr.target))
            return
        if isinstance(instr, IRGetIndex):
            out.extend((Instr(LOAD, instr.array), Instr(LOAD, instr.index), Instr(GET_INDEX), Instr(STORE, instr.target)))
            return
        if isinstance(instr, IRSetIndex):
            out.extend((Instr(LOAD, instr.array), Instr(LOAD, instr.index), Instr(LOAD, instr.value), Instr(SET_INDEX)))
            return
        if isinstance(instr, IRConst):
            out.append(Instr(PUSH_CONST, instr.value))
            out.append(Instr(STORE, instr.target))
            return
        if isinstance(instr, IRCopy):
            out.append(Instr(LOAD, instr.source))
            out.append(Instr(STORE, instr.target))
            return
        if isinstance(instr, IRBinOp):
            out.append(Instr(LOAD, instr.left))
            out.append(Instr(LOAD, instr.right))
            out.append(Instr(_BIN_OP_MAP[instr.op]))
            out.append(Instr(STORE, instr.target))
            return
        if isinstance(instr, IRUnaryOp):
            out.append(Instr(LOAD, instr.operand))
            out.append(Instr(NEG))
            out.append(Instr(STORE, instr.target))
            return
        if isinstance(instr, IRPrint):
            out.append(Instr(LOAD, instr.value))
            out.append(Instr(PRINT))
            return
        if isinstance(instr, IRLabel):
            out.append(Instr("LABEL", instr.name))
            return
        if isinstance(instr, IRJump):
            out.append(Instr(JUMP, instr.label))
            return
        if isinstance(instr, IRJumpIfFalse):
            out.append(Instr(LOAD, instr.cond))
            out.append(Instr(JUMP_IF_FALSE, instr.label))
            return
        if isinstance(instr, IRReturn):
            if instr.value is not None:
                out.append(Instr(LOAD, instr.value))
            else:
                out.append(Instr(PUSH_CONST, None))
            out.append(Instr(RETURN))
            return
        if isinstance(instr, IRCall):
            for a in instr.args:
                out.append(Instr(LOAD, a))
            out.append(Instr(CALL, (instr.name, len(instr.args))))
            if instr.target:
                out.append(Instr(STORE, instr.target))
            else:
                out.append(Instr(POP))
            return
        raise NotImplementedError(f"Bytecode compile: unsupported IR {type(instr).__name__}")

    @staticmethod
    def _resolve_labels(chunks):
        resolved = {}
        for name, chunk in chunks.items():
            addr = {}
            stripped = []
            for instr in chunk:
                if instr.op == "LABEL":
                    addr[instr.arg] = len(stripped)
                else:
                    stripped.append(instr)
            final = []
            for instr in stripped:
                if instr.op in (JUMP, JUMP_IF_FALSE):
                    final.append(Instr(instr.op, addr[instr.arg], instr.source_line, instr.ir_index))
                else:
                    final.append(instr)
            resolved[name] = final
        return resolved
