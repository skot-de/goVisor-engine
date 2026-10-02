"use client";

/**
 * Telemetrie, Browserseite — Seitenaufruf, Verweildauer, Scrolltiefe, Klickkarte.
 *
 * Gegenstueck zu `telemetrieSenke.ts` (Server) und `0035_telemetrie.sql` (Tabelle). Die
 * bestehende `track()`-Schicht aus Ticket #8 bleibt unveraendert; sie bekommt in
 * `analytics.ts` nur diese Senke dazu.
 *
 * ⚠ KEIN COOKIE. Die Sitzungskennung liegt in `sessionStorage` und stirbt mit dem Tab. Sie
 *   folgt niemandem ueber Tabs, Geraete oder Websites hinweg. Das ist die Grundlage dafuer,
 *   dass diese Messung ohne Zustimmungsbanner auskommt — und ein Banner auf den
 *   SEO-Landingpages wuerde genau das beschaedigen, worum es bei Ticket 17 geht.
 *
 * ⚠ KEIN ELEMENTTEXT. Das Klickziel ist ein Selektor oder ein `data-mess`-Attribut, nie der
 *   Text des Elements. Auf den App-Seiten stehen Vergabedaten; ein Klickziel-Text haette
 *   Lead-Inhalte in die Telemetrie getragen, und das faengt man spaeter nicht mehr ein.
 */

const WEG = "/api/ereignis";
const SCHLUESSEL = "gv_tm_sitzung";

type Rohereignis = Record<string, unknown> & { art: string };

/* ──────────────────────────────────────────────────────── Darf gemessen werden? */

/**
 * ⚠ „Do Not Track" und „Global Privacy Control" werden GEACHTET, obwohl keine Norm das
 *   erzwingt. Begruendung: diese Messung stuetzt sich auf berechtigtes Interesse statt auf
 *   Einwilligung. Diese Abwaegung traegt besser, wenn ein ausdruecklicher Widerspruch des
 *   Nutzers respektiert wird — und sie traegt schlechter, wenn man ihn uebergeht. Die paar
 *   verlorenen Zeilen sind der Preis.
 */
function darfMessen(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const n = navigator as Navigator & { globalPrivacyControl?: boolean; msDoNotTrack?: string };
    if (n.globalPrivacyControl === true) return false;
    if (n.doNotTrack === "1" || n.msDoNotTrack === "1") return false;
  } catch { /* im Zweifel messen */ }
  return true;
}

function sitzung(): string | null {
  try {
    let s = sessionStorage.getItem(SCHLUESSEL);
    if (!s) {
      s = (crypto.randomUUID?.() ?? String(Math.random()).slice(2)).replace(/-/g, "").slice(0, 32);
      sessionStorage.setItem(SCHLUESSEL, s);
    }
    return s;
  } catch {
    // Privates Fenster, blockierter Speicher: dann eben ohne Sitzung zaehlen.
    return null;
  }
}

/** Pfad ohne Query und Fragment. Der Server schneidet erneut ab (zwei Tore, s. Senke). */
function pfad(): string {
  try { return location.pathname || "/"; } catch { return "/"; }
}

/* ─────────────────────────────────────────────────────────────── Buendelung */

let puffer: Rohereignis[] = [];
let timer: ReturnType<typeof setTimeout> | null = null;

/** Sendet den Puffer. `endgueltig` nutzt `sendBeacon`, das auch beim Verlassen noch geht. */
function senden(endgueltig = false) {
  if (timer) { clearTimeout(timer); timer = null; }
  if (!puffer.length) return;
  const nutzlast = JSON.stringify(puffer.slice(0, 50));
  puffer = [];
  try {
    // ⚠ `sendBeacon` statt `fetch` beim Verlassen. Ein `fetch` wird beim Seitenwechsel
    //   abgebrochen, und genau dann liegt die interessanteste Zahl im Puffer: die
    //   Verweildauer. Ohne Beacon messen wir systematisch kurze Besuche nicht.
    if (endgueltig && navigator.sendBeacon?.(WEG, new Blob([nutzlast], { type: "application/json" }))) return;
    void fetch(WEG, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: nutzlast,
      keepalive: true,
    }).catch(() => { /* fail-open */ });
  } catch { /* fail-open: eine Messung darf nie die Seite stoeren */ }
}

function melde(e: Rohereignis) {
  if (!darfMessen()) return;
  puffer.push({ ...e, sitzung: sitzung(), pfad: e.pfad ?? pfad() });
  if (puffer.length >= 20) { senden(); return; }
  if (!timer) timer = setTimeout(() => senden(), 4000);
}

/** Von `analytics.ts` benutzt: ein benanntes Ereignis aus `EV` mitschreiben. */
export function sendeEreignis(art: string, props: Record<string, unknown> = {}) {
  melde({ art, props });
}

