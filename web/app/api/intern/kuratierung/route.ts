import { NextResponse } from "next/server";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

/**
 * Kuratierung (Admin-Portal, Bereich 5). Ansicht + Pflege der `curated/`-CSVs, die den
 * naechsten Gold-/Silber-Lauf steuern (Aliasse, Regions-/Kategorie-Korrekturen, gesperrte
 * Hosts, Portale ohne Abrufer).
 *
 * ⚠ WICHTIG — zwei Leseorte, je Datei verschieden. `data/` ist ein Symlink auf die externe
 * Platte (NICHT versioniert); das Repo-`curated/` ist versioniert. Gemessen an den ECHTEN
 * Lesestellen im Code, nicht an den Kommentaren dort:
 *   - entity_aliases  → `data/curated/` (gold.py liest cfg.data_dir/curated; der Kommentar
 *                       darueber behauptet "Repo zuerst", der Code tut es NICHT — s. Bericht)
 *   - kategorie       → Repo `curated/`, Fallback `data/curated/` (kategorie.py:_pfad)
 *   - region/hosts/portale → Repo `curated/` (region_ableiten.py, docfetch_queue.py,
 *                       pruefe_vollstaendigkeit.py)
 * Jede REGISTRY-Zeile schreibt an genau den Pfad, den ihr Konsument liest — sonst
 * "gebaut, nicht verdrahtet".
 *
 * ⚠ Schreiben auf eine Datei unter `data/` waehrend ein Lauf denselben Baum liest, ist die
 * Kollision, vor der `laeuft_was.sh` schuetzt. Vor jedem Schreiben auf `data/` wird geprueft
 * und im Zweifel fail-closed abgelehnt.
 *
 * Gleiche Sperre wie die uebrigen /api/intern-Routen (Middleware istAdmin + Prod-Riegel).
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const ROOT = path.resolve(process.cwd(), "..");
function gesperrt() {
  return process.env.NODE_ENV === "production" && process.env.INTERN_ENABLED !== "1";
}

type Ort = "repo" | "data" | "kategorie";
type Art = {
  id: string;
  label: string;
  ort: Ort;
  perLand: boolean;
  laender?: string[];               // erlaubte Laender (sonst beliebig 2-3 Buchstaben)
  datei: (land: string) => string;  // Basename
  spalten: string[];                // CSV-Kopf in dieser Reihenfolge
  pflicht: string[];                // Spalten, die beim Anlegen nicht leer sein duerfen
  enums?: Record<string, string[]>; // erlaubte Werte je Spalte (sonst frei)
  editierbar: boolean;
  gross?: boolean;                  // nur Vorschau (grosse, abgeleitete Datei)
  autoStand?: boolean;              // Spalte `stand` mit heute vorbelegen
  hinweis: string;
};

const REGISTRY: Art[] = [
  {
    id: "entity_aliases", label: "Entity-Aliasse", ort: "data", perLand: true,
    datei: (l) => `${l}_entity_aliases.csv`,
    spalten: ["alias_name", "canonical_name", "grund"],
    pflicht: ["alias_name", "canonical_name"], editierbar: true,
    hinweis: "Belegte Umbenennung/Fragment → kanonische Entitaet. Merge-Kandidaten aus Bereich 2 landen hier. Liegt unter data/ (externe Platte).",
  },
  {
    id: "region_korrektur", label: "Regionskorrekturen", ort: "repo", perLand: true,
    laender: ["DE", "AT", "CH"],
    datei: (l) => `${l}_region_korrektur.csv`,
    spalten: ["buyer_name", "plz", "region_alt", "region_neu", "beleg", "stand"],
    pflicht: ["buyer_name", "region_neu"], editierbar: true, autoStand: true,
    hinweis: "Belegte NUTS-Korrektur je Kaeufer (region_neu ueberschreibt region_alt).",
  },
  {
    id: "kategorie_korrektur", label: "Kategorie-Korrekturen", ort: "kategorie", perLand: true,
    datei: (l) => `${l}_kategorie_korrektur.csv`,
    spalten: ["notice_id", "division", "titel", "grund", "stand"],
    pflicht: ["notice_id", "division"], editierbar: true, autoStand: true,
    hinweis: "Branchen-/Divisions-Zuordnung je Notice. Speist zusaetzlich die LLM-Lernschleife.",
  },
  {
    id: "hosts_gesperrt", label: "Gesperrte Hosts", ort: "repo", perLand: false,
    datei: () => `hosts_gesperrt.csv`,
    spalten: ["host", "land", "grund", "beleg", "stand"],
    pflicht: ["host", "land", "grund"], editierbar: true, autoStand: true,
    hinweis: "Host wird gar nicht erst angefragt (robots/Anmeldung). Sperre gilt nur fuer Dokument-Abruf.",
  },
  {
    id: "portale_ohne_abrufer", label: "Portale ohne Abrufer", ort: "repo", perLand: false,
    datei: () => `portale_ohne_abrufer.csv`,
    spalten: ["host", "land", "leads", "grund", "stand"],
    pflicht: ["host", "land"], editierbar: true, autoStand: true,
    hinweis: "Bekannte Luecke: Portal ohne Parser (Anmeldung/abweisend). Kein Abruf, nur vermerkt.",
  },
  {
    id: "entity_merge_entscheidung", label: "Merge-Entscheidungen (Bereich 2)", ort: "repo", perLand: true,
    datei: (l) => `${l}_entity_merge_entscheidung.csv`,
    spalten: ["entity_a", "entity_b", "entscheidung", "name_a", "name_b", "grund", "stand"],
    pflicht: ["entity_a", "entity_b", "entscheidung"], editierbar: true, autoStand: true,
    enums: { entscheidung: ["gleich", "verschieden"] },
    hinweis: "Menschlicher Entscheid je Merge-Kandidat (aus Bereich 2). Oberste Instanz vor den LLM-Richtern; wirkt beim naechsten entity_merge_anwenden-Lauf + Gold-Rebuild.",
  },
  {
    id: "vergabestellen_worklist", label: "Vergabestellen-Worklist", ort: "repo", perLand: false,
    datei: () => `vergabestellen_kuratierung_worklist.csv`,
    spalten: ["notices", "fragmente", "beispiel_varianten"],
    pflicht: [], editierbar: false,
    hinweis: "Kuratierungs-Aufgaben (Namensfragmente je Vergabestelle). Nur Ansicht, abgeleitet.",
  },
  {
    id: "company_groups", label: "Firmengruppen (Vorschau)", ort: "data", perLand: true,
    datei: (l) => `${l}_company_groups.csv`,
    spalten: [], pflicht: [], editierbar: false, gross: true,
    hinweis: "Auto-geseedet, gross. Nur Kopf-Vorschau, nicht von Hand editieren.",
  },
];

function art(id: string): Art | undefined { return REGISTRY.find((a) => a.id === id); }
const LAND = /^[A-Z]{2,3}$/;

function pfad(a: Art, land: string): string {
  const name = a.datei(land);
  if (a.ort === "data") return path.join(ROOT, "data", "curated", name);
  if (a.ort === "repo") return path.join(ROOT, "curated", name);
  // kategorie: Repo zuerst, sonst data/ (spiegelt kategorie.py:_pfad)
  const repo = path.join(ROOT, "curated", name);
  const alt = path.join(ROOT, "data", "curated", name);
  return fs.existsSync(repo) || !fs.existsSync(alt) ? repo : alt;
}
function unterData(a: Art, land: string): boolean {
  return pfad(a, land).startsWith(path.join(ROOT, "data") + path.sep);
}
function relPfad(p: string): string { return path.relative(ROOT, p); }

// ── CSV (RFC4180-nah) ───────────────────────────────────────────────────────────────────
function parseCsv(text: string): string[][] {
  const rows: string[][] = []; let row: string[] = [], f = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { f += '"'; i++; } else q = false; }
      else f += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(f); f = ""; }
    else if (c === "\r") { /* skip */ }
    else if (c === "\n") { row.push(f); rows.push(row); row = []; f = ""; }
    else f += c;
  }
  if (f.length || row.length) { row.push(f); rows.push(row); }
  return rows;
}
function csvFeld(s: string): string {
  return /[",\n\r]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}
function baueCsv(kopf: string[], zeilen: Record<string, string>[]): string {
  const out = [kopf.map(csvFeld).join(",")];
  for (const z of zeilen) out.push(kopf.map((h) => csvFeld(z[h] ?? "")).join(","));
  return out.join("\n") + "\n";
}

function leseZeilen(p: string, spalten: string[]): { kopf: string[]; zeilen: Record<string, string>[] } {
  if (!fs.existsSync(p)) return { kopf: spalten, zeilen: [] };
  const raw = parseCsv(fs.readFileSync(p, "utf8")).filter((r) => r.some((c) => c !== ""));
  if (!raw.length) return { kopf: spalten, zeilen: [] };
  const kopf = raw[0];
  const zeilen = raw.slice(1).map((r) => Object.fromEntries(kopf.map((h, i) => [h, r[i] ?? ""])));
  return { kopf, zeilen };
}

const HEUTE = () => new Date().toISOString().slice(0, 10);

// Formel-Injektion (Excel) + Ueberlaenge abwehren. `-` bleibt erlaubt (Freitext/Minus).
function feldOk(s: string): string | null {
  if (s.length > 2000) return "Feld zu lang (max 2000).";
  if (/^[=+@\t]/.test(s)) return "Feld darf nicht mit = + @ beginnen.";
  return null;
}

export async function GET(req: Request) {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 404 });
  const q = new URL(req.url).searchParams;
  const id = q.get("kind");
  const land = (q.get("country") || "DE").toUpperCase();
  if (!LAND.test(land)) return NextResponse.json({ error: "country ungültig" }, { status: 400 });

  // Index: Uebersicht aller Arten mit Zeilenzahl + Frische.
  if (!id) {
    const arten = REGISTRY.map((a) => {
      const p = pfad(a, land);
      let n: number | null = null, mtime: string | null = null;
      try {
        const st = fs.statSync(p);
        mtime = st.mtime.toISOString().slice(0, 10);
        if (!a.gross) n = leseZeilen(p, a.spalten).zeilen.length;
      } catch { /* fehlt */ }
      return {
        id: a.id, label: a.label, editierbar: a.editierbar, perLand: a.perLand,
        laender: a.laender ?? null, gross: !!a.gross, hinweis: a.hinweis,
        pfad: relPfad(p), unterData: unterData(a, land), vorhanden: mtime !== null,
        zeilen: n, stand: mtime,
      };
    });
    return NextResponse.json({ land, arten }, { headers: { "cache-control": "no-store" } });
  }

  const a = art(id);
  if (!a) return NextResponse.json({ error: "unbekannte Art" }, { status: 400 });
  if (a.laender && a.perLand && !a.laender.includes(land))
    return NextResponse.json({ error: `nur ${a.laender.join("/")}` }, { status: 400 });

  const p = pfad(a, land);
  if (a.gross) {
    let count = 0, kopf: string[] = [], probe: Record<string, string>[] = [];
    try {
      const raw = fs.readFileSync(p, "utf8");
      const zeilen = raw.split("\n").filter(Boolean);
      count = Math.max(0, zeilen.length - 1);
      const g = leseZeilen(p, a.spalten);
      kopf = g.kopf; probe = g.zeilen.slice(0, 20);
    } catch { /* fehlt */ }
    return NextResponse.json(
      { id: a.id, label: a.label, editierbar: false, gross: true, pfad: relPfad(p),
        spalten: kopf, count, probe, hinweis: a.hinweis },
      { headers: { "cache-control": "no-store" } },
    );
  }

  const { kopf, zeilen } = leseZeilen(p, a.spalten);
  return NextResponse.json(
    { id: a.id, label: a.label, editierbar: a.editierbar, perLand: a.perLand,
      laender: a.laender ?? null, spalten: kopf.length ? kopf : a.spalten, pflicht: a.pflicht,
      zeilen, pfad: relPfad(p), unterData: unterData(a, land), hinweis: a.hinweis,
      wirkung: "Wirkt erst beim naechsten Gold-/Silber-Lauf." },
    { headers: { "cache-control": "no-store" } },
  );
}

