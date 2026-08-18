import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

/**
 * Zustand des Tageslaufs und des Dokumenten-Rückstands — LIVE aus dem Dateisystem.
 *
 * **Warum live und nicht aus einer Statusdatei.** Die naheliegende Lösung wäre, den Lauf am
 * Ende eine JSON schreiben zu lassen. Genau die versagt aber im wichtigsten Fall: läuft der
 * Tageslauf gar nicht erst an, schreibt er auch nichts — und das Dashboard zeigt vergnügt
 * den Stand von vorgestern. Eine Überwachung, die beim Ausfall stillsteht, überwacht nichts.
 *
 * Deshalb wird hier gelesen, was UNABHÄNGIG vom Lauf existiert: die Logdatei (oder ihr
 * Fehlen) und die Archive auf der Platte. Der Index hinterlässt zusätzlich seinen Stand
 * (`_index_stand.json`) — den braucht es, weil das Frontend kein DuckDB hat und die
 * indizierte Menge sonst nicht kennt.
 */

export const runtime = "nodejs";
export const dynamic = "force-dynamic";   // niemals cachen: der Sinn ist Aktualität

const WURZEL = path.resolve(process.cwd(), "..");
const LOGS = path.join(WURZEL, "data", "logs");
// launchd lenkt stderr hierher. DIESE Datei ist die einzige, die noch beschreibbar ist,
// wenn die Datenplatte gesperrt ist — und genau dann faellt der Lauf aus. Ohne sie hat das
// Dashboard einen blinden Fleck an der wichtigsten Stelle: ein Lauf, der stirbt, BEVOR er
// sein eigenes Log anlegen kann, waere unsichtbar (gemessen 2026-08-15: genau so lief es
// seit Tagen).
const LAUNCHD_ERR = path.join(process.env.HOME || "", "Library", "Logs",
                              "govisor-launchd.err.log");
const DOCS = path.join(WURZEL, "data", "docs", "DE");

type Lauf = {
  datum: string | null;
  ergebnis: "durch" | "mit_fehlern" | "abgebrochen" | "laeuft" | "keiner";
  dauerSek: number | null;
  endeUm: string | null;
  alterStunden: number | null;
  fehlerZeilen: string[];
  letzterSchritt: string | null;
  schrittListe: { zeit: string; name: string }[];
  /** Dauer je ABGESCHLOSSENEM Schritt dieses Laufs (aus den `⏱`-Zeilen). */
  schrittDauern: Record<string, number>;
  logZeilen: string[];
};

/** Der Dokumenten-Trichter für die Live-Ansicht.
 *
 * Liest die FERTIGEN Exporte, nicht die Rohdaten: `web/data/doc-*.json` ist genau das,
 * was beim Nutzer ankommt. Wer stattdessen Parquet zählte, sähe Zahlen, die im Frontend
 * nie erscheinen — und exakt diese Lücke soll hier ja sichtbar werden. Genau so blieb
 * monatelang unbemerkt, dass 4.499 Volltexte bereitlagen und 14 ankamen.
 */
function trichter() {
  const schluessel = (name: string): Set<string> | null => {
    try {
      const roh = fs.readFileSync(path.join(WURZEL, "web", "data", name), "utf-8");
      return new Set(Object.keys(JSON.parse(roh)));
    } catch { return null; }
  };
  // Der Volltext liegt seit dem 2026-08-18 je Vorgang in `web/data/doc-text/`; gezaehlt
  // wird ueber das Verzeichnis `doc-text-index.json` (284 KB statt 294 MB).
  const volltext = schluessel("doc-text-index.json");
  const analyse = schluessel("doc-analysis.json");
  const signale = schluessel("doc-signals.json");
  const struktur = schluessel("doc-struktur.json");

  // ⚠ DIE ZAHLEN, DIE WIRKLICH INTERESSIEREN, SIND DIFFERENZEN, KEINE BESTAENDE.
  // Sven am 2026-08-18 vor dieser Anzeige: „fuer mich liest sich das nach: es gibt nur noch
  // 25 im rueckstau … ich bin verwirrt." Zu Recht. Oben standen Archive (ZIP-DATEIEN),
  // darunter Vorgaenge — zwei Grundmengen ohne Beschriftung. Der Rueckstand beim Auspacken
  // war fast null, waehrend 4.766 Vorgaenge mit fertigem Volltext auf ihre Analyse warteten.
  // Vier Bestandszahlen nebeneinander beantworten die Frage „wo klemmt es" eben nicht.
  const fehlt = (a: Set<string> | null, b: Set<string> | null) =>
    a && b ? [...a].filter((k) => !b.has(k)).length : null;
  return {
    signale: signale?.size ?? null,
    volltext: volltext?.size ?? null,
    analyse: analyse?.size ?? null,
    struktur: struktur?.size ?? null,
    ohneAnalyse: fehlt(volltext, analyse),
    ohneSignale: fehlt(volltext, signale),
  };
}

