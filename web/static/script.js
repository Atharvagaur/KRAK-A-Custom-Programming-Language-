const STAGES = ["lexer", "parser", "semantic", "ir", "optimizer", "bytecode", "vm"];
const $ = (id) => document.getElementById(id);
const sourceEl = $("source"), compileBtn = $("compile-btn"), statusEl = $("status");
const outputEl = $("output"), exampleSelect = $("example-select");
const EXAMPLES = window.KRAK_EXAMPLES || {};
let sessionId = null, machineState = null, viewState = null, playTimer = null;
let playing = false, selectedInstruction = null, sourceLine = null, olderEvents = [], runGeneration = 0;
let compileResult = null, cfgVersion = "before", cfgSelectedBlock = null, cfgViewBox = null;

exampleSelect.addEventListener("change", () => {
  const name = exampleSelect.value;
  if (name && EXAMPLES[name]) sourceEl.value = EXAMPLES[name];
});
document.querySelectorAll(".tab").forEach(tab => tab.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  tab.classList.add("active"); $("panel-" + tab.dataset.tab).classList.add("active");
}));

$("compile-btn").addEventListener("click", compile);
$("run-btn").addEventListener("click", runAll);
$("play-btn").addEventListener("click", play);
$("pause-btn").addEventListener("click", pause);
$("step-btn").addEventListener("click", stepForward);
$("step-back-btn").addEventListener("click", stepBackward);
$("reset-btn").addEventListener("click", resetRun);
$("stop-btn").addEventListener("click", stopRun);
$("cfg-original-btn").addEventListener("click", () => setCfgVersion("before"));
$("cfg-optimized-btn").addEventListener("click", () => setCfgVersion("after"));
$("cfg-fit-btn").addEventListener("click", fitCfg);
sourceEl.addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); compile(); } });
sourceEl.addEventListener("input", updateGutter);
sourceEl.addEventListener("scroll", () => { $("source-gutter").scrollTop = sourceEl.scrollTop; });

async function api(path, method = "POST") {
  const response = await fetch(path, {method, headers: {"Content-Type": "application/json"}});
  const body = await response.json();
  if (!response.ok) throw Object.assign(new Error(body.error || "Request failed"), {body});
  return body;
}

async function compile() {
  runGeneration++;
  pause();
  if (sessionId) await fetch(`/api/debug/${sessionId}`, {method: "DELETE"}).catch(() => {});
  sessionId = null; machineState = viewState = null; selectedInstruction = null; olderEvents = [];
  statusEl.textContent = "compiling…"; statusEl.className = "status"; $("exec-status").textContent = "compiling";
  compileBtn.disabled = true; resetRail(); renderState(null); renderCompile({}); setButtons();
  try {
    const response = await fetch("/api/debug/start", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({source: sourceEl.value, optimize: $("optimize-toggle").checked, control_flow: $("cfg-opt-toggle").checked})});
    const data = await response.json();
    if (!response.ok) {
      const result = data.compile || {errors: data.errors || [], stage_reached: "lexer"};
      renderCompile(result); showCompileErrors(data.errors || result.errors || []); animateRail(result.stage_reached, true);
      $("exec-status").textContent = "compile error"; return;
    }
    sessionId = data.session_id; machineState = viewState = data.state;
    renderCompile(data.compile); animateRail("bytecode", false);
    statusEl.textContent = "compiled · ready"; statusEl.className = "status ok";
    $("exec-status").textContent = "ready to execute"; updateDisplayedState(); setButtons();
  } catch (error) {
    statusEl.textContent = error.message || "network error"; statusEl.className = "status err";
    $("exec-status").textContent = "compile failed";
  } finally { compileBtn.disabled = false; }
}

function renderCompile(result) {
  compileResult = result; cfgSelectedBlock = null; cfgViewBox = null;
  renderTokens(result.tokens || []); renderAst(result.ast); renderSymbols(result.symbols || []);
  renderIr("ir-before-view", result.ir_before || []); renderIr("ir-after-view", result.ir_after || []);
  renderNotes(result.optimizer_notes || [], result.optimizer_remarks || [], result.instruction_counts || {}); renderBytecode(result.bytecode || {}); renderCfg();
  clearRuntimeError();
}

