import { drawZebot } from "./zebot-sprite.js";

const $ = (id) => document.getElementById(id);
const WIDGET = new URLSearchParams(location.search).has("widget");
const REDUCED_MOTION = matchMedia("(prefers-reduced-motion: reduce)").matches;
const POLL_MS = 5 * 60 * 1000;
const RETRY_MS = 60 * 1000;
const TYPE_MS = 18;

const QUIPS = {
  feliz: ["GG, sigue así.", "Esa XP huele a level up.", "Modo speedrun: activado.", "Hoy no hay boss que nos gane."],
  normal: ["Aquí, monitoreando tu backlog.", "¿Qué tarea farmeamos hoy?", "Uptime del 100 %, ¿y el tuyo?", "Ping. ¿Sigues ahí?"],
  cansado: ["Batería de motivación al 30 %…", "Llevo rato sin ver un [x].", "Un pendiente cerrado y me recargo."],
  triste: ["¿Te olvidaste de mí… y de tus pendientes?", "Respawneando la esperanza…", "Estoy bien. Bueno, casi."],
  agotado: ["Error 404: motivación not found.", "Kernel panic emocional.", "Necesito un [x]. Urgente."],
  dormido: ["zzz… el servidor no responde.", "zzz… cinco minutos más…"],
};

const state = { mood: "normal", jumpStart: 0, waveUntil: 0, briefingDate: null, sleeping: false };

if (WIDGET) document.body.classList.add("widget");

// --- Animation --------------------------------------------------------------

const ctx = $("pet").getContext("2d");
function frame(t) {
  const fx = {};
  if (state.jumpStart) {
    const p = (t - state.jumpStart) / 450;
    if (p >= 1) state.jumpStart = 0; else fx.jump = p;
  }
  fx.wave = t < state.waveUntil;
  drawZebot(ctx, state.mood, REDUCED_MOTION ? 0 : t, fx);
  requestAnimationFrame(frame);
}
requestAnimationFrame((t) => { state.waveUntil = t + 2500; frame(t); });

function jump() { state.jumpStart = performance.now(); }

// --- Data -------------------------------------------------------------------

async function getJSON(url, timeoutMs = 15000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: ctrl.signal, cache: "no-store" });
    if (!res.ok) {
      const err = new Error(`HTTP ${res.status}`);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

async function refreshAll() {
  try {
    const [pet, tasks, study] = await Promise.all([
      getJSON("/pet"), getJSON("/tasks?limit=5"), getJSON("/study"),
    ]);
    const wasSleeping = state.sleeping;
    state.sleeping = false;
    renderPet(pet);
    renderTasks(tasks);
    renderStudy(study);
    $("updated").textContent = `Actualizado ${new Date().toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" })}`;
    if (wasSleeping || state.briefingDate !== tasks.date) await loadBriefing(false);
    setTimeout(refreshAll, POLL_MS);
  } catch (e) {
    console.warn("[zebot] API no disponible:", e.message);
    goToSleep();
    setTimeout(refreshAll, RETRY_MS);
  }
}

function goToSleep() {
  state.sleeping = true;
  state.mood = "dormido";
  $("mood").textContent = "dormido";
  setBubble("zzz… No encuentro el servidor. Reintento en un minuto.");
}

async function loadBriefing(refresh) {
  const btn = $("refresh");
  btn.disabled = true;
  if (refresh) setBubble("Recalculando el briefing…");
  try {
    const b = await getJSON(`/briefing${refresh ? "?refresh=true" : ""}`, 60000);
    state.briefingDate = b.date;
    renderPet(b.pet);
    typeBriefing(b.text);
    if (refresh) jump();
  } catch (e) {
    if (e.status === 429) quip("Límite de regeneraciones por hoy. Me nerfearon.");
    else if (!state.sleeping) setBubble("No pude generar el briefing. Lo intento más tarde.");
  } finally {
    btn.disabled = false;
  }
}

// --- Rendering --------------------------------------------------------------

function renderPet(p) {
  if (!state.sleeping) state.mood = p.mood;
  $("pet-name").textContent = p.name;
  $("mood").textContent = p.mood;
  $("pet").setAttribute("aria-label", `${p.name}, ${p.mood}`);
  bar("energy", p.energy);
  bar("happiness", p.happiness);
  bar("xp", p.xp % 100, `${p.xp % 100}/100`);
  $("level").textContent = p.level;
  $("streak").textContent = p.streak;
  $("streak-box").classList.toggle("zero", p.streak === 0);
  const badge = $("difficulty");
  const escalated = p.effective_difficulty !== p.difficulty;
  badge.hidden = !escalated;
  badge.textContent = escalated ? `modo ${p.effective_difficulty}` : "";
  badge.className = `badge ${p.effective_difficulty}`;
}

function bar(name, value, label) {
  const fill = $(`${name}-bar`);
  fill.style.width = `${Math.max(0, Math.min(100, value))}%`;
  if (name !== "xp") {
    fill.classList.toggle("critical", value <= 15);
    fill.classList.toggle("low", value > 15 && value < 40);
  }
  $(name).textContent = label ?? `${value}`;
}

function renderTasks(data) {
  $("tasks-count").textContent = `· ${data.open} abiertas${data.overdue ? ` · ${data.overdue} atrasadas` : ""}`;
  const ul = $("tasks");
  ul.replaceChildren();
  if (!data.tasks.length) {
    ul.append(el("li", { className: "muted" }, "Nada pendiente. Sospechoso."));
    return;
  }
  for (const t of data.tasks) {
    const meta = el("span", { className: "meta" }, t.project);
    if (t.overdue) meta.append(" · ", el("span", { className: "overdue" }, "atrasada"));
    ul.append(el("li", {}, el("span", {}, t.text), meta));
  }
}

function renderStudy(data) {
  const box = $("study");
  box.replaceChildren();
  for (const r of data.roadmaps) {
    const card = el("div", { className: "roadmap" });
    const title = el("h3", {}, el("span", {}, r.name));
    if (r.days_left != null) title.append(el("span", { className: "days" }, `${r.days_left} días`));
    card.append(title);
    if (r.current) {
      const c = r.current;
      card.append(el("span", { className: "phase" }, `Fase ${c.number} · ${c.title} (${c.start} → ${c.end})`));
      const ul = el("ul");
      for (const tp of c.topics.slice(0, 5)) {
        const li = el("li", { className: tp.done ? "done" : "" });
        if (tp.kind === "lab" || tp.kind === "entregable") li.append(el("span", { className: "kind" }, tp.kind));
        li.append(tp.text.replace(/^(Lab|Mini-script):\s*/i, ""));
        ul.append(li);
      }
      card.append(ul);
      if (r.expected_progress != null) {
        const actual = r.actual_progress != null ? `${Math.round(r.actual_progress * 100)} %` : "sin checkboxes";
        card.append(el("span", { className: "pace" }, `Avance ${actual} · tiempo de fase ${Math.round(r.expected_progress * 100)} %`));
      }
    } else {
      const next = r.next ? `Siguiente: Fase ${r.next.number} · ${r.next.title} (desde ${r.next.start})` : "Roadmap terminado.";
      card.append(el("span", { className: "phase" }, `Sin fase activa. ${next}`));
    }
    box.append(card);
  }
  if (!data.roadmaps.length) box.append(el("p", { className: "muted" }, "No hay roadmaps activos."));
}

// --- Bubble -----------------------------------------------------------------

let typingTimer = null;

function setBubble(text) {
  stopTyping();
  $("bubble-text").replaceChildren(el("p", {}, text));
}

function stopTyping() {
  clearInterval(typingTimer);
  typingTimer = null;
  $("bubble").classList.remove("typing");
}

/** Build paragraphs and bullet lists from Zebot's plain-text briefing. */
function briefingNodes(text) {
  const nodes = [];
  let list = null;
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (!line) { list = null; continue; }
    if (line.startsWith("- ")) {
      if (!list) { list = el("ul"); nodes.push(list); }
      list.append(el("li", {}, ...inline(line.slice(2))));
    } else {
      list = null;
      nodes.push(el("p", {}, ...inline(line)));
    }
  }
  return nodes;
}