/** Wer kann gerade analysieren? Geschrieben von `scripts/analyze_docs.py` nach jeder Runde.
 *
 * Die Zahl „wartet auf Analyse" stand am 2026-08-18 eine Stunde still, weil das Guthaben
 * leer war — und man sah nur, DASS nichts passiert, nicht warum. Ein Betriebsmonitor, der
 * den Stillstand zeigt, aber nicht seinen Grund, erzeugt genau die Rückfrage, die er
 * ersparen soll.
 */
function llmStand() {
  try {
    const roh = fs.readFileSync(path.join(WURZEL, "data", ".llm_stand.json"), "utf-8");
    const d = JSON.parse(roh) as {
      zeit: number; erschoepft: boolean;
      anbieter: { name: string; modell: string; keys: number; frei: number }[];
    };
    return {
      zeit: d.zeit ?? null,
      erschoepft: !!d.erschoepft,
      anbieter: (d.anbieter ?? []).map((a) => ({ name: a.name, modell: a.modell, frei: a.frei })),
    };
  } catch { return null; }
}

/** Zustand des Dauer-Arbeiters: läuft er, und was sagt er zuletzt? */
function arbeiterStand() {
  let laeuft = false;
  let letzte: string[] = [];
  try {
    const sperre = path.join(WURZEL, "data", ".dokumente_arbeiter.lock");
    const pid = Number(fs.readFileSync(sperre, "utf-8").trim());
    // `process.kill(pid, 0)` wirft, wenn es den Prozess nicht gibt — das ist die
    // Prüfung, nicht das Töten.
    if (pid) { process.kill(pid, 0); laeuft = true; }
  } catch { laeuft = false; }
  try {
    // NUR die eigenen Meldungen. Der Arbeiter leitet die Ausgaben der aufgerufenen
    // Schritte ins selbe Log, und `index-docs` schuettet dort seitenweise
    // pdfminer-Gemecker hinein ("Ignoring wrong pointing object 39 0"). Gemessen am
    // 2026-08-18: 13 von 189 Zeilen (6,9 %) waren eigene Meldungen — die letzten sechs
    // Zeilen zeigten damit meist gar nichts ueber den Arbeiter, sondern ueber ein PDF.
    // Der Zeitstempel am Zeilenanfang ist das Merkmal, das `sag()` im Skript setzt.
    letzte = fs.readFileSync(path.join(LOGS, "dokumente-arbeiter.log"), "utf-8")
      .split("\n").filter((z) => /^\[\d{2}\.\d{2}\. \d{2}:\d{2}\]/.test(z)).slice(-6);
  } catch { letzte = []; }
  return { laeuft, letzte };
}

/** Zählt Archive auf der Platte — ohne sie zu öffnen. */
function zaehleArchive(wurzel: string): number {
  let n = 0;
  const lauf = (d: string) => {
    let eintraege: fs.Dirent[];
    try { eintraege = fs.readdirSync(d, { withFileTypes: true }); } catch { return; }
    for (const e of eintraege) {
      if (e.isDirectory()) lauf(path.join(d, e.name));
      else if (e.name.endsWith(".zip")) n++;
    }
  };
  lauf(wurzel);
  return n;
}

