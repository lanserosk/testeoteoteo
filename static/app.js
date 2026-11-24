"use strict";

// ------------------------------------------------------------ configuración de módulos
const MODULES = {
  algebra: {
    title: "Aritmética y Álgebra",
    ops: [["evaluar", "Evaluar"], ["simplificar", "Simplificar"], ["expandir", "Expandir"],
          ["factorizar", "Factorizar"], ["resolver", "Resolver ecuación"]],
    examples: [
      { label: "Factorizar x³ − 6x² + 11x − 6", op: "factorizar", expr: "x^3 - 6x^2 + 11x - 6" },
      { label: "Resolver x² − 5x + 6 = 0", op: "resolver", expr: "x^2 - 5x + 6 = 0" },
    ],
  },
  trig: {
    title: "Trigonometría",
    ops: [["evaluar", "Evaluar"], ["simplificar", "Simplificar identidad"],
          ["expandir", "Expandir (ángulos compuestos)"], ["resolver", "Resolver ecuación"]],
    examples: [
      { label: "sin²x + cos²x", op: "simplificar", expr: "sin(x)^2 + cos(x)^2" },
      { label: "Resolver 2 sin x − 1 = 0", op: "resolver", expr: "2sin(x) - 1 = 0" },
    ],
  },
  lineal: {
    title: "Álgebra Lineal",
    ops: [["sistema", "Sistema de ecuaciones"], ["determinante", "Determinante"],
          ["inversa", "Inversa"], ["transpuesta", "Transpuesta"]],
    examples: [
      { label: "Sistema 2×2", op: "sistema", expr: "2x + y = 5\nx - y = 1" },
      { label: "Determinante 3×3", op: "determinante", expr: "[[2,1,0],[1,3,1],[0,1,4]]" },
    ],
  },
  diferencial: {
    title: "Cálculo Diferencial",
    ops: [["limite", "Límite"], ["derivada", "Derivada (orden n)"], ["parcial", "Derivada parcial"]],
    examples: [
      { label: "lím sin x / x, x→0", op: "limite", expr: "sin(x)/x", point: "0" },
      { label: "∂²/∂x∂y de x²y + sin(xy)", op: "parcial", expr: "x^2*y + sin(x*y)", vars: "x, y" },
    ],
  },
  integral: {
    title: "Cálculo Integral",
    ops: [["indefinida", "Integral indefinida"], ["definida", "Integral definida"],
          ["multiple", "Integral múltiple (doble / triple)"]],
    examples: [
      { label: "∫₀³ x² dx", op: "definida", expr: "x^2", a: "0", b: "3" },
      { label: "∫₀¹∫₀ˣ xy dy dx", op: "multiple", expr: "x*y", limits: "x, 0, 1\ny, 0, x" },
    ],
  },
};

// Botones de símbolos: [etiqueta, texto a insertar, posición del cursor dentro del texto (opcional)]
const SYMBOLS = [
  ["∫", "integrate("], ["∂", "diff("], ["√", "√("], ["π", "π"], ["∞", "∞"], ["^", "^"], ["a/b", "()/()", 1],
];

const DEFAULTS = { var: "", order: "1", point: "0", dir: "+-", vars: "x, y", a: "0", b: "1", limits: "x, 0, 1\ny, 0, x" };
const FIELD_IDS = Object.keys(DEFAULTS);

// ------------------------------------------------------------ utilidades
const $ = (id) => document.getElementById(id);
let mod = "algebra";
let lastInput = $("expr");
let previewTimer = null;
let seq = 0;

function renderTex(el, latex) {
  katex.render(latex, el, { throwOnError: false, displayMode: true });
}

async function api(path, body) {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({ error: "Respuesta inválida del servidor." }));
  if (!r.ok) throw new Error(j.error || "Error desconocido.");
  return j;
}

function payload() {
  const p = { module: mod, op: $("op").value, expr: $("expr").value };
  FIELD_IDS.forEach((id) => (p[id] = $(id).value));
  return p;
}

// ------------------------------------------------------------ navegación y formulario
function buildNav() {
  const nav = $("nav");
  Object.entries(MODULES).forEach(([key, m]) => {
    const b = document.createElement("button");
    b.textContent = m.title;
    b.dataset.mod = key;
    b.onclick = () => setModule(key);
    nav.appendChild(b);
  });
}

function buildSymbols() {
  SYMBOLS.forEach(([label, text, caret]) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.title = `Insertar ${text}`;
    b.onmousedown = (e) => e.preventDefault(); // conserva el foco del campo
    b.onclick = () => insertAtCursor(text, caret);
    $("symbols").appendChild(b);
  });
}

function insertAtCursor(text, caret) {
  const el = lastInput;
  const s = el.selectionStart, e = el.selectionEnd;
  el.value = el.value.slice(0, s) + text + el.value.slice(e);
  const pos = s + (caret === undefined ? text.length : caret);
  el.focus();
  el.setSelectionRange(pos, pos);
  schedulePreview();
}

function resetFields() {
  FIELD_IDS.forEach((id) => ($(id).value = DEFAULTS[id]));
}

function showFields() {
  const op = $("op").value;
  document.querySelectorAll("[data-for]").forEach((el) => {
    el.classList.toggle("show", el.dataset.for.split(" ").includes(op));
  });
}