/* ───────────────────────────────────────────── Seitenaufruf, Dauer, Scrolltiefe */

let seit = 0;
let tiefe = 0;
let laufenderPfad: string | null = null;

function tiefeJetzt(): number {
  try {
    const d = document.documentElement;
    const scrollbar = d.scrollHeight - window.innerHeight;
    if (scrollbar <= 0) return 100;      // Seite passt ins Bild = vollstaendig gesehen
    return Math.min(100, Math.round(((window.scrollY || 0) / scrollbar) * 100));
  } catch { return 0; }
}

/** Schliesst den laufenden Seitenaufruf ab. Mehrfachaufruf ist unschaedlich. */
function schliesseSeite() {
  if (!laufenderPfad) return;
  melde({
    art: "seite_verlassen",
    pfad: laufenderPfad,
    dauer_ms: Date.now() - seit,
    tiefe_pct: Math.max(tiefe, tiefeJetzt()),
  });
  laufenderPfad = null;
}

/** Beginnt einen Seitenaufruf. Bei einem Routenwechsel wird der vorige zuerst geschlossen.
 *
 * ⚠ GENAU HIER ENTSTEHT SONST DIE DOPPELZAEHLUNG. Im App Router wechselt die Route ohne
 *   Neuladen; wer nur beim ersten Laden zaehlt, sieht eine Sitzung als EINEN Aufruf, und wer
 *   nicht vorher abschliesst, verliert die Verweildauer der vorigen Seite. */
export function beginneSeite(neu?: string) {
  const p = neu ?? pfad();
  if (laufenderPfad === p) return;
  schliesseSeite();
  laufenderPfad = p;
  seit = Date.now();
  tiefe = tiefeJetzt();
  melde({ art: "seite_gesehen", pfad: p });
}

/* ──────────────────────────────────────────────────────────────── Klickkarte */

/** Stabile Kennung des geklickten Elements — ohne Text.
 *
 * Reihenfolge: `data-mess` (ausdrueckliche Benennung im Markup, am stabilsten) → `id` →
 * Tag plus erste Klasse der naechsten drei Vorfahren. Mehr Tiefe bringt nichts: lange
 * Selektoren brechen beim naechsten Umbau und sind beim Auswerten unlesbar.
 *
 * ⚠ KEIN `textContent`, KEIN `value`, KEIN `aria-label` mit Freitext. Auf den App-Seiten
 *   stehen Vergabedaten, und `aria-label` traegt oft genau den Lead-Titel. */
function zielVon(el: Element | null): string | null {
  if (!el) return null;
  try {
    const mess = el.closest("[data-mess]")?.getAttribute("data-mess");
    if (mess) return mess.slice(0, 200);
    if (el.id) return `#${el.id}`.slice(0, 200);
    const teile: string[] = [];
    let k: Element | null = el;
    for (let i = 0; i < 3 && k; i++, k = k.parentElement) {
      const klasse = (k.getAttribute("class") || "").trim().split(/\s+/)[0];
      teile.unshift(klasse ? `${k.tagName.toLowerCase()}.${klasse}` : k.tagName.toLowerCase());
    }
    return teile.join(">").slice(0, 200);
  } catch { return null; }
}

function beiKlick(ev: MouseEvent) {
  const el = ev.target as Element | null;
  const ziel = zielVon(el);
  if (!ziel) return;
  let x: number | null = null, y: number | null = null;
  try {
    const r = (el as HTMLElement).getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      x = Math.round(((ev.clientX - r.left) / r.width) * 100);
      y = Math.round(((ev.clientY - r.top) / r.height) * 100);
    }
  } catch { /* Position ist Beigabe, das Element ist die Information */ }
  melde({
    art: "klick",
    ziel,
    ziel_x_pct: x,
    ziel_y_pct: y,
    viewport_w: window.innerWidth,
    viewport_h: window.innerHeight,
  });
}

/* ──────────────────────────────────────────────────────────────── Anschluss */

let haengt = false;

/** Haengt die Sammler ein. Mehrfachaufruf ist unschaedlich. */
export function starteTelemetrie() {
  if (haengt || !darfMessen()) return;
  haengt = true;
  document.addEventListener("click", beiKlick, { capture: true, passive: true });
  window.addEventListener("scroll", () => { tiefe = Math.max(tiefe, tiefeJetzt()); }, { passive: true });

  // ⚠ `pagehide` und `visibilitychange`, NICHT `unload`. `unload` feuert auf iOS gar nicht
  //   und verhindert die Rueckwaerts-Zwischenspeicherung; wer darauf baut, verliert genau die
  //   mobilen Besuche. Das sind bei einer SEO-Seite nicht die wenigsten.
  window.addEventListener("pagehide", () => { schliesseSeite(); senden(true); });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") { schliesseSeite(); senden(true); }
    else beginneSeite();
  });
}
