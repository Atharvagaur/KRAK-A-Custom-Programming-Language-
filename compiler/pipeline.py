"""The single orchestrator every consumer (CLI, web UI, tests) should call.

    result = compile_and_run(source)

`result` is a dict containing every intermediate artifact so a UI can
render each compiler stage, plus `output` / `errors`.
"""

from phases.phase1_lexical_analysis.lexer import Lexer
from phases.phase2_parsing.parser import Parser
from phases.phase3_semantic_analysis.analyzer import SemanticAnalyzer
from phases.phase4_ir_generation.generator import IRGenerator
from phases.phase5_optimization.optimizer import Optimizer
from phases.phase6_bytecode_generation.compiler import BytecodeCompiler
from phases.phase7_virtual_machine.virtual_machine import VirtualMachine
from phases.phase0_common.errors import KrakError
from phases.phase4_ir_generation.cfg import build_cfg


def compile_source(source: str, optimize=True, control_flow=True):
    """Compile source without starting execution; shared by run and debugger."""
    result = {
        "tokens": [],
        "ast": None,
        "symbols": [],
        "ir_before": [],
        "ir_after": [],
        "optimizer_notes": [],
        "optimizer_remarks": [],
        "cfg_before": None,
        "cfg_after": None,
        "bytecode_before": {},
        "bytecode_to_block": {},
        "optimization_enabled": bool(optimize),
        "control_flow_enabled": bool(optimize and control_flow),
        "bytecode": {},
        "output": [],
        "errors": [],
        "stage_reached": None,
    }

    try:
        # 1. Lexer
        tokens = Lexer(source).tokenize()
        result["tokens"] = [t.to_dict() for t in tokens]
        result["stage_reached"] = "lexer"

        # 2. Parser
        program = Parser(tokens).parse()
        result["ast"] = program.to_dict()
        result["stage_reached"] = "parser"

        # 3. Semantic analysis
        symtab = SemanticAnalyzer().analyze(program)
        result["symbols"] = symtab.snapshot()
        result["stage_reached"] = "semantic"

        # 4. IR generation
        ir_code = IRGenerator().generate(program)
        result["ir_before"] = [i.to_dict() for i in ir_code]
        original_cfg = build_cfg(ir_code)
        result["cfg_before"] = original_cfg.to_dict()
        result["stage_reached"] = "ir"

        # 5. Optimization
        optimizer = Optimizer()
        optimized = optimizer.optimize(ir_code, control_flow=control_flow) if optimize else list(ir_code)
        result["ir_after"] = [i.to_dict() for i in optimized]
        result["optimizer_notes"] = optimizer.notes if optimize else []
        result["optimizer_remarks"] = optimizer.remarks if optimize else []
        optimized_cfg = build_cfg(optimized)
        result["cfg_after"] = optimized_cfg.to_dict()
        result["stage_reached"] = "optimizer"

        # 6. Bytecode
        before_compiler = BytecodeCompiler()
        before_chunks = before_compiler.compile(ir_code)
        result["bytecode_before"] = {
            name: [instr.to_dict() for instr in instrs] for name, instrs in before_chunks.items()
        }
        bc_compiler = BytecodeCompiler()
        chunks = bc_compiler.compile(optimized)
        result["bytecode"] = {
            name: [instr.to_dict() for instr in instrs] for name, instrs in chunks.items()
        }
        result["bytecode_to_block"] = {
            name: [optimized_cfg.instruction_to_block.get(str(index),
                   optimized_cfg.functions.get(name, {}).get("entry")) if index is not None
                   else optimized_cfg.functions.get(name, {}).get("entry")
                   for index in indices]
            for name, indices in bc_compiler.bytecode_to_ir.items()
        }
        result["instruction_counts"] = {
            "ir_before": len(ir_code), "ir_after": len(optimized),
            "blocks_before": len(original_cfg.blocks), "blocks_after": len(optimized_cfg.blocks),
            "bytecode_before": sum(map(len, before_chunks.values())),
            "bytecode_after": sum(map(len, chunks.values())),
        }
        result["stage_reached"] = "bytecode"

        return result, chunks, bc_compiler.functions

    except KrakError as e:
        result["errors"].append(e.to_dict())
    except (ZeroDivisionError, IndexError, KeyError, RecursionError, ValueError) as e:
        result["errors"].append({"kind": "Internal Error", "message": str(e), "line": None, "column": None})

    return result, None, None


def compile_and_run(source: str, optimize=True, control_flow=True) -> dict:
    result, chunks, functions = compile_source(source, optimize=optimize, control_flow=control_flow)
    if result["errors"]:
        return result
    try:
        vm = VirtualMachine(chunks, param_map=functions, tracing=False)
        result["output"] = vm.run()
        result["stage_reached"] = "vm"
    except KrakError as e:
        result["errors"].append(e.to_dict())
    except (ZeroDivisionError, IndexError, KeyError, RecursionError, ValueError) as e:
        result["errors"].append({"kind": "Internal Error", "message": str(e), "line": None, "column": None})
    return result