function setModule(key) {
  mod = key;
  const m = MODULES[key];
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("active", b.dataset.mod === key));
  $("mod-title").textContent = m.title;
  $("op").innerHTML = m.ops.map(([v, t]) => `<option value="${v}">${t}</option>`).join("");
  const ex = $("examples");
  ex.innerHTML = "";
  m.examples.forEach((e) => {
    const c = document.createElement("button");
    c.className = "chip";
    c.textContent = e.label;
    c.onclick = () => loadExample(e);
    ex.appendChild(c);
  });
  $("expr").value = "";
  resetFields();
  showFields();
  clearOutput();
  schedulePreview();
  $("expr").focus();
}

function loadExample(e) {
  resetFields();
  $("op").value = e.op;
  $("expr").value = e.expr;
  FIELD_IDS.forEach((id) => { if (e[id] !== undefined) $(id).value = e[id]; });
  showFields();
  preview();
  calculate();
}

// ------------------------------------------------------------ vista previa (SymPy en el servidor)
function schedulePreview() {
  clearTimeout(previewTimer);
  previewTimer = setTimeout(preview, 300);
}

async function preview() {
  const box = $("preview");
  const mine = ++seq;
  if (!$("expr").value.trim()) {
    box.innerHTML = '<span class="muted">Escribe una expresión para ver su vista previa…</span>';
    return;
  }
  try {
    const r = await api("/api/preview", payload());
    if (mine !== seq) return;
    renderTex(box, r.problem);
  } catch (err) {
    if (mine !== seq) return;
    box.innerHTML = "";
    const s = document.createElement("span");
    s.className = "err";
    s.textContent = err.message;
    box.appendChild(s);
  }
}

// ------------------------------------------------------------ cálculo y resultado
function clearOutput() {
  $("out").hidden = true;
  $("error").hidden = true;
  $("plot-card").hidden = true;
}

async function calculate() {
  if (!$("expr").value.trim()) {
    showError("Escribe una expresión.");
    return;
  }
  $("go").disabled = true;
  $("go").textContent = "Calculando…";
  try {
    const r = await api("/api/calcular", payload());
    $("error").hidden = true;
    $("out").hidden = false;
    renderTex($("res-problem"), r.problem);
    renderTex($("res-result"), r.result);
    $("approx-wrap").hidden = !r.approx;
    $("res-approx").hidden = true;
    $("approx-btn").textContent = "Ver valor decimal aproximado";
    if (r.approx) renderTex($("res-approx"), r.approx);
    drawPlot(r.plot);
  } catch (err) {
    showError(err.message);
  } finally {
    $("go").disabled = false;
    $("go").textContent = "Calcular";
  }
}

function showError(msg) {
  $("out").hidden = true;
  $("plot-card").hidden = true;
  $("error").hidden = false;
  $("error").textContent = msg;
}

function drawPlot(p) {
  const card = $("plot-card");
  if (!p) { card.hidden = true; return; }
  card.hidden = false;
  const cfg = { responsive: true, displaylogo: false };
  const base = { margin: { l: 50, r: 20, t: 10, b: 45 }, paper_bgcolor: "rgba(0,0,0,0)", legend: { orientation: "h" } };
  if (p.dim === 2) {
    const data = p.traces.map((t) => ({
      x: t.x, y: t.y, name: t.name, type: "scatter", mode: "lines", connectgaps: false,
      ...(t.fill ? { fill: "tozeroy", line: { width: 0 }, fillcolor: "rgba(79,70,229,.25)" } : {}),
    }));
    const layout = { ...base, xaxis: { title: p.vars[0], zeroline: true }, yaxis: { title: "y", zeroline: true } };
    if (p.yrange) layout.yaxis.range = p.yrange;
    Plotly.newPlot("plot", data, layout, cfg);
  } else {
    const escalas = ["Viridis", "Plasma", "Cividis"];
    const data = p.traces.map((t, i) => ({
      x: p.x, y: p.y, z: t.z, name: t.name, type: "surface", showscale: false,
      colorscale: escalas[i % escalas.length], opacity: i ? 0.7 : 1,
    }));
    const layout = { ...base, margin: { l: 0, r: 0, t: 0, b: 0 },
      scene: { xaxis: { title: p.vars[0] }, yaxis: { title: p.vars[1] }, zaxis: { title: "z" } } };
    Plotly.newPlot("plot", data, layout, cfg);
  }
}

// ------------------------------------------------------------ eventos
buildNav();
buildSymbols();

document.addEventListener("focusin", (e) => {
  if (e.target.matches("input[type=text], input:not([type]), textarea")) lastInput = e.target;
});
document.addEventListener("input", (e) => {
  if (e.target.matches("input, textarea")) schedulePreview();
});
$("op").addEventListener("change", () => { showFields(); schedulePreview(); });
$("dir").addEventListener("change", schedulePreview);
$("go").onclick = calculate;
$("expr").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); calculate(); }
});
$("approx-btn").onclick = () => {
  const el = $("res-approx");
  el.hidden = !el.hidden;
  $("approx-btn").textContent = el.hidden ? "Ver valor decimal aproximado" : "Ocultar valor decimal";
};

setModule("algebra");
