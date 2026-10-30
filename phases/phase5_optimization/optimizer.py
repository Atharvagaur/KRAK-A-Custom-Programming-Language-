"""Local IR optimizations plus conservative control-flow-aware passes."""

import operator
from phases.phase4_ir_generation.instructions import (
    IRConst, IRCopy, IRBinOp, IRUnaryOp, IRPrint, IRLabel,
    IRJump, IRJumpIfFalse, IRFuncBegin, IRFuncEnd, IRReturn, IRCall,
    IRArray, IRGetIndex, IRSetIndex,
)
from phases.phase4_ir_generation.cfg import build_cfg

_BIN_OPS = {
    "+": operator.add, "-": operator.sub, "*": operator.mul,
    "/": lambda a, b: a / b if isinstance(a, float) or isinstance(b, float) else a // b,
    "==": operator.eq, "!=": operator.ne,
    "<": operator.lt, ">": operator.gt, "<=": operator.le, ">=": operator.ge,
}

_CONSTANT = "constant"
_OVERDEFINED = ("overdefined",)
_MISSING = object()


def _is_constant(value):
    return isinstance(value, tuple) and len(value) == 2 and value[0] == _CONSTANT


class Optimizer:
    def __init__(self):
        self.notes = []  # human-readable log of what got optimized, for the UI
        self.remarks = []

    def optimize(self, code, control_flow=True):
        code = self._fold_and_propagate(code)
        code = self._dead_store_elim(code)
        if control_flow:
            code = self._control_flow_optimize(code)
        return code

    def _remark(self, pass_name, instr, after, reason):
        remark = {"pass": pass_name, "instruction": instr.to_line(),
                  "result": after, "reason": reason,
                  "line": getattr(instr, "source_line", None)}
        self.remarks.append(remark)

    @staticmethod
    def _copy_line(source, target):
        target.source_line = getattr(source, "source_line", None)
        return target

    def _control_flow_optimize(self, code):
        """Run conservative global constant propagation and CFG cleanup."""
        # Validate before making changes. Bad labels are compiler errors, not
        # opportunities for a best-effort rewrite.
        build_cfg(code)
        code = self._global_constant_propagation(code)
        code = self._fold_constant_branches(code)
        code = self._remove_unreachable_blocks(code)
        code = self._simplify_jumps(code)
        build_cfg(code)
        return code

    @staticmethod
    def _join_constants(states):
        """Join reachable predecessor maps; None means iteration bottom."""
        present = [state for state in states if state is not None]
        if not present:
            return None
        keys = set().union(*(state.keys() for state in present))
        result = {}
        for key in keys:
            vals = [state.get(key, _OVERDEFINED) for state in present]
            first = vals[0]
            if _is_constant(first) and all(
                _is_constant(v) and type(v[1]) is type(first[1]) and v[1] == first[1]
                for v in vals[1:]
            ):
                result[key] = first
            else:
                result[key] = _OVERDEFINED
        return result

    def _global_constant_propagation(self, code):
        graph = build_cfg(code)
        by_id = {b.id: b for b in graph.blocks}
        rewritten_by_index = {}
        for function, info in graph.functions.items():
            ids = info["blocks"]
            if not ids:
                continue
            blocks = [by_id[i] for i in ids]
            reachable = set()
            stack = [info["entry"]]
            while stack:
                bid = stack.pop()
                if bid in reachable:
                    continue
                reachable.add(bid)
                stack.extend(edge["target"] for edge in by_id[bid].successors)
            # UNDEFINED is the fixed-point bottom; missing definitions at a
            # reachable merge become OVERDEFINED once their predecessor is known.
            in_state, out_state = {bid: None for bid in ids}, {bid: None for bid in ids}
            params = []
            for instr in code:
                if isinstance(instr, IRFuncBegin) and instr.name == function:
                    params = instr.params
                    break
            entry_state = {name: _OVERDEFINED for name in params}
            limit = max(4, len(blocks) * 4)
            for _ in range(limit):
                changed = False
                for block in blocks:
                    if block.id not in reachable:
                        continue
                    if block.id == info["entry"]:
                        incoming = entry_state
                    else:
                        pred_states = [out_state[p] for p in block.predecessors if p in reachable]
                        incoming = self._join_constants(pred_states)
                        if incoming is None:
                            continue
                    state = dict(incoming)
                    for instr in block.instructions:
                        self._transfer(instr, state, None)
                    if in_state[block.id] != incoming or out_state[block.id] != state:
                        in_state[block.id], out_state[block.id] = dict(incoming), state
                        changed = True
                if not changed:
                    break
            else:
                raise ValueError(f"constant propagation failed to converge in {function}")

            # Rewrite only after convergence, using the entry facts of each block.
            for block in blocks:
                if block.id not in reachable or in_state[block.id] is None:
                    continue
                state = dict(in_state[block.id])
                for index, instr in zip(block.indices, block.instructions):
                    replacement = self._transfer(instr, state, "rewrite")
                    rewritten_by_index[index] = replacement

        return [replacement for i, instr in enumerate(code)
                if (replacement := rewritten_by_index.get(i, instr)) is not None]

    def _transfer(self, instr, state, mode):
        """Transfer one IR instruction; mode=rewrite emits safe folded IR."""
        replacement = instr
        if isinstance(instr, IRConst):
            state[instr.target] = (_CONSTANT, instr.value)
        elif isinstance(instr, IRCopy):
            value = state.get(instr.source, _OVERDEFINED)
            if _is_constant(value):
                state[instr.target] = value
                if mode and not (isinstance(instr, IRConst) and instr.value == value[1]):
                    replacement = self._copy_line(instr, IRConst(instr.target, value[1]))
                    self._remark("global constant propagation", instr, replacement.to_line(),
                                 f"{instr.source} is constant on every reachable incoming path")
            else:
                state[instr.target] = _OVERDEFINED
        elif isinstance(instr, IRBinOp):
            lv, rv = state.get(instr.left, _OVERDEFINED), state.get(instr.right, _OVERDEFINED)
            if _is_constant(lv) and _is_constant(rv) and instr.op in _BIN_OPS:
                try:
                    value = _BIN_OPS[instr.op](lv[1], rv[1])
                except (ZeroDivisionError, TypeError, ValueError, OverflowError):
                    value = _OVERDEFINED
                if value is not _OVERDEFINED:
                    state[instr.target] = (_CONSTANT, value)
                    if mode:
                        replacement = self._copy_line(instr, IRConst(instr.target, value))
                        self._remark("global constant propagation", instr, replacement.to_line(),
                                     "both operands are proven constant at this program point")
                else:
                    state[instr.target] = _OVERDEFINED
            else:
                state[instr.target] = _OVERDEFINED
        elif isinstance(instr, IRUnaryOp):
            value = state.get(instr.operand, _OVERDEFINED)
            if _is_constant(value) and instr.op == "-":
                result = -value[1]
                state[instr.target] = (_CONSTANT, result)
                if mode:
                    replacement = self._copy_line(instr, IRConst(instr.target, result))
                    self._remark("global constant propagation", instr, replacement.to_line(),
                                 "operand is proven constant at this program point")
            else:
                state[instr.target] = _OVERDEFINED
        elif isinstance(instr, (IRArray, IRGetIndex, IRCall)):
            target = getattr(instr, "target", None)
            if target:
                state[target] = _OVERDEFINED
        elif isinstance(instr, IRSetIndex):
            # Arrays are never represented as constants in this domain.
            state[instr.array] = _OVERDEFINED
        elif isinstance(instr, IRJumpIfFalse) and mode:
            value = state.get(instr.cond, _OVERDEFINED)
            if _is_constant(value) and isinstance(value[1], bool):
                if value[1]:
                    replacement = None
                    self._remark("constant branch folding", instr, "removed",
                                 "the condition is proven true on every reachable incoming path")
                else:
                    replacement = self._copy_line(instr, IRJump(instr.label))
                    self._remark("constant branch folding", instr, replacement.to_line(),
                                 "the condition is proven false on every reachable incoming path")
        return replacement

    def _fold_constant_branches(self, code):
        graph = build_cfg(code)
        block_by_index = {i: block for block in graph.blocks for i in block.indices}
        out = []
        for index, instr in enumerate(code):
            if isinstance(instr, IRJumpIfFalse):
                block = block_by_index[index]
                # Condition definition may be an immediately dominating constant
                # emitted by the preceding dataflow rewrite.
                constants = {}
                for prior in block.instructions:
                    if prior is instr:
                        break
                    if isinstance(prior, IRConst):
                        constants[prior.target] = prior.value
                    elif isinstance(prior, (IRCopy, IRBinOp, IRUnaryOp, IRCall, IRArray, IRGetIndex)):
                        constants.pop(getattr(prior, "target", None), None)
                condition = constants.get(instr.cond, _MISSING)
                if condition is not _MISSING and isinstance(condition, bool):
                    if condition:
                        self._remark("constant branch folding", instr, "removed",
                                     "the condition is proven true; execution falls through")
                    else:
                        replacement = self._copy_line(instr, IRJump(instr.label))
                        out.append(replacement)
                        self._remark("constant branch folding", instr, replacement.to_line(),
                                     "the condition is proven false")
                    continue
            out.append(instr)
        return out

    def _remove_unreachable_blocks(self, code):
        graph = build_cfg(code)
        by_id = {b.id: b for b in graph.blocks}
        keep_indices = set()
        for info in graph.functions.values():
            if not info["entry"]:
                continue
            reachable, stack = set(), [info["entry"]]
            while stack:
                bid = stack.pop()
                if bid in reachable:
                    continue
                reachable.add(bid)
                stack.extend(edge["target"] for edge in by_id[bid].successors)
            for bid in reachable:
                keep_indices.update(by_id[bid].indices)
        result = []
        for i, instr in enumerate(code):
            if isinstance(instr, (IRFuncBegin, IRFuncEnd)) or i in keep_indices:
                result.append(instr)
            else:
                self._remark("unreachable block elimination", instr, "removed",
                             "its block is not reachable from this function's entry")
        return result

    def _simplify_jumps(self, code):
        result = list(code)
        def scopes(items):
            names, current = [], "__main__"
            for instr in items:
                if isinstance(instr, IRFuncBegin):
                    current = instr.name
                names.append(current)
                if isinstance(instr, IRFuncEnd):
                    current = "__main__"
            return names

        # Redirect through label-only blocks ending in an unconditional jump.
        for _ in range(max(1, len(result))):
            scope_at = scopes(result)
            labels = {}
            for i, instr in enumerate(result):
                if isinstance(instr, IRLabel):
                    labels[(scope_at[i], instr.name)] = i
            next_target = {}
            for (scope, name), pos in labels.items():
                j = pos + 1
                while j < len(result) and isinstance(result[j], IRLabel):
                    j += 1
                if j < len(result) and scope_at[j] == scope and isinstance(result[j], IRJump):
                    next_target[(scope, name)] = result[j].label
            changed = False
            rewritten = []
            for index, instr in enumerate(result):
                if isinstance(instr, (IRJump, IRJumpIfFalse)):
                    label = instr.label
                    seen = set()
                    scope = scope_at[index]
                    while (scope, label) in next_target and label not in seen:
                        seen.add(label); label = next_target[(scope, label)]
                    if label != instr.label:
                        new = self._copy_line(instr, type(instr)(**({"label": label} if isinstance(instr, IRJump) else {"cond": instr.cond, "label": label})))
                        self._remark("jump threading", instr, new.to_line(),
                                     "the destination immediately forwards to the final target")
                        instr = new; changed = True
                rewritten.append(instr)
            result = rewritten
            if not changed:
                break
        # A jump to the next executable block is equivalent to falling through.
        scope_at = scopes(result)
        labels = {}
        for i, instr in enumerate(result):
            if isinstance(instr, IRLabel): labels[(scope_at[i], instr.name)] = i
        out = []
        for i, instr in enumerate(result):
            target = (scope_at[i], instr.label) if isinstance(instr, IRJump) else None
            if isinstance(instr, IRJump) and target in labels:
                j = labels[target] + 1
                while j < len(result) and scope_at[j] == scope_at[i] and isinstance(result[j], IRLabel): j += 1
                next_i = i + 1
                while next_i < len(result) and scope_at[next_i] == scope_at[i] and isinstance(result[next_i], IRLabel): next_i += 1
                if j == next_i:
                    self._remark("redundant jump elimination", instr, "removed",
                                 "the target is the immediately following block")
                    continue
            out.append(instr)
        return out

    # ---- pass 1 + 2: constant folding & propagation ----
    def _fold_and_propagate(self, code):
        out = []
        constants = {}  # var/temp -> known constant value

        def const_of(place):
            if place in constants:
                return constants[place]
            try:
                return int(place)
            except (TypeError, ValueError):
                return None

        for instr in code:
            if isinstance(instr, (IRLabel, IRFuncBegin, IRFuncEnd)):
                # control-flow join points / func boundaries invalidate our
                # simple straight-line constant knowledge
                constants.clear()
                out.append(instr)
                continue

            if isinstance(instr, IRConst):
                constants[instr.target] = instr.value
                out.append(instr)
                continue

            if isinstance(instr, IRCopy):
                if instr.source in constants:
                    constants[instr.target] = constants[instr.source]
                else:
                    constants.pop(instr.target, None)
                out.append(instr)
                continue

            if isinstance(instr, IRBinOp):
                lv = constants.get(instr.left)
                rv = constants.get(instr.right)
                if lv is not None and rv is not None and instr.op in _BIN_OPS:
                    # both operands known -> fully fold to a constant
                    try:
                        result = _BIN_OPS[instr.op](lv, rv)
                    except ZeroDivisionError:
                        out.append(instr)
                        constants.pop(instr.target, None)
                        continue
                    new_instr = IRConst(target=instr.target, value=result)
                    new_instr.source_line = getattr(instr, "source_line", None)
                    self.notes.append(
                        f"constant folded: {instr.left}({lv}) {instr.op} {instr.right}({rv}) -> {result}"
                    )
                    constants[instr.target] = result
                    out.append(new_instr)
                elif instr.op == "+" and rv == 0 and lv is None:
                    self.notes.append(f"simplified: {instr.left} + 0 -> {instr.left}")
                    constants.pop(instr.target, None)
                    simplified = IRCopy(target=instr.target, source=instr.left)
                    simplified.source_line = getattr(instr, "source_line", None)
                    out.append(simplified)
                elif instr.op == "+" and lv == 0 and rv is None:
                    self.notes.append(f"simplified: 0 + {instr.right} -> {instr.right}")
                    constants.pop(instr.target, None)
                    simplified = IRCopy(target=instr.target, source=instr.right)
                    simplified.source_line = getattr(instr, "source_line", None)
                    out.append(simplified)
                elif instr.op == "*" and rv == 1 and lv is None:
                    self.notes.append(f"simplified: {instr.left} * 1 -> {instr.left}")
                    constants.pop(instr.target, None)
                    simplified = IRCopy(target=instr.target, source=instr.left)
                    simplified.source_line = getattr(instr, "source_line", None)
                    out.append(simplified)
                elif instr.op == "*" and lv == 1 and rv is None:
                    self.notes.append(f"simplified: 1 * {instr.right} -> {instr.right}")
                    constants.pop(instr.target, None)
                    simplified = IRCopy(target=instr.target, source=instr.right)
                    simplified.source_line = getattr(instr, "source_line", None)
                    out.append(simplified)
                else:
                    constants.pop(instr.target, None)
                    out.append(instr)
                continue

            if isinstance(instr, IRUnaryOp):
                v = constants.get(instr.operand)
                if v is not None and instr.op == "-":
                    result = -v
                    self.notes.append(f"constant folded: -{instr.operand}({v}) -> {result}")
                    constants[instr.target] = result
                    folded = IRConst(target=instr.target, value=result)
                    folded.source_line = getattr(instr, "source_line", None)
                    out.append(folded)
                else:
                    constants.pop(instr.target, None)
                    out.append(instr)
                continue

            if isinstance(instr, (IRPrint, IRJumpIfFalse)):
                out.append(instr)
                continue

            if isinstance(instr, IRCall):
                if instr.target:
                    constants.pop(instr.target, None)
                out.append(instr)
                continue

            out.append(instr)

        return out

    # ---- pass 3: dead-store elimination ----
    def _dead_store_elim(self, code):
        """If a straight-line run assigns to the same target twice with no
        read of it in between, the earlier assignment is dead."""
        result = list(code)
        changed = True
        while changed:
            changed = False
            last_write_idx = {}
            drop = set()
            for i, instr in enumerate(result):
                if isinstance(instr, (IRLabel, IRFuncBegin, IRFuncEnd, IRJump, IRJumpIfFalse)):
                    last_write_idx.clear()
                    continue
                # reads
                for read in self._reads_of(instr):
                    last_write_idx.pop(read, None)
                # writes
                target = self._write_of(instr)
                if target is not None:
                    if target in last_write_idx:
                        drop.add(last_write_idx[target])
                        changed = True
                    last_write_idx[target] = i
            if drop:
                for i in sorted(drop):
                    self.notes.append(f"dead store eliminated: {result[i].to_line()}")
                result = [instr for i, instr in enumerate(result) if i not in drop]
        return result

    @staticmethod
    def _write_of(instr):
        # Only assignments with no runtime-visible evaluation are candidates.
        # Arithmetic, indexing, calls, and array construction may fail or have
        # observable effects even when their result is overwritten.
        if isinstance(instr, (IRConst, IRCopy)):
            return instr.target
        return None

    @staticmethod
    def _reads_of(instr):
        if isinstance(instr, IRCopy):
            return [instr.source]
        if isinstance(instr, IRArray):
            return list(instr.elements)
        if isinstance(instr, IRGetIndex):
            return [instr.array, instr.index]
        if isinstance(instr, IRSetIndex):
            return [instr.array, instr.index, instr.value]
        if isinstance(instr, IRBinOp):
            return [instr.left, instr.right]
        if isinstance(instr, IRUnaryOp):
            return [instr.operand]
        if isinstance(instr, IRPrint):
            return [instr.value]
        if isinstance(instr, IRJumpIfFalse):
            return [instr.cond]
        if isinstance(instr, IRReturn) and instr.value is not None:
            return [instr.value]
        if isinstance(instr, IRCall):
            return list(instr.args)
        return []
