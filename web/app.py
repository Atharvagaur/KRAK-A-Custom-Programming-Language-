"""Flask UI/API for the compiler pipeline and its step-capable VM debugger.

Compilation artifacts come from compiler.pipeline. Debug execution sessions
use the same VM dispatcher as ordinary runs and remain isolated per session.
"""

import os
import sys
import time
import uuid
from threading import RLock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from flask import Flask, render_template, request, jsonify
from compiler.pipeline import compile_and_run, compile_source
from phases.phase7_virtual_machine.virtual_machine import VirtualMachine

app = Flask(__name__)
DEBUG_SESSIONS = {}
DEBUG_LOCK = RLock()
MAX_DEBUG_SESSIONS = 4
MAX_SOURCE_BYTES = 20_000

EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "examples")

DEFAULT_SOURCE = """MAKE $x = 10!
MAKE $y = 20!

WHEN ($x < $y) {
    SAY "SEY"!
}
OTHERWISE {
    SAY "ON"!
}
"""


@app.route("/")
def index():
    examples = {}
    if os.path.isdir(EXAMPLES_DIR):
        for fname in sorted(os.listdir(EXAMPLES_DIR)):
            if fname.endswith(".krak"):
                with open(os.path.join(EXAMPLES_DIR, fname), "r", encoding="utf-8") as f:
                    examples[fname] = f.read()
    return render_template("index.html", default_source=DEFAULT_SOURCE, examples=examples)


@app.route("/api/compile", methods=["POST"])
def api_compile():
    data = request.get_json(force=True, silent=True) or {}
    source = data.get("source", "")
    result = compile_and_run(source, optimize=data.get("optimize", True),
                             control_flow=data.get("control_flow", True))
    return jsonify(result)


def _find_debug_session(session_id):
    with DEBUG_LOCK:
        entry = DEBUG_SESSIONS.get(session_id)
        if entry is None:
            return None
        now = time.monotonic()
        if now - entry["touched"] > 1800:
            del DEBUG_SESSIONS[session_id]
            return None
        entry["touched"] = now
        return entry


@app.route("/api/debug/start", methods=["POST"])
def api_debug_start():
    data = request.get_json(force=True, silent=True) or {}
    source = data.get("source", "")
    optimize = data.get("optimize", True)
    control_flow = data.get("control_flow", True)
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        return jsonify({"errors": [{"kind": "Request Error", "message": "Source must be text under 20 KB"}]}), 413
    now = time.monotonic()
    with DEBUG_LOCK:
        for key, entry in list(DEBUG_SESSIONS.items()):
            if now - entry["touched"] > 1800:
                del DEBUG_SESSIONS[key]
        if len(DEBUG_SESSIONS) >= MAX_DEBUG_SESSIONS:
            return jsonify({"errors": [{"kind": "Session Limit", "message": "Four debug sessions are already active; stop one before starting another"}]}), 429
    compiled, chunks, functions = compile_source(source, optimize=optimize, control_flow=control_flow)
    if compiled["errors"]:
        return jsonify({"compile": compiled, "errors": compiled["errors"]}), 400
    session_id = uuid.uuid4().hex
    vm = VirtualMachine(chunks, param_map=functions, tracing=True)
    with DEBUG_LOCK:
        for key, entry in list(DEBUG_SESSIONS.items()):
            if now - entry["touched"] > 1800:
                del DEBUG_SESSIONS[key]
        if len(DEBUG_SESSIONS) >= MAX_DEBUG_SESSIONS:
            return jsonify({"errors": [{"kind": "Session Limit", "message": "Four debug sessions are already active; stop one before starting another"}]}), 429
        DEBUG_SESSIONS[session_id] = {"vm": vm, "compiled": compiled, "touched": now}
    return jsonify({"session_id": session_id, "compile": compiled, "state": vm.state()})


@app.route("/api/debug/<session_id>/step", methods=["POST"])
def api_debug_step(session_id):
    with DEBUG_LOCK:
        entry = _find_debug_session(session_id)
        if entry is None:
            return jsonify({"error": "Debug session expired or stopped"}), 404
        return jsonify(entry["vm"].step())


@app.route("/api/debug/<session_id>/back", methods=["POST"])
def api_debug_back(session_id):
    with DEBUG_LOCK:
        entry = _find_debug_session(session_id)
        if entry is None:
            return jsonify({"error": "Debug session expired or stopped"}), 404
        return jsonify(entry["vm"].back())


@app.route("/api/debug/<session_id>/reset", methods=["POST"])
def api_debug_reset(session_id):
    with DEBUG_LOCK:
        entry = _find_debug_session(session_id)
        if entry is None:
            return jsonify({"error": "Debug session expired or stopped"}), 404
        return jsonify(entry["vm"].reset())


@app.route("/api/debug/<session_id>/run", methods=["POST"])
def api_debug_run(session_id):
    with DEBUG_LOCK:
        entry = _find_debug_session(session_id)
        if entry is None:
            return jsonify({"error": "Debug session expired or stopped"}), 404
        return jsonify(entry["vm"].run_to_end())


@app.route("/api/debug/<session_id>/inspect/<int:step>", methods=["GET"])
def api_debug_inspect(session_id, step):
    try:
        with DEBUG_LOCK:
            entry = _find_debug_session(session_id)
            if entry is None:
                return jsonify({"error": "Debug session expired or stopped"}), 404
            return jsonify(entry["vm"].inspect(step))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404


@app.route("/api/debug/<session_id>/events", methods=["GET"])
def api_debug_events(session_id):
    with DEBUG_LOCK:
        entry = _find_debug_session(session_id)
        if entry is None:
            return jsonify({"error": "Debug session expired or stopped"}), 404
        before = request.args.get("before", type=int)
        limit = min(max(request.args.get("limit", default=100, type=int), 1), 100)
        return jsonify(entry["vm"].events_before(before, limit))


@app.route("/api/debug/<session_id>", methods=["DELETE"])
def api_debug_stop(session_id):
    with DEBUG_LOCK:
        DEBUG_SESSIONS.pop(session_id, None)
    return jsonify({"status": "stopped"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
