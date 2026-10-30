"""Stack VM with an instruction-level execution history for the debugger.

Normal ``run()`` and interactive ``step()`` share the same dispatcher. History
stores bounded deep snapshots so rewind restores stacks, locals, arrays, calls,
and output rather than attempting to reverse control flow heuristically.
"""

from copy import deepcopy

from phases.phase6_bytecode_generation.instructions import (
    PUSH_CONST, LOAD, STORE, ADD, SUB, MUL, DIV, NEG,
    CMP_LT, CMP_GT, CMP_LE, CMP_GE, CMP_EQ, CMP_NEQ,
    JUMP, JUMP_IF_FALSE, PRINT, CALL, RETURN, POP, HALT,
    MAKE_ARRAY, GET_INDEX, SET_INDEX,
)
from phases.phase0_common.errors import RuntimeError_, KrakError

MAX_CALL_DEPTH = 200
MAX_HISTORY = 2000


class VirtualMachine:
    def __init__(self, chunks: dict, param_map: dict = None, tracing: bool = False):
        self.chunks = chunks
        self.param_map = param_map or {}
        self.tracing = tracing
        self.reset()

    def reset(self):
        """Start a fresh run without retaining any previous runtime values."""
        self.frames = [{"id": 0, "chunk": "__main__", "ip": 0, "vars": {}, "stack": []}]
        self.output = []
        self.status = "ready"
        self.error = None
        self.steps = 0
        self._next_frame_id = 1
        self._history = [self._snapshot()]
        self._events = []
        self._cursor = 0
        return self.state()

    def run(self):
        """Execute the program to completion using the normal VM dispatcher."""
        if not self.tracing:
            while self.status not in ("halted", "error"):
                frame = self.frames[-1]
                code = self.chunks[frame["chunk"]]
                if frame["ip"] >= len(code):
                    self.status = "halted"
                    break
                self._execute_one(frame, code[frame["ip"]])
                self.steps += 1
            return self.output
        while self.status not in ("halted", "error"):
            self.step()
        if self.error:
            raise RuntimeError_(self.error["message"], self.error.get("line"))
        return self.output

    def step(self):
        if self._cursor < len(self._history) - 1:
            self._history = self._history[:self._cursor + 1]
            self._events = self._events[:self._cursor]
        if self.status in ("halted", "error"):
            return self.state()
        if len(self._history) >= MAX_HISTORY + 1:
            self.status = "error"
            self.error = {"kind": "Runtime Error", "message": f"Execution history limit ({MAX_HISTORY} instructions) reached", "line": None}
            return self.state()

        if self.status == "ready":
            self.status = "running"
        frame = self.frames[-1]
        code = self.chunks[frame["chunk"]]
        if frame["ip"] >= len(code):
            self.status = "halted"
            return self.state()

        ip_before = frame["ip"]
        instr = code[ip_before]
        event = {
            "step": self.steps + 1,
            "chunk": frame["chunk"],
            "ip": ip_before,
            "ip_before": ip_before,
            "instruction": instr.to_dict(),
            "kind": self._event_kind(instr.op),
            "detail": "",
        }
        stack_before = list(frame["stack"])
        try:
            self._execute_one(frame, instr)
            if self.status not in ("halted", "error"):
                self.status = "paused"
            event["detail"] = self._event_detail(instr, frame, ip_before, stack_before)
        except KrakError as exc:
            self.status = "error"
            self.error = exc.to_dict()
            if self.error.get("line") is None:
                self.error["line"] = instr.source_line
            event["kind"] = "error"
            event["detail"] = exc.message
        except (ZeroDivisionError, IndexError, KeyError, TypeError, ValueError) as exc:
            self.status = "error"
            self.error = {"kind": "Runtime Error", "message": str(exc), "line": instr.source_line}
            event["kind"] = "error"
            event["detail"] = str(exc)

        active = self.frames[-1] if self.frames else None
        event["ip_after"] = {"chunk": active["chunk"], "index": active["ip"]} if active else None

        self.steps += 1
        self._events.append(event)
        self._history.append(self._snapshot())
        self._cursor += 1
        return self.state()

    def back(self):
        if self._cursor > 0:
            self._cursor -= 1
            self._events = self._events[:self._cursor]
            self._restore(self._history[self._cursor])
        return self.state()

    def run_to_end(self, max_steps=MAX_HISTORY):
        executed = 0
        while self.status not in ("halted", "error") and executed < max_steps:
            before = self.steps
            self.step()
            executed += self.steps - before
        return self.state()

    def inspect(self, step):
        if step < 0 or step >= len(self._history):
            raise ValueError("Unknown execution step")
        return self._state_from_snapshot(self._history[step], step)

    def events_before(self, before=None, limit=100):
        before = min(self._cursor + 1, before if before is not None else self._cursor + 1)
        before = max(1, before)
        start = max(0, before - 1 - limit)
        return {"events": deepcopy(self._events[start:before - 1]),
                "has_earlier": start > 0, "next_before": start + 1}

    def state(self):
        frame = self.frames[-1] if self.frames else None
        current = None
        if frame and self.status not in ("halted", "error"):
            code = self.chunks.get(frame["chunk"], [])
            if 0 <= frame["ip"] < len(code):
                current = code[frame["ip"]].to_dict()
        return {
            "status": self.status,
            "step": self._cursor,
            "instruction_pointer": {"chunk": frame["chunk"], "index": frame["ip"]} if frame else None,
            "current_instruction": current,
            "stack": self._json_value(frame["stack"]) if frame else [],
            "variables": self._json_value(frame["vars"]) if frame else {},
            "frames": self._frame_views(),
            "output": list(self.output),
            "error": self.error,
            "events": deepcopy(self._events[-200:]),
            "history_start": max(0, len(self._events) - 200),
            "history_size": len(self._events) + 1,
        }

    def _execute_one(self, frame, instr):
        op, arg = instr.op, instr.arg
        stack, variables = frame["stack"], frame["vars"]
        next_ip = frame["ip"] + 1
        if op == PUSH_CONST:
            stack.append(deepcopy(arg))
        elif op == MAKE_ARRAY:
            stack.append([stack.pop() for _ in range(arg)][::-1])
        elif op == GET_INDEX:
            index, array = stack.pop(), stack.pop()
            stack.append(self._array_element(array, index))
        elif op == SET_INDEX:
            value, index, array = stack.pop(), stack.pop(), stack.pop()
            self._array_element(array, index)
            array[index] = value
        elif op == LOAD:
            if arg not in variables:
                raise RuntimeError_(f"Undefined variable '{arg}' at runtime", instr.source_line)
            stack.append(variables[arg])
        elif op == STORE:
            variables[arg] = stack.pop()
        elif op == ADD:
            b, a = stack.pop(), stack.pop(); stack.append(a + b)
        elif op == SUB:
            b, a = stack.pop(), stack.pop(); stack.append(a - b)
        elif op == MUL:
            b, a = stack.pop(), stack.pop(); stack.append(a * b)
        elif op == DIV:
            b, a = stack.pop(), stack.pop()
            if b == 0:
                raise RuntimeError_("Division by zero", instr.source_line)
            stack.append(a / b if (isinstance(a, float) or isinstance(b, float)) else a // b)
        elif op == NEG:
            stack.append(-stack.pop())
        elif op in (CMP_LT, CMP_GT, CMP_LE, CMP_GE, CMP_EQ, CMP_NEQ):
            b, a = stack.pop(), stack.pop()
            stack.append({CMP_LT: lambda: a < b, CMP_GT: lambda: a > b,
                          CMP_LE: lambda: a <= b, CMP_GE: lambda: a >= b,
                          CMP_EQ: lambda: a == b, CMP_NEQ: lambda: a != b}[op]())
        elif op == JUMP:
            next_ip = arg
        elif op == JUMP_IF_FALSE:
            cond = stack.pop()
            if not cond:
                next_ip = arg
        elif op == PRINT:
            self.output.append(self._format(stack.pop()))
        elif op == CALL:
            fname, nargs = arg
            if fname not in self.chunks:
                raise RuntimeError_(f"Call to undefined function '{fname}'", instr.source_line)
            if len(self.frames) >= MAX_CALL_DEPTH + 1:
                raise RuntimeError_("Maximum call depth exceeded (infinite recursion?)", instr.source_line)
            args = [stack.pop() for _ in range(nargs)][::-1]
            params = self.param_map.get(fname, [])
            frame["ip"] = next_ip
            self.frames.append({"id": self._next_frame_id, "chunk": fname, "ip": 0,
                                "vars": dict(zip(params, args)), "stack": []})
            self._next_frame_id += 1
            return
        elif op == RETURN:
            value = stack.pop() if stack else None
            if len(self.frames) == 1:
                self.status = "halted"
            else:
                self.frames.pop()
                self.frames[-1]["stack"].append(value)
            return
        elif op == POP:
            stack.pop()
        elif op == HALT:
            self.status = "halted"
        else:
            raise RuntimeError_(f"Unknown opcode '{op}'", instr.source_line)
        frame["ip"] = next_ip

    def _snapshot(self):
        return {"frames": deepcopy(self.frames), "output": list(self.output), "status": self.status,
                "error": deepcopy(self.error), "steps": self.steps, "next_frame_id": self._next_frame_id}

    def _restore(self, snapshot):
        self.frames = deepcopy(snapshot["frames"])
        self.output = list(snapshot["output"])
        self.status = snapshot["status"]
        self.error = deepcopy(snapshot["error"])
        self.steps = snapshot["steps"]
        self._next_frame_id = snapshot["next_frame_id"]

    def _state_from_snapshot(self, snapshot, step):
        saved = self._snapshot()
        cursor = self._cursor
        self._restore(snapshot)
        result = self.state()
        result["step"] = step
        self._restore(saved)
        self._cursor = cursor
        return result

    def _frame_views(self):
        return [{"id": f["id"], "function": f["chunk"], "instruction_pointer": f["ip"],
                 "variables": self._json_value(f["vars"]), "stack": self._json_value(f["stack"])}
                for f in self.frames]

    @staticmethod
    def _json_value(value):
        if isinstance(value, list):
            return [VirtualMachine._json_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): VirtualMachine._json_value(v) for k, v in value.items()}
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _event_kind(op):
        if op in (PUSH_CONST, LOAD): return "push"
        if op == STORE: return "store"
        if op in (ADD, SUB, MUL, DIV, NEG): return "arithmetic"
        if op in (CMP_LT, CMP_GT, CMP_LE, CMP_GE, CMP_EQ, CMP_NEQ, JUMP_IF_FALSE): return "branch"
        if op == JUMP: return "jump"
        if op == CALL: return "call"
        if op == RETURN: return "return"
        if op == PRINT: return "output"
        if op == HALT: return "halt"
        return "instruction"

    @staticmethod
    def _event_detail(instr, frame, ip_before, stack_before):
        op = instr.op
        if op == PUSH_CONST: return f"Pushed {VirtualMachine._format(instr.arg)}"
        if op == LOAD:
            return f"Read {instr.arg} = {VirtualMachine._format(frame['stack'][-1])}"
        if op == STORE:
            return f"Wrote {instr.arg} = {VirtualMachine._format(frame['vars'].get(instr.arg))}"
        if op in (ADD, SUB, MUL, DIV, NEG):
            return f"Stack result {VirtualMachine._format(frame['stack'][-1])}"
        if op in (CMP_LT, CMP_GT, CMP_LE, CMP_GE, CMP_EQ, CMP_NEQ):
            return f"Condition evaluated to {VirtualMachine._format(frame['stack'][-1])}"
        if op == JUMP: return f"Jump to address {instr.arg}"
        if op == JUMP_IF_FALSE:
            value = bool(stack_before[-1]) if stack_before else False
            target = instr.arg if not value else ip_before + 1
            return f"Condition was {str(value).lower()}; {'jumped' if not value else 'continued'} to {target}"
        if op == CALL: return f"Called {instr.arg[0]} · {len(frame['vars'])} local(s)"
        if op == RETURN: return f"Returned {VirtualMachine._format(stack_before[-1]) if stack_before else 'null'}"
        if op == PRINT: return f"Output: {VirtualMachine._format(stack_before[-1]) if stack_before else ''}"
        if op == SET_INDEX: return "Mutated array element"
        if op == HALT: return "Program halted"
        return instr.to_line()

    @staticmethod
    def _array_element(array, index):
        if not isinstance(array, list):
            raise RuntimeError_("Cannot index a non-array value")
        if isinstance(index, bool) or not isinstance(index, int):
            raise RuntimeError_("Array index must be an integer")
        if index < 0:
            raise RuntimeError_("Array index cannot be negative")
        if index >= len(array):
            raise RuntimeError_(f"Array index {index} out of bounds for length {len(array)}")
        return array[index]

    @staticmethod
    def _format(val):
        if isinstance(val, bool): return "true" if val else "false"
        if val is None: return "null"
        return str(val)
