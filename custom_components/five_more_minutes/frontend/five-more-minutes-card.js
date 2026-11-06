// The Five More Minutes card: one computer's time at a glance, and the same controls the portal gives a key.
//
// Served by the integration itself (see __init__.py), so installing the integration is all it takes; the card then appears
// under "Add card". It reads the computer's own entities and calls the integration's actions, so it can do exactly what the
// key allows: a key without timer:start shows no start buttons, as it has no Start timer button entity.
//
// Plain custom element, no build step and nothing fetched from elsewhere.

const DOMAIN = "five_more_minutes";
const CARD = "five-more-minutes-card";
const AMBER = "#f2a63b";
const DEFAULT_START = [15, 30, 45, 60, 90];
const DEFAULT_ADD = [5, 15, 30];

const WORDS = {
  en: {
    cardName: "Five More Minutes",
    cardDescription: "A computer's screen time: the countdown, and buttons to start, add, end and cancel.",
    online: "Online",
    offline: "Offline",
    unreachable: "Can't reach Five More Minutes right now. The card comes back by itself.",
    noComputer: "Choose a computer in the card's settings.",
    left: "left",
    until: (t) => `until ${t}`,
    noTime: "No time running",
    startBelow: "Start time below",
    locked: "Locked",
    lockedUntil: (t) => `Locked until ${t}`,
    start: "Start time",
    startLifts: "Start time (lifts the lock)",
    add: "Add time",
    endNow: "End now",
    endHint: "Ends the time and locks the computer, as the rules say",
    cancel: "Cancel timer",
    cancelHint: "Stops the timer without locking",
    message: "Message on the screen (optional)",
    minutes: (m) => (m % 60 === 0 && m >= 60 ? `${m / 60} h` : `${m} min`),
    plus: (m) => `+${m} min`,
    watchOnly: "This key can only watch. Make a key with the timer permissions to get buttons.",
    computer: "Computer",
    title: "Title (optional)",
    startChoices: "Choices for starting time (minutes)",
    addChoices: "Choices for adding time (minutes)",
    showMessage: "Show the message field",
  },
  sv: {
    cardName: "Five More Minutes",
    cardDescription: "En dators skärmtid: nedräkningen och knappar för att starta, lägga till, avsluta och avbryta.",
    online: "Ansluten",
    offline: "Inte ansluten",
    unreachable: "Når inte Five More Minutes just nu. Kortet kommer tillbaka av sig självt.",
    noComputer: "Välj en dator i kortets inställningar.",
    left: "kvar",
    until: (t) => `till ${t}`,
    noTime: "Ingen tid igång",
    startBelow: "Starta tid nedan",
    locked: "Låst",
    lockedUntil: (t) => `Låst till ${t}`,
    start: "Starta tid",
    startLifts: "Starta tid (häver låset)",
    add: "Lägg till tid",
    endNow: "Avsluta nu",
    endHint: "Avslutar tiden och låser datorn, som reglerna säger",
    cancel: "Avbryt timern",
    cancelHint: "Stoppar timern utan att låsa",
    message: "Meddelande på skärmen (valfritt)",
    minutes: (m) => (m % 60 === 0 && m >= 60 ? `${m / 60} tim` : `${m} min`),
    plus: (m) => `+${m} min`,
    watchOnly: "Den här nyckeln kan bara titta. Skapa en nyckel med timerbehörigheterna för att få knappar.",
    computer: "Dator",
    title: "Rubrik (valfri)",
    startChoices: "Val för att starta tid (minuter)",
    addChoices: "Val för att lägga till tid (minuter)",
    showMessage: "Visa meddelandefältet",
  },
};

const words = (hass) => (String(hass?.locale?.language || hass?.language || "en").startsWith("sv") ? WORDS.sv : WORDS.en);

/** The computers this integration has made, as device ids. */
function computers(hass) {
  const seen = new Set();
  for (const entity of Object.values(hass?.entities || {})) {
    if (entity.platform === DOMAIN && entity.device_id) seen.add(entity.device_id);
  }
  return [...seen];
}