/** `code` spans become <code>; everything else stays plain text (never HTML). */
function inline(text) {
  return text.split(/`([^`]+)`/).map((part, i) => (i % 2 ? el("code", {}, part) : part));
}

function typeBriefing(text) {
  stopTyping();
  const box = $("bubble-text");
  const nodes = briefingNodes(text);
  box.replaceChildren(...nodes);
  if (REDUCED_MOTION) return;

  // Type text node by text node, so inline <code> keeps its formatting.
  const walker = document.createTreeWalker(box, NodeFilter.SHOW_TEXT);
  const targets = [];
  while (walker.nextNode()) targets.push([walker.currentNode, walker.currentNode.data]);
  targets.forEach(([n]) => { n.data = ""; });
  let i = 0, pos = 0;
  $("bubble").classList.add("typing");
  typingTimer = setInterval(() => {
    if (i >= targets.length) { stopTyping(); return; }
    const [node, full] = targets[i];
    pos += 2;
    node.data = full.slice(0, pos);
    if (pos >= full.length) { i++; pos = 0; }
  }, TYPE_MS);
  box.onclick = () => {
    if (!typingTimer) return;
    targets.forEach(([n, full]) => { n.data = full; });
    stopTyping();
  };
}

// --- Interaction ------------------------------------------------------------

let quipTimer = null;
function quip(text) {
  let q = document.querySelector(".quip");
  if (!q) {
    q = el("p", { className: "quip", role: "status" });
    $("pet-btn").after(q);
  }
  q.textContent = text;
  q.hidden = false;
  clearTimeout(quipTimer);
  quipTimer = setTimeout(() => { q.hidden = true; }, 4000);
}

$("pet-btn").addEventListener("click", () => {
  jump();
  if (WIDGET) {
    $("bubble").classList.toggle("collapsed");
    return;
  }
  const list = QUIPS[state.mood] ?? QUIPS.normal;
  quip(list[Math.floor(Math.random() * list.length)]);
});

$("refresh").addEventListener("click", () => loadBriefing(true));

// --- Helpers ----------------------------------------------------------------

function el(tag, props = {}, ...children) {
  const node = Object.assign(document.createElement(tag), props);
  node.append(...children);
  return node;
}

refreshAll();

// Desktop shell (Tauri): the frameless window is dragged by Zebot or its name line.
// Drag starts only after a few pixels of movement, so a plain click still pokes Zebot.
// Explicit startDragging() instead of data-tauri-drag-region: a missing permission
// shows up in the console instead of failing silently.
if (WIDGET && window.__TAURI__) {
  const DRAG_THRESHOLD = 4;
  let press = null;
  for (const handle of [$("pet-btn"), document.querySelector(".mood-line")]) {
    handle.addEventListener("mousedown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault(); // no text selection while dragging
      press = { x: event.screenX, y: event.screenY };
    });
    handle.style.cursor = "move";
    handle.title = "Arrastra para mover a Zebot";
  }
  window.addEventListener("mouseup", () => { press = null; });
  window.addEventListener("mousemove", (event) => {
    if (!press || Math.hypot(event.screenX - press.x, event.screenY - press.y) < DRAG_THRESHOLD) return;
    press = null;
    window.__TAURI__.window.getCurrentWindow().startDragging().catch((err) => console.error("drag:", err));
  });
}
