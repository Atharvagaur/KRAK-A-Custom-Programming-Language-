"""Backward-compat shim: re-exports from phases.phase4_ir_generation.instructions."""
from phases.phase4_ir_generation.instructions import (  # noqa: F401
    IRInstr, IRConst, IRCopy, IRBinOp, IRUnaryOp, IRStore, IRArray,
    IRGetIndex, IRSetIndex, IRPrint, IRLabel, IRJump, IRJumpIfFalse,
    IRFuncBegin, IRFuncEnd, IRReturn, IRCall,
)
