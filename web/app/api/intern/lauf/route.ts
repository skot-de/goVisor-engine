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
};

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
  try { dateien = fs.readdirSync(LOGS).filter((f) => /^daily-\d{4}-\d{2}-\d{2}\.log$/.test(f)); }
  catch { return null; }
  if (!dateien.length) return null;
  dateien.sort();                       // Dateiname ist ISO-Datum → sortiert chronologisch
  return dateien[dateien.length - 1];
}

function leseLauf(): Lauf {
  const datei = letzteLogdatei();
  if (!datei) {
    return { datum: null, ergebnis: "keiner", dauerSek: null, endeUm: null,
             alterStunden: null, fehlerZeilen: [], letzterSchritt: null };
  }
  const voll = path.join(LOGS, datei);
  const datum = datei.slice(6, 16);
  let text = "";
  try { text = fs.readFileSync(voll, "utf8"); } catch { /* leer behandeln */ }
  const zeilen = text.split("\n");

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
  };
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

  return NextResponse.json({
    erzeugt: new Date().toISOString(),
    lauf,
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
    },
  });
}