function letzteLogdatei(): string | null {
  let dateien: string[];
  // Zwei Namensformen: `daily-2026-08-16.log` (alt, ein Lauf je TAG) und
  // `daily-2026-08-16-2200.log` (neu, ein Lauf je START). Beide muessen gelesen werden —
  // die Historie soll nicht verschwinden, nur weil das Schema sich geaendert hat.
  try {
    dateien = fs.readdirSync(LOGS)
      .filter((f) => /^daily-\d{4}-\d{2}-\d{2}(-\d{4})?\.log$/.test(f));
  } catch { return null; }
  if (!dateien.length) return null;
  // Alphabetisch sortiert stimmt die Reihenfolge fuer BEIDE Formen: `…-16.log` kommt vor
  // `…-16-0900.log`, und innerhalb eines Tages sortiert die Uhrzeit korrekt. Die Altform
  // landet damit VOR den Laeufen desselben Tages — richtig, sie ist die aeltere.
  dateien.sort();
  return dateien[dateien.length - 1];
}

function leseLauf(): Lauf {
  const datei = letzteLogdatei();
  if (!datei) {
    return { datum: null, ergebnis: "keiner", dauerSek: null, endeUm: null,
             alterStunden: null, fehlerZeilen: [], letzterSchritt: null,
             schrittListe: [], schrittDauern: {}, logZeilen: [] };
  }
  const voll = path.join(LOGS, datei);
  const datum = datei.slice(6, 16);
  let text = "";
  try { text = fs.readFileSync(voll, "utf8"); } catch { /* leer behandeln */ }
  const alleZeilen = text.split("\n");

  // NUR DER LETZTE LAUF. Bis 2026-08-16 hiess die Logdatei nur `daily-<datum>.log` —
  // zwei Laeufe am selben Tag landeten also hintereinander in DERSELBEN Datei. Das
  // Dashboard las beide als einen: es fand das Ende des ERSTEN und meldete
  // „durchgelaufen", waehrend der zweite noch arbeitete.
  //
  // Der Dateiname traegt jetzt die Startzeit, das Problem entsteht also nicht neu. Dieser
  // Schnitt bleibt trotzdem: die Altbestaende sind noch da, und ein Anzeigefehler, der
  // „laeuft" als „fertig" ausgibt, ist genau der, den man nicht bemerkt.
  const startZeilen: number[] = [];
  alleZeilen.forEach((z, i) => { if (z.startsWith("goVisor Tageslauf  ")) startZeilen.push(i); });
  const zeilen = startZeilen.length > 1
    ? alleZeilen.slice(startZeilen[startZeilen.length - 1])
    : alleZeilen;

  // Der Lauf meldet sein Ende selbst. Fehlt die Zeile, ist er abgebrochen — das ist der
  // Fall, den man am dringendsten sehen will und der sich sonst als „alles ruhig" tarnt.
  const ende = [...zeilen].reverse().find((z) => z.includes("Tageslauf fertig in")) || null;
  const mDauer = ende?.match(/fertig in (\d+)s/);
  const mZeit = ende?.match(/\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)/);

  // ✖ ist ein harter Fehlschlag eines Schritts, ⚠ eine unvollständige, aber verkraftete
  // Teilaufgabe. Beide gehören ins Dashboard — der Unterschied steht im Text.
  const fehlerZeilen = zeilen
    .filter((z) => z.trimStart().startsWith("✖") || z.trimStart().startsWith("⚠"))
    .map((z) => z.trim())
    .slice(-12);

  const schritte = zeilen.filter((z) => /^▶ \d{2}:\d{2}:\d{2}/.test(z));
  const letzterSchritt = schritte.length ? schritte[schritte.length - 1].replace(/^▶ \S+\s+/, "") : null;
  // Dauern des LAUFENDEN Laufs. Der Schritt schreibt seine Dauer erst, wenn der naechste
  // beginnt — der aktuelle steht deshalb nie hier drin, und genau das ist richtig: seine
  // Dauer laeuft ja noch.
  const schrittDauern: Record<string, number> = {};
  for (const z of zeilen) {
    const dm = z.match(/^  ⏱ (.+?) — (\d+)s$/);
    if (dm) schrittDauern[dm[1].trim()] = Number(dm[2]);
  }
  const schrittListe = schritte.map((z) => {
    const m = z.match(/^▶ (\d{2}:\d{2}:\d{2})\s+(.*)$/);
    return { zeit: m ? m[1] : "", name: m ? m[2].trim() : z.trim() };
  });

  let stand: fs.Stats | null = null;
  try { stand = fs.statSync(voll); } catch { /* ignorieren */ }
  const laeuftNoch = !ende && stand ? Date.now() - stand.mtimeMs < 20 * 60 * 1000 : false;

  return {
    datum,
    ergebnis: ende
      ? (ende.includes("MIT Fehler") ? "mit_fehlern" : "durch")
      : (laeuftNoch ? "laeuft" : "abgebrochen"),
    dauerSek: mDauer ? Number(mDauer[1]) : null,
    endeUm: mZeit ? mZeit[1] : null,
    alterStunden: stand ? Math.round((Date.now() - stand.mtimeMs) / 36e5 * 10) / 10 : null,
    fehlerZeilen,
    letzterSchritt,
    schrittListe, schrittDauern,
    // Die letzten Zeilen roh — beim Zusehen will man wissen, WAS gerade passiert, nicht nur
    // welcher Schritt laeuft. Ein Schritt kann 40 Minuten dauern.
    logZeilen: zeilen.filter(Boolean).slice(-60).map((z) => z.replace(/\s+$/, "")),
  };
}