export async function POST(req: Request) {
  if (gesperrt()) return NextResponse.json({ error: "not found" }, { status: 404 });
  let body: Record<string, unknown>;
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }

  const a = art(String(body.kind ?? ""));
  if (!a) return NextResponse.json({ error: "unbekannte Art" }, { status: 400 });
  if (!a.editierbar) return NextResponse.json({ error: "nur Ansicht" }, { status: 400 });
  const land = String(body.country ?? "DE").toUpperCase();
  if (!LAND.test(land)) return NextResponse.json({ error: "country ungültig" }, { status: 400 });
  if (a.laender && a.perLand && !a.laender.includes(land))
    return NextResponse.json({ error: `nur ${a.laender.join("/")}` }, { status: 400 });

  const aktion = String(body.action ?? "");
  if (!["append", "delete"].includes(aktion))
    return NextResponse.json({ error: "action ∈ {append,delete}" }, { status: 400 });

  const p = pfad(a, land);

  // Fail-closed: kein Schreiben auf data/, solange ein Lauf denselben Baum benutzt.
  if (unterData(a, land)) {
    const r = spawnSync("bash", ["scripts/laeuft_was.sh"], { cwd: ROOT, timeout: 20_000 });
    if (r.status !== 0) {
      return NextResponse.json(
        { error: "Ein Lauf schreibt gerade nach data/, Kuratierung jetzt gesperrt (fail-closed). Spaeter erneut." },
        { status: 409 },
      );
    }
  }

  const { kopf, zeilen } = leseZeilen(p, a.spalten);
  const spalten = kopf.length ? kopf : a.spalten;

  if (aktion === "delete") {
    const i = Number(body.index);
    if (!Number.isInteger(i) || i < 0 || i >= zeilen.length)
      return NextResponse.json({ error: "index ungültig" }, { status: 400 });
    zeilen.splice(i, 1);
  } else {
    const roh = (body.row ?? {}) as Record<string, unknown>;
    const neu: Record<string, string> = {};
    for (const s of spalten) neu[s] = String(roh[s] ?? "").trim();
    if (a.autoStand && spalten.includes("stand") && !neu.stand) neu.stand = HEUTE();
    for (const s of a.pflicht) if (!neu[s]) return NextResponse.json({ error: `${s} fehlt` }, { status: 400 });
    for (const s of spalten) { const f = feldOk(neu[s]); if (f) return NextResponse.json({ error: `${s}: ${f}` }, { status: 400 }); }
    if (a.enums) for (const [s, erlaubt] of Object.entries(a.enums))
      if (neu[s] && !erlaubt.includes(neu[s])) return NextResponse.json({ error: `${s} muss ∈ {${erlaubt.join(",")}}` }, { status: 400 });
    zeilen.push(neu);
  }

  // Atomar schreiben (tmp + rename) — kein halb geschriebener Stand fuer einen mitlesenden Lauf.
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = p + ".tmp-" + process.pid;
  fs.writeFileSync(tmp, baueCsv(spalten, zeilen), "utf8");
  fs.renameSync(tmp, p);

  return NextResponse.json({ ok: true, zeilen: zeilen.length, pfad: relPfad(p) });
}
