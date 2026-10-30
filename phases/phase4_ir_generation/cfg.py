"""Control-flow graph for KRAK's labeled, three-address IR.

Each function and ``__main__`` is analyzed independently because bytecode
uses a separate chunk per function. Block instruction indices refer to the
original flat IR sequence, which lets later compiler stages preserve exact
debugger mappings.
"""

from dataclasses import dataclass, field

from .instructions import IRFuncBegin, IRFuncEnd, IRJump, IRJumpIfFalse, IRLabel, IRReturn


@dataclass
class BasicBlock:
    id: str
    function: str
    instructions: list = field(default_factory=list)
    indices: list = field(default_factory=list)
    predecessors: list = field(default_factory=list)
    successors: list = field(default_factory=list)
    entry: bool = False
    exit: bool = False

    def to_dict(self):
        terminator = self.instructions[-1] if self.instructions else None
        return {
            "id": self.id, "function": self.function, "entry": self.entry,
            "exit": self.exit,
            "instructions": [{"index": i, **instr.to_dict()} for i, instr in zip(self.indices, self.instructions)],
            "predecessors": list(self.predecessors), "successors": list(self.successors),
            "branch": terminator.to_line() if isinstance(terminator, IRJumpIfFalse) else None,
        }


@dataclass
class ControlFlowGraph:
    blocks: list
    functions: dict
    instruction_to_block: dict

    def to_dict(self):
        return {"blocks": [block.to_dict() for block in self.blocks],
                "functions": self.functions,
                "instruction_to_block": {str(k): v for k, v in self.instruction_to_block.items()}}

    def validate(self):
        by_id = {block.id: block for block in self.blocks}
        for block in self.blocks:
            for succ in block.successors:
                if succ["target"] not in by_id:
                    raise ValueError(f"CFG edge from {block.id} targets missing block {succ['target']}")
                if block.id not in by_id[succ["target"]].predecessors:
                    raise ValueError(f"CFG predecessor mismatch for {succ['target']}")
            for pred in block.predecessors:
                if block.id not in [edge["target"] for edge in by_id[pred].successors]:
                    raise ValueError(f"CFG successor mismatch for {pred}")
        return True


def build_cfg(code):
    """Split IR at leaders and derive jump/fall-through edges."""
    segments = []
    current_name, current = "__main__", []
    for index, instr in enumerate(code):
        if isinstance(instr, IRFuncBegin):
            if current:
                segments.append((current_name, current))
                current = []
            current_name = instr.name
            continue
        if isinstance(instr, IRFuncEnd):
            segments.append((current_name, current))
            current_name, current = "__main__", []
            continue
        current.append((index, instr))
    if current or not segments:
        segments.append((current_name, current))
    if not any(name == "__main__" for name, _ in segments):
        segments.append(("__main__", []))

    all_blocks, function_info, instruction_to_block = [], {}, {}
    for function, items in segments:
        if function in function_info:
            raise ValueError(f"duplicate function body '{function}'")
        if not items:
            block = BasicBlock(f"{function}:B0", function, entry=True, exit=True)
            all_blocks.append(block)
            function_info[function] = {"entry": block.id, "blocks": [block.id]}
            continue
        label_to_pos = {}
        for pos, (_, instr) in enumerate(items):
            if isinstance(instr, IRLabel):
                if instr.name in label_to_pos:
                    raise ValueError(f"duplicate label '{instr.name}' in {function}")
                label_to_pos[instr.name] = pos
        leaders = {0}
        for pos, (_, instr) in enumerate(items):
            if isinstance(instr, IRLabel):
                leaders.add(pos)
            if isinstance(instr, (IRJump, IRJumpIfFalse, IRReturn)) and pos + 1 < len(items):
                leaders.add(pos + 1)
        starts = sorted(leaders)
        chunks = [items[start:(starts[i + 1] if i + 1 < len(starts) else len(items))]
                  for i, start in enumerate(starts)]
        pos_to_block = {}
        blocks = []
        for number, chunk in enumerate(chunks):
            block_id = f"{function}:B{number}"
            block = BasicBlock(block_id, function,
                               [instr for _, instr in chunk], [index for index, _ in chunk], entry=(number == 0))
            blocks.append(block)
            for pos in range(starts[number], starts[number] + len(chunk)):
                pos_to_block[pos] = block
            for index, _ in chunk:
                instruction_to_block[str(index)] = block_id
        label_blocks = {name: pos_to_block[pos].id for name, pos in label_to_pos.items()}
        for n, block in enumerate(blocks):
            last = block.instructions[-1]
            fallthrough = blocks[n + 1].id if n + 1 < len(blocks) else None
            edges = []
            if isinstance(last, IRJump):
                if last.label not in label_blocks:
                    raise ValueError(f"jump in {function} targets missing label '{last.label}'")
                edges.append({"target": label_blocks[last.label], "kind": "jump", "label": last.label})
            elif isinstance(last, IRJumpIfFalse):
                if last.label not in label_blocks:
                    raise ValueError(f"conditional jump in {function} targets missing label '{last.label}'")
                edges.append({"target": label_blocks[last.label], "kind": "false", "label": last.label})
                if fallthrough:
                    edges.append({"target": fallthrough, "kind": "true", "label": None})
            elif isinstance(last, IRReturn):
                block.exit = True
            elif fallthrough:
                edges.append({"target": fallthrough, "kind": "fallthrough", "label": None})
            else:
                block.exit = True
            block.successors = edges
            for edge in edges:
                target = next(b for b in blocks if b.id == edge["target"])
                if block.id not in target.predecessors:
                    target.predecessors.append(block.id)
        function_info[function] = {"entry": blocks[0].id, "blocks": [b.id for b in blocks]}
        all_blocks.extend(blocks)
    graph = ControlFlowGraph(all_blocks, function_info, instruction_to_block)
    graph.validate()
    return graph
