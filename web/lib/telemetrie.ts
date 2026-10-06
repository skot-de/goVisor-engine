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

import {
  BESUCHER_COOKIE, COOKIE_TAGE, EINWILLIGUNG_COOKIE, kampagneAus, leseCookie,
  type Entscheidung, type Kampagne,
} from "@/lib/einwilligung";

const WEG = "/api/ereignis";
const SCHLUESSEL = "gv_tm_sitzung";

type Rohereignis = Record<string, unknown> & { art: string };

/* ──────────────────────────────────────────────────────── Darf gemessen werden? */

/**
 * Stufe 1 laeuft immer (im Browser), sie braucht keine Einwilligung.
 *
 * ⚠ KORREKTUR ZUM 2026-10-02: hier unterdrueckte „Do Not Track" bzw. „Global Privacy
 *   Control" zunaechst JEDE Messung. Das war zu weit gegriffen. Stufe 1 erkennt niemanden
 *   wieder und stuetzt sich auf berechtigtes Interesse; ein Widerspruch gegen
 *   Nachverfolgung richtet sich nicht dagegen. Die Signale wirken deshalb jetzt genau dort,
 *   wo sie hingehoeren: sie verhindern Stufe 2 (s. `widerspruch()`), also die dauerhafte
 *   Kennung — und sie verhindern, dass ueberhaupt gefragt wird.
 */
function darfMessen(): boolean {
  return typeof window !== "undefined";
}

/**
 * Hat der Besucher der Nachverfolgung ausdruecklich widersprochen?
 *
 * ⚠ GPC UND DNT HABEN IN DER EU KEINE BINDENDE WIRKUNG — und werden hier trotzdem geachtet.
 *   Nicht aus Vorsicht, sondern weil es die Abwaegung traegt: wer ein maschinenlesbares Nein
 *   sendet und dann einen Einwilligungshinweis vorgesetzt bekommt, ist zu Recht veraergert.
 *   Wir fragen solche Besucher gar nicht und setzen keine Kennung. Stufe 1 laeuft weiter.
 */
export function widerspruch(): boolean {
  try {
    const n = navigator as Navigator & { globalPrivacyControl?: boolean; msDoNotTrack?: string };
    return n.globalPrivacyControl === true || n.doNotTrack === "1" || n.msDoNotTrack === "1";
  } catch { return false; }
}

/* ──────────────────────────────────────────── Einwilligung und Besucherkennung (Stufe 2) */

function setzeCookie(name: string, wert: string, tage: number) {
  try {
    const bis = new Date(Date.now() + tage * 86_400_000).toUTCString();
    const sicher = location.protocol === "https:" ? "; Secure" : "";
    document.cookie = `${name}=${encodeURIComponent(wert)}; Expires=${bis}; Path=/; SameSite=Lax${sicher}`;
  } catch { /* blockierte Cookies: dann bleibt es bei Stufe 1 */ }
}

/** Die Entscheidung des Besuchers, oder `null` wenn noch nichts entschieden ist. */
export function entscheidung(): Entscheidung {
  if (typeof document === "undefined") return null;
  const w = leseCookie(document.cookie, EINWILLIGUNG_COOKIE);
  return w === "ja" || w === "nein" ? w : null;
}

/**
 * Entscheidung festhalten. Bei „ja" wird zusaetzlich die dauerhafte Kennung angelegt,
 * bei „nein" eine bestehende entfernt.
 *
 * ⚠ DAS ENTFERNEN BEI „NEIN" IST KEIN DETAIL. Ein Widerruf muss so einfach sein wie die
 *   Erteilung (Art. 7 Abs. 3 DSGVO). Bliebe die Kennung im Browser liegen, wuerde sie beim
 *   naechsten Besuch mitgesendet — und der Server wuerde sie verwerfen, weil die
 *   Einwilligung fehlt. Das ginge gerade noch, aber es waere eine Kennung ohne Grundlage auf
 *   dem Geraet des Besuchers. Die loescht man.
 */
export function entscheide(wert: "ja" | "nein") {
  setzeCookie(EINWILLIGUNG_COOKIE, wert, COOKIE_TAGE);
  if (wert === "ja") {
    if (!leseCookie(document.cookie, BESUCHER_COOKIE)) {
      const id = (crypto.randomUUID?.() ?? String(Math.random()).slice(2)).replace(/-/g, "");
      setzeCookie(BESUCHER_COOKIE, id, COOKIE_TAGE);
    }
  } else {
    setzeCookie(BESUCHER_COOKIE, "", -1);
  }
}

/**
 * Kampagnenkennung des EINSTIEGS, nicht der aktuellen Seite.
 *
 * ⚠ GENAU HIER GEHT KAMPAGNENMESSUNG SONST KAPUTT. Die `utm_*`-Parameter stehen nur in der
 *   Adresse, mit der jemand ANKOMMT; klickt er weiter, sind sie weg. Wer sie je Ereignis
 *   frisch aus der Adresse liest, sieht die Kampagne genau beim ersten Aufruf und danach
 *   nie — und ordnet damit eine Anmeldung keiner Kampagne mehr zu, obwohl sie aus ihr kam.
 *   Deshalb werden sie beim ersten Aufruf in `sessionStorage` gelegt und an JEDES Ereignis
 *   der Sitzung angehaengt.
 */
const KAMPAGNE_SCHLUESSEL = "gv_tm_kampagne";

function kampagne(): Kampagne {
  if (entscheidung() !== "ja") return {};   // Kampagne ist Stufe 2
  try {
    const frisch = kampagneAus(location.search);
    if (Object.keys(frisch).length) {
      sessionStorage.setItem(KAMPAGNE_SCHLUESSEL, JSON.stringify(frisch));
      return frisch;
    }
    const gemerkt = sessionStorage.getItem(KAMPAGNE_SCHLUESSEL);
    return gemerkt ? (JSON.parse(gemerkt) as Kampagne) : {};
  } catch { return {}; }
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
  // ⚠ `kampagne()` prueft selbst auf Einwilligung und liefert sonst nichts. Die
  //   Besucherkennung und die Einwilligung selbst schickt der Browser NICHT mit — sie stehen
  //   in Cookies, die ohnehin bei jeder Anfrage mitlaufen, und der Server liest sie dort.
  //   Sie als Feld zu senden waere ein Feld, dem man nicht glauben darf.
  puffer.push({ ...e, sitzung: sitzung(), pfad: e.pfad ?? pfad(), ...kampagne() });
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