function renderTokens(tokens) {
  $("tokens-table").querySelector("tbody").innerHTML = tokens.filter(t => t.type !== "EOF")
    .map(t => `<tr><td>${escapeHtml(t.type)}</td><td>${escapeHtml(String(t.value))}</td><td>${t.line}</td><td>${t.column}</td></tr>`).join("");
}
function renderAst(ast) { $("ast-view").textContent = ast ? JSON.stringify(ast, null, 2) : ""; }
function renderSymbols(symbols) {
  $("symbols-table").querySelector("tbody").innerHTML = symbols.length
    ? symbols.map(s => `<tr><td>${escapeHtml(s.name)}</td><td>${escapeHtml(s.type)}</td></tr>`).join("")
    : `<tr><td colspan="2" class="empty-hint">no variables declared</td></tr>`;
}
function renderIr(id, instrs) { $(id).textContent = instrs.map(i => i.text).join("\n"); }
function renderNotes(notes, remarks = [], counts = {}) {
  const metrics = Object.keys(counts).length ? `<div class="note metrics">IR ${counts.ir_before} → ${counts.ir_after} · blocks ${counts.blocks_before} → ${counts.blocks_after} · bytecode ${counts.bytecode_before} → ${counts.bytecode_after}</div>` : "";
  const explanations = remarks.map(r => `<div class="note"><b>${escapeHtml(r.pass)}</b> · ${escapeHtml(r.instruction)} → ${escapeHtml(r.result)}<small>${escapeHtml(r.reason)}</small></div>`).join("");
  $("optimizer-notes").innerHTML = metrics + explanations + notes.map(n => `<div class="note">${escapeHtml(n)}</div>`).join("");
}