/** Der letzte VOLLSTAENDIGE Lauf als Massstab — nicht die `step`-Zeilen im Skript.
 *
 * Gemessen 2026-08-15: das Skript enthaelt 30 `step`-Aufrufe, der vollstaendige Lauf vom
 * 14.08. meldete 20. Zehn Schritte haengen an Bedingungen (neue Quellen, Supabase-Creds,
 * Phase). Ein Balken gegen die statische 30 stuende bei einem sauberen Lauf fuer immer bei
 * 67 % — und ein Fortschritt, der nie 100 % erreicht, wird nicht geglaubt.
 *
 * Deshalb der empirische Massstab: was hier zuletzt WIRKLICH gelaufen ist. Er kann daneben
 * liegen, wenn sich der Umfang aendert (heute sind die neuen Quellen dazugekommen) — darum
 * wird er nach oben nachgezogen, statt bei 100 % zu kleben.
 */
function massstab(ausser: string | null):
    { schritte: number; dauerSek: number; namen: string[]; dauern: Record<string, number> } | null {
  let dateien: string[];
  try {
    dateien = fs.readdirSync(LOGS)
      .filter((f) => /^daily-\d{4}-\d{2}-\d{2}(-\d{4})?\.log$/.test(f));
  } catch { return null; }
  dateien.sort().reverse();
  for (const f of dateien) {
    if (ausser && f === ausser) continue;
    let t = "";
    try { t = fs.readFileSync(path.join(LOGS, f), "utf8"); } catch { continue; }
    const ende = t.split("\n").reverse().find((z) => z.includes("Tageslauf fertig in"));
    if (!ende) continue;                       // unvollstaendig → taugt nicht als Massstab
    const m = ende.match(/fertig in (\d+)s/);
    const namen = (t.match(/^▶ \d{2}:\d{2}:\d{2}  (.+)$/gm) || [])
      .map((z) => z.replace(/^▶ \d{2}:\d{2}:\d{2}  /, "").trim());
    // Dauer je Schritt aus dem Vergleichslauf — daraus wird die Restzeit je Schritt
    // geschaetzt statt einer einzigen Gesamtzahl. „Noch 3 h" hilft niemandem, „subreport
    // dauert normal 88 min" schon.
    const dauern: Record<string, number> = {};
    for (const z of t.split("\n")) {
      const dm = z.match(/^  ⏱ (.+?) — (\d+)s$/);
      if (dm) dauern[dm[1].trim()] = Number(dm[2]);
    }
    if (namen.length > 0) {
      return { schritte: namen.length, dauerSek: m ? Number(m[1]) : 0, namen, dauern };
    }
  }
  return null;
}

/** Die letzten Zeilen des launchd-Fehlerlogs — nur, wenn sie NEUER sind als der letzte
 *  eigene Lauf-Log. Sonst zeigt das Dashboard alte Fehler, die laengst behoben sind. */
