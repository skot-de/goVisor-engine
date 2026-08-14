import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

// `ohne` mitzählen: sonst fehlen die CPV-losen Vergaben still in jedem Zähler und in der
// Geo-Aggregation — dieselbe Klasse Fehler wie eine fehlende Route, nur unsichtbarer.
const BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie",
                  "ohne"] as const;

// Lead-Zahl je Grundraum. OHNE ?q: voller Bestand aus branchen.json (Workspace-Zähler).
// MIT ?q=<begriffe>: Treffer je Grundraum für die aktive Textsuche — damit das Branchen-
// menü nicht die Maximalzahlen zeigt, wenn man z. B. "Hamm" sucht (0 bei Bau, 6 bei IT …).

// Such-Korpus je Branche (nur die durchsuchbaren Strings, kleingeschrieben) — beim ersten
// ?q-Request einmal aus den leads-*.json gelesen und modulweit gehalten (überlebt warme
// Invocations). Spiegelt leadText() im Client: Titel+Auftraggeber+Kürzel+Leistung+
// Beschreibung+Stichworte.
let CORPUS: Record<string, string[]> | null = null;
let corpusPromise: Promise<Record<string, string[]>> | null = null;
// Koordinaten je Branche — INDEX-GLEICH zum CORPUS (beide aus derselben leads-<b>.json in
// gleicher Reihenfolge gelesen), damit Text- UND Geo-Filter über denselben Index kombinierbar
// sind. Leads ohne Koordinate tragen null (fallen aus jeder Umkreiszählung).
let GEO: Record<string, ([number, number] | null)[]> | null = null;
let geoPromise: Promise<Record<string, ([number, number] | null)[]>> | null = null;

type RawLead = {
  titel?: string; buyer?: string; buyerShort?: string; natur?: string;
  beschreibung?: string; kw?: { w?: string }[]; lat?: number; lon?: number;
};

function searchText(l: RawLead): string {
  const kw = Array.isArray(l.kw) ? l.kw.map((k) => k?.w || "").join(" ") : "";
  return `${l.titel || ""} ${l.buyer || ""} ${l.buyerShort || ""} ${l.natur || ""} ${l.beschreibung || ""} ${kw}`.toLowerCase();
}

// Großkreis-Distanz (km) — spiegelt haversine() im Client (explorerCore.js).
function haversine(aLat: number, aLon: number, bLat: number, bLon: number): number {
  const R = 6371, toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(bLat - aLat), dLon = toRad(bLon - aLon);
  const s = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(aLat)) * Math.cos(toRad(bLat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(s));
}

async function loadCorpus(): Promise<Record<string, string[]>> {
  if (CORPUS) return CORPUS;
  if (corpusPromise) return corpusPromise;
  corpusPromise = (async () => {
    const out: Record<string, string[]> = {};
    for (const b of BRANCHEN) {
      try {
        const raw = await loadDataFile(`leads-${b}.json`);
        const arr = raw ? (JSON.parse(raw) as RawLead[]) : [];
        out[b] = Array.isArray(arr) ? arr.map(searchText) : [];
      } catch {
        out[b] = [];
      }
    }
    CORPUS = out;
    return out;
  })();
  return corpusPromise;
}

// Koordinaten je Branche, index-gleich zu loadCorpus (gleiche Datei, gleiche Reihenfolge).
async function loadGeo(): Promise<Record<string, ([number, number] | null)[]>> {
  if (GEO) return GEO;
  if (geoPromise) return geoPromise;
  geoPromise = (async () => {
    const out: Record<string, ([number, number] | null)[]> = {};
    for (const b of BRANCHEN) {
      try {
        const raw = await loadDataFile(`leads-${b}.json`);
        const arr = raw ? (JSON.parse(raw) as RawLead[]) : [];
        out[b] = Array.isArray(arr)
          ? arr.map((l) => (typeof l.lat === "number" && typeof l.lon === "number" ? [l.lat, l.lon] : null))
          : [];
      } catch {
        out[b] = [];
      }
    }
    GEO = out;
    return out;
  })();
  return geoPromise;
}

export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams;
  const q = (sp.get("q") || "").trim().toLowerCase();
  const lat = parseFloat(sp.get("lat") || ""), lon = parseFloat(sp.get("lon") || ""), r = parseFloat(sp.get("r") || "");
  const hasGeo = Number.isFinite(lat) && Number.isFinite(lon) && Number.isFinite(r) && r > 0;

  // Ohne Query UND ohne Geo: die vollen Totale (unverändertes Verhalten).
  if (!q && !hasGeo) {
    const json = await loadDataFile("branchen.json");
    return new NextResponse(json ?? "{}", {
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  }

  // Treffer je Branche unter dem aktiven Filter zählen — Text (mehrere Wörter → UND, wie im
  // Client) und/oder Umkreis (Haversine), über denselben Lead-Index kombiniert.
  const terms = q ? q.split(/\s+/).filter(Boolean) : [];
  const corpus = terms.length ? await loadCorpus() : null;
  const geo = hasGeo ? await loadGeo() : null;
  const counts: Record<string, number> = {};
  for (const b of BRANCHEN) {
    const texts = corpus?.[b] || [];
    const coords = geo?.[b] || [];
    const len = Math.max(texts.length, coords.length);
    let n = 0;
    for (let i = 0; i < len; i++) {
      if (terms.length && !terms.every((t) => (texts[i] || "").includes(t))) continue;
      if (hasGeo) { const c = coords[i]; if (!c || haversine(lat, lon, c[0], c[1]) > r) continue; }
      n++;
    }
    counts[b] = n;
  }
  return NextResponse.json(counts, { headers: { "cache-control": "no-store" } });
}