function renderBytecode(chunks) {
  const el = $("bytecode-view");
  el.innerHTML = Object.keys(chunks).map(name => {
    const rows = chunks[name].map((instr, idx) => `<tr class="instruction-row" data-chunk="${escapeHtml(name)}" data-ip="${idx}"><td class="addr">${idx}</td><td class="op">${escapeHtml(instr.op)}</td><td>${escapeHtml(formatArg(instr.arg))}</td></tr>`).join("");
    return `<div class="chunk"><div class="chunk-title">${escapeHtml(name)}</div><table><thead><tr><th>addr</th><th>opcode</th><th>operand</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }).join("") || `<div class="empty-hint">compile a program to generate bytecode</div>`;
  el.querySelectorAll(".instruction-row").forEach(row => row.addEventListener("click", () => {
    selectedInstruction = {chunk: row.dataset.chunk, index: Number(row.dataset.ip)};
    renderInstructionSelection();
  }));
}
function formatArg(value) { return value === null || value === undefined ? "" : Array.isArray(value) ? JSON.stringify(value) : typeof value === "object" ? JSON.stringify(value) : String(value); }

async function stepForward() {
  if (!sessionId || playing) return;
  const generation = runGeneration;
  try { const result = await api(`/api/debug/${sessionId}/step`); if (generation !== runGeneration) return; machineState = result; viewState = machineState; updateDisplayedState(); setButtons(); }
  catch (e) { showTransportError(e); }
}
async function stepBackward() {
  if (!sessionId || playing) return;
  const generation = runGeneration;
  try { const result = await api(`/api/debug/${sessionId}/back`); if (generation !== runGeneration) return; machineState = result; viewState = machineState; updateDisplayedState(); setButtons(); }
  catch (e) { showTransportError(e); }
}
async function runAll() {
  if (!sessionId || playing) return;
  const generation = runGeneration;
  statusEl.textContent = "running to completion…"; statusEl.className = "status";
  try { const result = await api(`/api/debug/${sessionId}/run`); if (generation !== runGeneration) return; machineState = result; viewState = machineState; updateDisplayedState(); setButtons(); }
  catch (e) { showTransportError(e); }
}
async function play() {
  if (!sessionId || playing) return;
  playing = true; const generation = runGeneration; setButtons();
  const tick = async () => {
    if (!playing || !sessionId || generation !== runGeneration) return;
    try {
      const result = await api(`/api/debug/${sessionId}/step`);
      if (generation !== runGeneration) return;
      machineState = result; viewState = machineState;
      updateDisplayedState(); setButtons();
      if (playing && !["halted", "error"].includes(machineState.status)) {
        playTimer = setTimeout(tick, Number($("speed-select").value));
      } else { playing = false; setButtons(); }
    } catch (e) { playing = false; showTransportError(e); setButtons(); }
  };
  await tick();
}
function pause() { playing = false; clearTimeout(playTimer); playTimer = null; setButtons(); }
async function resetRun() {
  if (!sessionId) return;
  pause(); runGeneration++;
  try { machineState = await api(`/api/debug/${sessionId}/reset`); viewState = machineState; selectedInstruction = null; olderEvents = []; updateDisplayedState(); setButtons(); }
  catch (e) { showTransportError(e); }
}
async function stopRun() {
  runGeneration++; pause();
  if (sessionId) await fetch(`/api/debug/${sessionId}`, {method: "DELETE"}).catch(() => {});
  sessionId = null; machineState = viewState = null; renderState(null); setButtons();
  clearRuntimeError();
  statusEl.textContent = "debug session stopped"; statusEl.className = "status"; $("exec-status").textContent = "stopped";
}

async function inspectStep(step) {
  if (!sessionId) return;
  try { viewState = await api(`/api/debug/${sessionId}/inspect/${step}`, "GET"); updateDisplayedState(); }
  catch (e) { showTransportError(e); }
}
function updateDisplayedState() {
  renderState(viewState);
  renderCfg();
  setVMStage(viewState);
  if (viewState && viewState !== machineState) $("exec-status").textContent = `viewing history · step ${viewState.step}`;
  else if (machineState) $("exec-status").textContent = machineState.status;
}

function setVMStage(state) {
  if (!state || state.status === "ready") return;
  const node = document.querySelector('.rail-node[data-stage="vm"]');
  if (!node) return;
  node.classList.remove("active", "reached", "errored");
  node.classList.add(state.status === "error" ? "errored" : state.status === "halted" ? "reached" : "active");
}

function renderState(state) {
  if (!state) {
    const vmNode = document.querySelector('.rail-node[data-stage="vm"]');
    if (vmNode) vmNode.classList.remove("active", "reached", "errored");
    $("step-badge").textContent = "step 0"; $("ip-view").textContent = "—";
    $("current-op").textContent = "waiting for compile"; $("stack-view").innerHTML = `<div class="empty-runtime">Compile a program to begin.</div>`;
    $("variables-view").innerHTML = `<div class="empty-runtime">No active variables.</div>`; $("frames-view").innerHTML = `<div class="empty-runtime">No calls yet.</div>`;
    $("history-view").innerHTML = `<div class="empty-runtime">Instruction events will appear here.</div>`; outputEl.textContent = "";
    $("history-count").textContent = "0 events"; $("output-count").textContent = "0 lines"; $("stack-depth").textContent = "0 values";
    $("vm-dynamic-count").textContent = "0";
    $("frame-label").textContent = "main"; $("frame-count").textContent = "0"; sourceLine = null; updateGutter(); return;
  }
  $("step-badge").textContent = `step ${state.step}`;
  $("vm-dynamic-count").textContent = String(Math.max(0, state.step || 0));
  $("ip-view").textContent = state.instruction_pointer ? `${state.instruction_pointer.chunk} · ${state.instruction_pointer.index}` : "—";
  const current = state.current_instruction;
  $("current-op").textContent = current ? `${current.op}${current.arg == null ? "" : "  " + formatArg(current.arg)}` : state.status === "error" ? "runtime error" : "program complete";
  sourceLine = current?.line || state.error?.line || null; updateGutter();
  const stack = state.stack || [];
  $("stack-depth").textContent = `${stack.length} ${stack.length === 1 ? "value" : "values"}`;
  $("stack-view").innerHTML = stack.length ? stack.map((v, i) => `<div class="stack-item ${i === stack.length - 1 ? "top" : ""}"><span class="stack-index">${i}</span><span class="stack-value">${escapeHtml(formatArg(v))}</span>${i === stack.length - 1 ? `<span class="top-tag">TOP</span>` : ""}</div>`).join("") : `<div class="empty-runtime">stack is empty</div>`;
  const frames = state.frames || [], active = frames[frames.length - 1];
  $("variables-view").innerHTML = active && Object.keys(active.variables).length ? Object.entries(active.variables).map(([name, val]) => `<div class="variable-row"><span>${escapeHtml(name)}</span><strong>${escapeHtml(formatArg(val))}</strong></div>`).join("") : `<div class="empty-runtime">No active variables.</div>`;
  $("frame-label").textContent = active?.function || "main"; $("frame-count").textContent = `${frames.length} active`;
  $("frames-view").innerHTML = frames.length ? [...frames].reverse().map((f, i) => `<div class="frame-card ${i === 0 ? "active" : ""}"><span class="frame-depth">${frames.length - i}</span><strong>${escapeHtml(f.function)}</strong><small>${Object.keys(f.variables).length} locals · IP ${f.instruction_pointer}</small><div class="frame-locals">${Object.entries(f.variables).map(([name, value]) => `<span>${escapeHtml(name)} <b>${escapeHtml(formatArg(value))}</b></span>`).join("") || "<span>no locals</span>"}</div></div>`).join("") : `<div class="empty-runtime">No calls yet.</div>`;
  renderHistory(state); renderOutput(state); renderBytecodeProgress(state); renderInstructionSelection();
  if (state.error) showRuntimeError(state.error); else clearRuntimeError();
  statusEl.textContent = state.error ? `runtime error at step ${state.step}` : state.status;
  statusEl.className = state.error ? "status err" : state.status === "halted" ? "status ok" : "status";
}

function setCfgVersion(version) {
  cfgVersion = version; cfgSelectedBlock = null;
  $("cfg-original-btn").classList.toggle("selected", version === "before");
  $("cfg-optimized-btn").classList.toggle("selected", version === "after");
  cfgViewBox = null; renderCfg();
}
function fitCfg() { cfgViewBox = null; renderCfg(); }
function renderCfg() {
  const svg = $("cfg-svg"), graph = compileResult?.[`cfg_${cfgVersion}`];
  if (!graph || !graph.blocks?.length) {
    svg.innerHTML = ""; $("cfg-details").textContent = "No basic blocks in this representation."; return;
  }
  const optimized = cfgVersion === "after";
  const byFunction = new Map();
  graph.blocks.forEach(block => { if (!byFunction.has(block.function)) byFunction.set(block.function, []); byFunction.get(block.function).push(block); });
  const W = 205, H = 118, GX = 52, GY = 58, LABEL = 32;
  const positions = new Map(); let maxX = 800;
  [...byFunction.entries()].forEach(([fn, blocks], row) => blocks.forEach((block, col) => {
    const x = 24 + col * (W + GX), y = LABEL + row * (H + GY);
    positions.set(block.id, {x, y, block, row, col}); maxX = Math.max(maxX, x + W + 28);
  }));
  const maxY = LABEL + byFunction.size * (H + GY) + 20;
  const executed = new Set(), takenEdges = new Set(); let activeBlock = null, activeIr = null;
  const addressMap = compileResult.bytecode_to_block || {};
  if (optimized && viewState) {
    for (const event of (viewState.events || [])) {
      const blockId = addressMap[event.chunk]?.[event.ip];
      if (blockId) executed.add(blockId);
      if (["JUMP", "JUMP_IF_FALSE"].includes(event.instruction?.op) && event.ip_after?.chunk === event.chunk) {
        const target = addressMap[event.chunk]?.[event.ip_after.index];
        if (blockId && target && target !== blockId) takenEdges.add(`${blockId}>${target}`);
      }
    }
    const ip = viewState.instruction_pointer;
    if (ip && !["ready", "halted", "error"].includes(viewState.status)) {
      activeBlock = addressMap[ip.chunk]?.[ip.index] || null;
      activeIr = viewState.current_instruction?.ir_index ?? null;
    }
  }
  const edges = graph.blocks.flatMap(block => block.successors.map(edge => ({from:block.id, ...edge})));
  const edgeMarkup = edges.map(edge => {
    const a = positions.get(edge.from), b = positions.get(edge.target); if (!a || !b) return "";
    const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
    const bend = Math.max(34, Math.abs(x2 - x1) * .42);
    const path = a.row === b.row && b.col < a.col
      ? `M ${a.x + W/2} ${a.y} C ${a.x + W/2} ${a.y-44}, ${b.x + W/2} ${b.y-44}, ${b.x + W/2} ${b.y}`
      : `M ${x1} ${y1} C ${x1+bend} ${y1}, ${x2-bend} ${y2}, ${x2} ${y2}`;
    const key = `${edge.from}>${edge.target}`, visited = optimized && takenEdges.has(key);
    const kind = edge.kind === "true" ? "true-edge" : edge.kind === "false" ? "false-edge" : "normal-edge";
    const label = edge.kind === "true" ? "true" : edge.kind === "false" ? "false" : edge.kind === "jump" ? "jump" : "";
    return `<g class="cfg-edge ${kind} ${visited ? "taken" : ""}"><path d="${path}" marker-end="url(#cfg-arrow)"/><title>${escapeHtml(edge.from)} → ${escapeHtml(edge.target)}${label ? ` (${label})` : ""}</title>${label ? `<text x="${(x1+x2)/2}" y="${(y1+y2)/2-8}">${label}</text>` : ""}</g>`;
  }).join("");
  const nodes = [...positions.values()].map(({x,y,block}) => {
    const active = block.id === activeBlock, visited = executed.has(block.id), selected = block.id === cfgSelectedBlock;
    const instructionLines = block.instructions.slice(0, 3).map(row => {
      const current = active && row.index === activeIr;
      return `<text class="cfg-instr ${current ? "current" : ""}" x="${x+12}" y="${y+56+17*block.instructions.indexOf(row)}">${escapeHtml(row.text.length > 27 ? row.text.slice(0,24)+"…" : row.text)}</text>`;
    }).join("");
    const extra = block.instructions.length > 3 ? `<text class="cfg-more" x="${x+12}" y="${y+108}">+${block.instructions.length-3} instructions</text>` : "";
    return `<g class="cfg-node ${block.entry ? "entry" : ""} ${block.exit ? "exit" : ""} ${active ? "active" : ""} ${visited ? "visited" : ""} ${selected ? "selected" : ""}" data-block="${escapeHtml(block.id)}" tabindex="0"><rect x="${x}" y="${y}" width="${W}" height="${H}" rx="9"/><text class="cfg-title" x="${x+12}" y="${y+21}">${escapeHtml(block.id)}${block.entry ? " · ENTRY" : ""}${block.exit ? " · EXIT" : ""}</text><text class="cfg-meta" x="${x+12}" y="${y+39}">in ${block.predecessors.length} · out ${block.successors.length}</text>${instructionLines}${extra}</g>`;
  }).join("");
  svg.setAttribute("viewBox", cfgViewBox || `0 0 ${maxX} ${maxY}`);
  svg.setAttribute("width", maxX); svg.setAttribute("height", maxY);
  svg.innerHTML = `<defs><marker id="cfg-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z"/></marker></defs><text class="cfg-function" x="12" y="22">${[...byFunction.keys()].map(escapeHtml).join("  ·  ")}</text>${edgeMarkup}${nodes}`;
  svg.querySelectorAll(".cfg-node").forEach(node => {
    const select = () => { cfgSelectedBlock = node.dataset.block; renderCfg(); };
    node.addEventListener("click", select); node.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(); } });
  });
  const selected = positions.get(cfgSelectedBlock);
  if (selected) {
    const b = selected.block;
    $("cfg-details").innerHTML = `<strong>${escapeHtml(b.id)}</strong> · predecessors: ${b.predecessors.map(escapeHtml).join(", ") || "none"} · successors: ${b.successors.map(e => `${escapeHtml(e.kind)} → ${escapeHtml(e.target)}`).join(", ") || "exit"}<br>${b.instructions.map(i => `${i.index}: ${escapeHtml(i.text)}`).join("<br>")}`;
  } else {
    $("cfg-details").textContent = optimized ? "Optimized CFG. Select a block for its instructions and adjacent blocks." : "Original CFG. Execution highlighting follows the optimized bytecode, so it is shown on the optimized view.";
  }
  if (!cfgPanBound) bindCfgPan(svg);
}
let cfgPanBound = false;
function bindCfgPan(svg) {
  cfgPanBound = true; let drag = null;
  const parseBox = () => (svg.getAttribute("viewBox") || "0 0 800 600").split(/\s+/).map(Number);
  svg.addEventListener("pointerdown", e => { if (e.target.closest(".cfg-node")) return; drag = {x:e.clientX,y:e.clientY,box:parseBox()}; svg.setPointerCapture(e.pointerId); });
  svg.addEventListener("pointermove", e => { if (!drag) return; const [x,y,w,h]=drag.box, scale=w/svg.clientWidth; cfgViewBox=`${x-(e.clientX-drag.x)*scale} ${y-(e.clientY-drag.y)*scale} ${w} ${h}`; svg.setAttribute("viewBox",cfgViewBox); });
  svg.addEventListener("pointerup", () => { drag=null; });
  svg.addEventListener("wheel", e => { e.preventDefault(); const [x,y,w,h]=parseBox(), factor=e.deltaY>0?1.12:.89, nw=w*factor, nh=h*factor; cfgViewBox=`${x+(w-nw)/2} ${y+(h-nh)/2} ${nw} ${nh}`; svg.setAttribute("viewBox",cfgViewBox); }, {passive:false});
}

function renderHistory(state) {
  const events = [...new Map([...olderEvents, ...(state.events || [])].map(event => [event.step, event])).values()]
    .filter(event => event.step <= state.step).sort((a, b) => a.step - b.step);
  $("history-count").textContent = `${Math.max(0, state.history_size - 1)} events`;
  const firstStep = events.length ? events[0].step : 1;
  const earlier = firstStep > 1 ? `<button id="load-earlier" class="load-earlier">load earlier events · before step ${firstStep}</button>` : "";
  $("history-view").innerHTML = earlier + (events.length ? events.map(e => {
    const step = e.step;
    return `<button class="event-row ${step === state.step ? "selected" : ""} ${e.kind === "error" ? "event-error" : ""}" data-step="${step}"><span class="event-step">${step.toString().padStart(3, "0")}</span><span class="event-kind">${escapeHtml(e.kind)}</span><span class="event-instr">${escapeHtml(e.chunk)}:${e.ip} ${escapeHtml(e.instruction.op)}</span><small>${escapeHtml(e.detail)}</small></button>`;
  }).join("") : `<div class="empty-runtime">Instruction events will appear here.</div>`);
  const earlierButton = $("load-earlier");
  if (earlierButton) earlierButton.addEventListener("click", () => loadEarlierEvents(firstStep));
  $("history-view").querySelectorAll(".event-row").forEach(row => row.addEventListener("click", () => inspectStep(Number(row.dataset.step))));
}
async function loadEarlierEvents(before) {
  if (!sessionId) return;
  const button = $("load-earlier"); if (button) button.disabled = true;
  try {
    const page = await api(`/api/debug/${sessionId}/events?before=${before}&limit=100`, "GET");
    olderEvents = [...new Map([...page.events, ...olderEvents].map(event => [event.step, event])).values()].sort((a, b) => a.step - b.step);
    renderHistory(viewState || machineState);
  } catch (e) { showTransportError(e); }
}
function renderOutput(state) {
  const lines = state.output || [];
  outputEl.textContent = lines.length ? lines.join("\n") : "(no output yet)";
  $("output-count").textContent = `${lines.length} ${lines.length === 1 ? "line" : "lines"}`;
  outputEl.scrollTop = outputEl.scrollHeight;
}
function renderBytecodeProgress(state) {
  const executed = new Set((machineState?.events || []).map(e => `${e.chunk}:${e.ip}`));
  const ip = state.instruction_pointer;
  document.querySelectorAll(".instruction-row").forEach(row => {
    const key = `${row.dataset.chunk}:${row.dataset.ip}`;
    row.classList.toggle("executed", executed.has(key));
    row.classList.toggle("current", !!ip && row.dataset.chunk === ip.chunk && Number(row.dataset.ip) === ip.index && !["halted", "error"].includes(state.status));
    row.classList.toggle("inspected", selectedInstruction?.chunk === row.dataset.chunk && selectedInstruction?.index === Number(row.dataset.ip));
  });
}
function renderInstructionSelection() {
  const old = $("instruction-inspector");
  if (old) old.remove();
  if (!selectedInstruction) return;
  const row = document.querySelector(`.instruction-row[data-chunk="${CSS.escape(selectedInstruction.chunk)}"][data-ip="${selectedInstruction.index}"]`);
  if (!row) return;
  const info = document.createElement("div"); info.id = "instruction-inspector"; info.className = "instruction-inspector";
  info.textContent = `Inspection only · ${selectedInstruction.chunk} · address ${selectedInstruction.index} · ${row.children[1].textContent} ${row.children[2].textContent}`;
  $("bytecode-view").prepend(info);
}
function showCompileErrors(errors) {
  statusEl.textContent = "compilation failed"; statusEl.className = "status err";
  $("exec-status").textContent = "compile error";
  outputEl.textContent = errors.map(e => `${e.kind}${e.line ? ` · line ${e.line}` : ""}: ${e.message}`).join("\n") || "Compilation failed.";
  $("runtime-error").hidden = true;
}
function showRuntimeError(error) {
  const loc = error.line ? ` · source line ${error.line}` : "";
  $("runtime-error").hidden = false; $("runtime-error").textContent = `${error.kind || "Runtime Error"}${loc}: ${error.message}`;
  $("exec-status").textContent = "runtime error";
}
function clearRuntimeError() { $("runtime-error").hidden = true; $("runtime-error").textContent = ""; }
function showTransportError(error) { statusEl.textContent = error.message || "debug request failed"; statusEl.className = "status err"; }

function setButtons() {
  const active = !!sessionId, terminal = !machineState || ["halted", "error"].includes(machineState.status);
  $("run-btn").disabled = !active || terminal || playing;
  $("play-btn").disabled = !active || terminal || playing;
  $("pause-btn").disabled = !playing;
  $("step-btn").disabled = !active || terminal || playing;
  $("step-back-btn").disabled = !active || !machineState || machineState.step <= 0 || playing;
  $("reset-btn").disabled = !active;
  $("stop-btn").disabled = !active;
}
function updateGutter() {
  const lines = sourceEl.value.split("\n");
  $("source-gutter").innerHTML = lines.map((_, i) => `<span class="source-line ${sourceLine === i + 1 ? "current" : ""}">${i + 1}</span>`).join("");
  $("source-gutter").scrollTop = sourceEl.scrollTop;
}
function resetRail() { document.querySelectorAll(".rail-node").forEach(n => n.classList.remove("reached", "active", "errored")); }
async function animateRail(reachedStage, hadError) {
  resetRail(); const nodes = Object.fromEntries([...document.querySelectorAll(".rail-node")].map(n => [n.dataset.stage, n]));
  const reachedIdx = STAGES.indexOf(reachedStage); if (reachedIdx < 0) return;
  for (let i = 0; i <= reachedIdx; i++) { const node = nodes[STAGES[i]]; if (!node) continue;
    if (i === reachedIdx && hadError) node.classList.add("errored"); else node.classList.add(i === reachedIdx ? "active" : "reached");
    await new Promise(r => setTimeout(r, 55));
  }
}
function escapeHtml(str) { return String(str).replace(/[&<>"']/g, c => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[c])); }

updateGutter(); setButtons();