function launchdFehler(seit: number | null): { zeit: number; zeilen: string[] } | null {
  let st: fs.Stats;
  try { st = fs.statSync(LAUNCHD_ERR); } catch { return null; }
  if (seit != null && st.mtimeMs <= seit) return null;
  try {
    const zeilen = fs.readFileSync(LAUNCHD_ERR, "utf8")
      .split("\n").map((z) => z.trim()).filter(Boolean).slice(-10);
    return zeilen.length ? { zeit: st.mtimeMs, zeilen } : null;
  } catch { return null; }
}

export async function GET() {
  // GLEICHE SPERRE WIE DIE ANDEREN /api/intern-ROUTEN. Diese Antwort enthaelt Auszuege aus
  // Logdateien (Pfade, Fehlermeldungen, Schrittnamen) — das ist Betriebswissen und gehoert
  // nicht ins offene Netz, auch wenn es harmlos aussieht.
  if (process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1") {
    return NextResponse.json({ error: "not found" }, { status: 404 });
  }
  const lauf = leseLauf();

  const aufPlatte = zaehleArchive(DOCS);
  let indexStand: Record<string, unknown> | null = null;
  try {
    indexStand = JSON.parse(fs.readFileSync(path.join(DOCS, "_index_stand.json"), "utf8"));
  } catch { /* noch kein Lauf mit Standdatei */ }

  // OHNE STANDDATEI GIBT ES KEINE ZAHL, nur Unwissen. Der erste Entwurf rechnete hier mit
  // 0 indizierten Archiven weiter und meldete damit einen Rueckstand von 3.282 — eine
  // Zahl, die nach Alarm aussieht und nur bedeutet, dass noch nie ein Index mit Stand
  // gelaufen ist. Eine erfundene Kennzahl ist schlimmer als ein ehrliches „unbekannt":
  // nach ihr wird gehandelt.
  const hatStand = indexStand != null;
  const indiziert = hatStand
    ? Number(indexStand?.archive_bearbeitet ?? 0) + Number(indexStand?.archive_uebersprungen ?? 0)
    : null;
  const status = (indexStand?.status ?? {}) as Record<string, number>;

  // Der eigene Lauf-Log ist die Hauptquelle. Ist das launchd-Log JUENGER, hat ein Lauf
  // gestartet und ist gescheitert, ohne bis zum eigenen Log zu kommen — das ist der Fall,
  // der ohne diese Zeile unsichtbar bliebe.
  let eigenerStand: number | null = null;
  const letzte = letzteLogdatei();
  if (letzte) { try { eigenerStand = fs.statSync(path.join(LOGS, letzte)).mtimeMs; } catch { /* egal */ } }
  const vorLog = launchdFehler(eigenerStand);

  const mass = massstab(letzte);
  const fertig = lauf.schrittListe.length;
  // Nach oben nachziehen: laeuft der aktuelle Lauf laenger als der Massstab, ist der
  // Massstab veraltet — nicht der Lauf kaputt.
  const erwartet = mass ? Math.max(mass.schritte, fertig) : fertig;
  const anteil = erwartet ? Math.min(1, fertig / erwartet) : 0;
  // Restzeit nur schaetzen, wenn es einen Massstab gibt UND der Lauf laeuft. Eine Zahl
  // ohne Grundlage waere hier besonders schaedlich: nach ihr wird der Tag geplant.
  const verbleibendSek = mass && mass.dauerSek && lauf.ergebnis === "laeuft"
    ? Math.max(0, Math.round(mass.dauerSek * (1 - anteil)))
    : null;

  // ── ERTRAGSBERICHT ──────────────────────────────────────────────────────────────────
  // Vom Tageslauf geschrieben (`govisor/ertrag.py`). Er wird hier nur DURCHGEREICHT, nicht
  // nachgerechnet: die Zahlen stammen aus DuckDB ueber Parquet, das kann eine Route nicht
  // — und zwei Rechenwege fuer dieselbe Kennzahl waeren zwei Wahrheiten.
  //
  // Fehlt die Datei, fehlt die Kachel. Ein Dashboard, das bei fehlender Nebengroesse
  // komplett ausfaellt, wird beim ersten Mal geschlossen.
  let ertrag: Record<string, unknown> | null = null;
  try {
    ertrag = JSON.parse(fs.readFileSync(path.join(LOGS, "ertrag.json"), "utf8"));
  } catch {
    ertrag = null;
  }

  // ── SCHRITTLISTE: wo genau steht der Lauf? ──────────────────────────────────────────
  // Ein Balken sagt „64 von 64" und damit fast nichts. Was man wissen will, ist WELCHER
  // Schritt gerade laeuft, wie lange er schon braucht und was noch kommt.
  //
  // Die erledigten Schritte stehen im eigenen Log, die noch kommenden nur im Massstab —
  // deshalb werden beide Listen zusammengefuehrt. Fehlt der Massstab, zeigt die Liste
  // ehrlich nur das Erledigte statt eine erfundene Zukunft.
  // Schrittnamen tragen VERAENDERLICHE Teile in Klammern: die Portalliste von NetServer
  // waechst, und „Gold-Rebuild (Leads mit Stichtag 2026-08-14)" enthaelt das Datum. Ein
  // Vergleich auf den vollen Namen findet deshalb nie eine Uebereinstimmung — im Browser
  // gesehen: bereits gelaufene Schritte standen als „offen" in der Liste.
  //
  // Verglichen wird deshalb der Teil VOR der ersten Klammer. Der ist im Skript fest.
  const kern = (n: string) => n.split(" (")[0].trim();
  const gemacht = new Set(lauf.schrittListe.map((x) => kern(x.name)));
  const dauern = mass?.dauern ?? {};
  const schritte: { name: string; zeit: string | null; dauerSek: number | null;
                    normalSek: number | null; zustand: "fertig" | "laeuft" | "offen" }[] = [];
  lauf.schrittListe.forEach((x, i) => {
    const laeuft = i === lauf.schrittListe.length - 1 && lauf.ergebnis === "laeuft";
    schritte.push({
      name: x.name, zeit: x.zeit,
      dauerSek: lauf.schrittDauern?.[x.name] ?? null,
      normalSek: dauern[x.name] ?? null,
      zustand: laeuft ? "laeuft" : "fertig",
    });
  });
  // Was der Massstab kennt und dieser Lauf noch nicht angefasst hat. Reihenfolge wie im
  // Vergleichslauf — sie ist im Skript fest, also belastbar.
  for (const n of mass?.namen ?? []) {
    if (!gemacht.has(kern(n))) {
      schritte.push({ name: n, zeit: null, dauerSek: null,
                      normalSek: dauern[n] ?? null, zustand: "offen" });
    }
  }

  return NextResponse.json({
    erzeugt: new Date().toISOString(),
    ertrag,
    schritte,
    lauf,
    fortschritt: { fertig, erwartet, anteil, verbleibendSek,
                   massstabAus: mass ? "letzter vollstaendiger Lauf" : null },
    // Startversuche, die es nicht bis zum eigenen Log geschafft haben.
    vorLog,
    dokumente: {
      aufPlatte,
      indiziert,
      // Rueckstand = was auf der Platte liegt und der Index noch nicht kennt. Negativ kann
      // er werden, wenn Archive geloescht wurden — dann ehrlich 0 statt einer Minuszahl,
      // die niemand deuten kann.
      rueckstand: indiziert == null ? null : Math.max(0, aufPlatte - indiziert),
      stand: indexStand?.stand ?? null,
      zeichen: Number(indexStand?.zeichen ?? 0),
      status,
      // Was der Index NICHT verwerten konnte. Steht getrennt, weil es kein Rueckstand ist:
      // diese Archive sind bearbeitet, sie haben nur keinen Text ergeben.
      abgeschossen: (status.speicher ?? 0) + (status.zeitlimit ?? 0),
      // ── DER TRICHTER ──────────────────────────────────────────────────────────────
      // „Archive auf der Platte" allein sagt nicht, wo es klemmt. Erst die Stufen zeigen,
      // ob das Abholen hinterherhinkt oder das Auswerten — gemessen am 2026-08-18 waren
      // es BEIDE, aber an ganz verschiedenen Stellen: 34 % geholt, nur 1,5 % analysiert.
      trichter: trichter(),
      // Läuft der Dauer-Arbeiter, und was hat er zuletzt gesagt?
      arbeiter: arbeiterStand(),
      llm: llmStand(),
    },
  });
}