/** One computer's entities, by what they are (their translation key). */
function entitiesOf(hass, deviceId) {
  const found = {};
  for (const entity of Object.values(hass?.entities || {})) {
    if (entity.platform === DOMAIN && entity.device_id === deviceId && entity.translation_key) {
      found[entity.translation_key] = entity.entity_id;
    }
  }
  return found;
}

/** Minutes from the editor: numbers or strings, kept between 1 and a day, in order, each once. */
function minutesList(value, fallback) {
  const list = (Array.isArray(value) ? value : [])
    .map((v) => Math.round(Number(v)))
    .filter((v) => Number.isFinite(v) && v >= 1 && v <= 1440);
  return list.length ? [...new Set(list)].sort((a, b) => a - b) : fallback;
}

function instant(text) {
  if (!text || text === "unknown" || text === "unavailable") return null;
  const t = Date.parse(text);
  return Number.isNaN(t) ? null : t;
}

/** 1:05:09, 12:04, 0:42: what a countdown looks like. */
function clock(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const two = (n) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${two(m)}:${two(s)}` : `${m}:${two(s)}`;
}

const STYLE = `
  :host { --fmm-amber: ${AMBER}; }
  [hidden] { display: none !important; }
  ha-card { padding: 16px; display: flex; flex-direction: column; gap: 14px; }
  .head { display: flex; align-items: center; gap: 12px; }
  .mark { width: 36px; height: 36px; flex: none; }
  .names { flex: 1; min-width: 0; }
  .name { font-size: 1.1em; font-weight: 600; color: var(--primary-text-color); white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; }
  .sub { font-size: 0.85em; color: var(--secondary-text-color); }
  .status { display: inline-flex; align-items: center; gap: 6px; font-size: 0.85em; color: var(--secondary-text-color);
    padding: 4px 10px; border-radius: 999px; background: var(--secondary-background-color, rgba(127,127,127,0.12)); }
  .status i { width: 8px; height: 8px; border-radius: 50%; background: var(--disabled-text-color, #9e9e9e); }
  .status.on i { background: var(--success-color, #43a047); }
  .main { display: flex; align-items: center; gap: 20px; }
  .dial { position: relative; width: 132px; height: 132px; flex: none; }
  .dial svg { width: 100%; height: 100%; transform: rotate(-90deg); }
  .track { fill: none; stroke: var(--divider-color, rgba(127,127,127,0.25)); stroke-width: 9; }
  .bar { fill: none; stroke: var(--fmm-amber); stroke-width: 9; stroke-linecap: round; transition: stroke-dashoffset 0.9s linear; }
  .bar.lock { stroke: var(--error-color, #db4437); }
  .bar.none { stroke: transparent; }
  .read { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center;
    text-align: center; padding: 0 14px; }
  .big { font-size: 1.9em; font-weight: 600; font-variant-numeric: tabular-nums; color: var(--primary-text-color); line-height: 1.1; }
  .big.word { font-size: 1.2em; }
  .small { font-size: 0.8em; color: var(--secondary-text-color); margin-top: 2px; }
  .side { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
  .state { font-size: 1em; font-weight: 600; color: var(--primary-text-color); }
  .note { font-size: 0.9em; color: var(--secondary-text-color); overflow-wrap: anywhere; }
  .note q { quotes: "“" "”"; font-style: italic; }
  .group { display: flex; flex-direction: column; gap: 8px; }
  .label { font-size: 0.8em; text-transform: uppercase; letter-spacing: 0.06em; color: var(--secondary-text-color); }
  .chips { display: flex; flex-wrap: wrap; gap: 8px; }
  button { font: inherit; cursor: pointer; border-radius: 999px; padding: 8px 14px; border: 1px solid transparent;
    background: color-mix(in srgb, var(--fmm-amber) 18%, transparent); color: var(--primary-text-color); font-weight: 500; }
  button:hover { background: color-mix(in srgb, var(--fmm-amber) 30%, transparent); }
  button.solid { background: var(--fmm-amber); color: #15171a; }
  button.solid:hover { filter: brightness(1.06); }
  button.quiet { background: transparent; border-color: var(--divider-color, rgba(127,127,127,0.35)); }
  button.quiet:hover { background: var(--secondary-background-color, rgba(127,127,127,0.12)); }
  button.danger { background: transparent; border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
  button.danger:hover { background: color-mix(in srgb, var(--error-color, #db4437) 12%, transparent); }
  button:disabled { opacity: 0.5; cursor: progress; }
  .row { display: flex; flex-wrap: wrap; gap: 8px; }
  input { font: inherit; width: 100%; box-sizing: border-box; padding: 10px 12px; border-radius: 10px;
    border: 1px solid var(--divider-color, rgba(127,127,127,0.35)); background: var(--card-background-color, transparent);
    color: var(--primary-text-color); }
  input:focus { outline: 2px solid color-mix(in srgb, var(--fmm-amber) 60%, transparent); border-color: transparent; }
  .info { font-size: 0.9em; color: var(--secondary-text-color); }
  .error { font-size: 0.9em; color: var(--error-color, #db4437); }
  .error:empty { display: none; }
  @media (max-width: 420px) { .main { flex-direction: column; align-items: stretch; } .dial { margin: 0 auto; } }
`;

// The app icon, drawn: an amber tile, a dark ring open on the left with a faint arc closing it, and a 5.
const MARK = `<svg class="mark" viewBox="0 0 36 36" aria-hidden="true">
  <rect width="36" height="36" rx="8" fill="${AMBER}"/>
  <circle cx="18" cy="18" r="12" fill="none" stroke="#12161a" stroke-opacity="0.22" stroke-width="3.2"/>
  <path d="M10.3 8.8 A12 12 0 1 1 8.5 25.4" fill="none" stroke="#12161a" stroke-width="3.2" stroke-linecap="round"/>
  <text x="18" y="23.6" text-anchor="middle" font-size="15" font-weight="700" fill="#12161a"
    font-family="system-ui, -apple-system, Segoe UI, Roboto, sans-serif">5</text>
</svg>`;

const RADIUS = 52;
const AROUND = 2 * Math.PI * RADIUS;

class FiveMoreMinutesCard extends HTMLElement {
  static getStubConfig(hass) {
    const [first] = computers(hass);
    return first ? { device_id: first } : {};
  }

  static getConfigForm() {
    const choices = [5, 10, 15, 20, 30, 45, 60, 90, 120, 180].map((m) => ({ value: String(m), label: `${m}` }));
    return {
      schema: [
        { name: "device_id", required: true, selector: { device: { integration: DOMAIN } } },
        { name: "title", selector: { text: {} } },
        { name: "start_minutes", selector: { select: { multiple: true, custom_value: true, options: choices } } },
        { name: "add_minutes", selector: { select: { multiple: true, custom_value: true, options: choices } } },
        { name: "show_message", selector: { boolean: {} } },
      ],
      computeLabel: (schema, _data, hass) => {
        const w = words(hass);
        return { device_id: w.computer, title: w.title, start_minutes: w.startChoices, add_minutes: w.addChoices,
          show_message: w.showMessage }[schema.name];
      },
    };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    this._config = { show_message: true, ...config };
    this._shape = null; // rebuild the controls
    this._paint();
  }

  set hass(hass) {
    this._hass = hass;
    this._paint();
  }

  getCardSize() {
    return 5;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }

  connectedCallback() {
    this._timer = setInterval(() => this._tick(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  // --- what the card shows -------------------------------------------------------------------------------------------

  _deviceId() {
    return this._config?.device_id || computers(this._hass)[0];
  }

  _read() {
    const hass = this._hass;
    const id = this._deviceId();
    if (!hass || !id) return null;
    const e = entitiesOf(hass, id);
    const state = (key) => (e[key] ? hass.states[e[key]] : undefined);
    const device = hass.devices?.[id];
    const timer = state("timer_ends");
    const lock = state("lock_ends");
    const connected = state("connected");
    const message = state("timer_message");
    const probe = timer || connected;
    return {
      id,
      name: this._config.title || device?.name_by_user || device?.name || words(hass).cardName,
      available: !!probe && probe.state !== "unavailable",
      online: connected?.state === "on",
      timerEnds: instant(timer?.state),
      timerStarted: instant(timer?.attributes?.started_at),
      lockEnds: instant(lock?.state),
      lockStarted: instant(lock?.attributes?.started_at),
      message: message && !["unknown", "unavailable", ""].includes(message.state) ? message.state : null,
      can: {
        start: !!e.start_timer,
        add: !!e.extend_time,
        end: !!e.end_time,
        cancel: !!e.cancel_timer,
      },
    };
  }

  _mode(r, now) {
    if (!r.available) return "unavailable";
    if (r.timerEnds && r.timerEnds > now) return "running";
    if (r.lockEnds && r.lockEnds > now) return "locked";
    return "idle";
  }

  _paint() {
    if (!this._config || !this._hass) return;
    if (!this.shadowRoot) {
      this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card>
        <div class="head">${MARK}<div class="names"><div class="name"></div><div class="sub"></div></div>
          <span class="status"><i></i><span></span></span></div>
        <div class="body"></div>
        <div class="error" role="alert"></div>
      </ha-card>`;
    }
    this._tick();
  }

  _tick() {
    const root = this.shadowRoot;
    if (!root || !this._hass) return;
    const w = words(this._hass);
    const $ = (s) => root.querySelector(s);
    const r = this._read();

    if (!r) {
      $(".name").textContent = w.cardName;
      $(".sub").textContent = "";
      $(".status").hidden = true;
      this._build("none", null, w);
      return;
    }

    const now = Date.now();
    const mode = this._mode(r, now);
    $(".name").textContent = r.name;
    $(".status").hidden = mode === "unavailable";
    $(".status").classList.toggle("on", r.online);
    $(".status span").textContent = r.online ? w.online : w.offline;
    $(".sub").textContent = "";

    this._build(mode, r, w);
    if (mode === "unavailable") return;

    const time = (t) => new Date(t).toLocaleTimeString(this._hass.locale?.language || undefined, { hour: "2-digit", minute: "2-digit" });
    const bar = $(".bar");
    const big = $(".big");
    const small = $(".small");
    const stateLine = $(".state");
    const note = $(".note");
    let fraction = 0;

    if (mode === "running") {
      const left = r.timerEnds - now;
      const whole = r.timerStarted ? r.timerEnds - r.timerStarted : left;
      fraction = whole > 0 ? left / whole : 1;
      bar.setAttribute("class", "bar");
      big.className = "big";
      big.textContent = clock(left);
      small.textContent = w.left;
      stateLine.textContent = w.until(time(r.timerEnds));
      note.innerHTML = "";
      if (r.message) {
        const q = document.createElement("q");
        q.textContent = r.message; // the parent's words, as text
        note.append(q);
      }
    } else if (mode === "locked") {
      const left = r.lockEnds - now;
      const whole = r.lockStarted ? r.lockEnds - r.lockStarted : left;
      fraction = whole > 0 ? left / whole : 1;
      bar.setAttribute("class", "bar lock");
      big.className = "big";
      big.textContent = clock(left);
      small.textContent = w.locked;
      stateLine.textContent = w.lockedUntil(time(r.lockEnds));
      note.textContent = "";
    } else {
      bar.setAttribute("class", "bar none");
      big.className = "big word";
      big.textContent = "–";
      small.textContent = "";
      stateLine.textContent = w.noTime;
      note.textContent = r.can.start ? w.startBelow : "";
    }
    bar.style.strokeDashoffset = String(AROUND * (1 - Math.max(0, Math.min(1, fraction))));
  }

  // --- the controls --------------------------------------------------------------------------------------------------

  /** Rebuilds the body only when what it should hold changes, so a message being typed is not wiped every second. */
  _build(mode, r, w) {
    const shape = JSON.stringify([mode, r?.can, this._config, w === WORDS.sv]);
    if (shape === this._shape) return;
    this._shape = shape;
    const body = this.shadowRoot.querySelector(".body");
    const typed = body.querySelector("input")?.value || "";
    body.innerHTML = "";

    if (mode === "none") {
      body.innerHTML = `<div class="info"></div>`;
      body.firstChild.textContent = w.noComputer;
      return;
    }
    if (mode === "unavailable") {
      body.innerHTML = `<div class="info"></div>`;
      body.firstChild.textContent = w.unreachable;
      return;
    }

    body.innerHTML = `<div class="main">
        <div class="dial"><svg viewBox="0 0 120 120"><circle class="track" cx="60" cy="60" r="${RADIUS}"/>
          <circle class="bar none" cx="60" cy="60" r="${RADIUS}" stroke-dasharray="${AROUND}" stroke-dashoffset="${AROUND}"/></svg>
          <div class="read"><div class="big"></div><div class="small"></div></div></div>
        <div class="side"><div class="state"></div><div class="note"></div></div>
      </div>
      <div class="controls group"></div>`;
    const controls = body.querySelector(".controls");
    const startList = minutesList(this._config.start_minutes, DEFAULT_START);
    const addList = minutesList(this._config.add_minutes, DEFAULT_ADD);
    const can = r.can;

    const group = (label) => {
      const g = document.createElement("div");
      g.className = "group";
      if (label) {
        const l = document.createElement("div");
        l.className = "label";
        l.textContent = label;
        g.append(l);
      }
      const row = document.createElement("div");
      row.className = "chips";
      g.append(row);
      controls.append(g);
      return row;
    };
    const button = (row, text, kind, title, run) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = text;
      if (kind) b.className = kind;
      if (title) b.title = title;
      b.addEventListener("click", () => this._act(run));
      row.append(b);
    };

    if (mode === "running") {
      if (can.add) {
        const row = group(w.add);
        for (const m of addList) button(row, w.plus(m), "", null, () => ["extend_timer", { minutes: m }]);
      }
      if (can.end || can.cancel) {
        const row = group(null);
        if (can.end) button(row, w.endNow, "danger", w.endHint, () => ["end_time", {}]);
        if (can.cancel) button(row, w.cancel, "quiet", w.cancelHint, () => ["cancel_timer", {}]);
      }
    } else if (can.start) {
      if (this._config.show_message !== false) {
        const field = document.createElement("input");
        field.type = "text";
        field.maxLength = 60;
        field.placeholder = w.message;
        field.setAttribute("aria-label", w.message);
        field.value = typed;
        controls.append(field);
      }
      const row = group(mode === "locked" ? w.startLifts : w.start);
      for (const m of startList) {
        button(row, w.minutes(m), m === startList[Math.min(1, startList.length - 1)] ? "solid" : "", null, () => {
          const text = controls.querySelector("input")?.value.trim();
          return ["start_timer", text ? { minutes: m, message: text } : { minutes: m }];
        });
      }
    }

    if (!can.start && !can.add && !can.end && !can.cancel) {
      const info = document.createElement("div");
      info.className = "info";
      info.textContent = w.watchOnly;
      controls.append(info);
    }
  }

  async _act(what) {
    const [service, data] = what();
    const error = this.shadowRoot.querySelector(".error");
    const buttons = [...this.shadowRoot.querySelectorAll("button")];
    error.textContent = "";
    buttons.forEach((b) => (b.disabled = true));
    try {
      await this._hass.callService(DOMAIN, service, { device_id: [this._deviceId()], ...data });
      if (service === "start_timer") {
        const field = this.shadowRoot.querySelector("input");
        if (field) field.value = "";
      }
    } catch (e) {
      error.textContent = e?.message || String(e);
      setTimeout(() => {
        if (error.textContent === (e?.message || String(e))) error.textContent = "";
      }, 8000);
    } finally {
      buttons.forEach((b) => (b.disabled = false));
    }
  }
}

if (!customElements.get(CARD)) {
  customElements.define(CARD, FiveMoreMinutesCard);
  window.customCards = window.customCards || [];
  const w = words({ language: navigator.language });
  window.customCards.push({
    type: CARD,
    name: w.cardName,
    description: w.cardDescription,
    preview: true,
    documentationURL: "https://github.com/Five-More-Minutes-App/fmm-plugin-home-assistant#dashboard-card",
  });
}
