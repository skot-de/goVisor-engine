import { NextResponse } from "next/server";
import { loadDataFile } from "@/lib/dataSource";

const BRANCHEN = ["it", "bau", "medizin", "beratung", "sicherheit", "energie"] as const;

// Lead-Zahl je Grundraum. OHNE ?q: voller Bestand aus branchen.json (Workspace-Zähler).
// MIT ?q=<begriffe>: Treffer je Grundraum für die aktive Textsuche — damit das Branchen-
// menü nicht die Maximalzahlen zeigt, wenn man z. B. "Hamm" sucht (0 bei Bau, 6 bei IT …).

// Such-Korpus je Branche (nur die durchsuchbaren Strings, kleingeschrieben) — beim ersten
// ?q-Request einmal aus den leads-*.json gelesen und modulweit gehalten (überlebt warme
// Invocations). Spiegelt leadText() im Client: Titel+Auftraggeber+Kürzel+Leistung+
// Beschreibung+Stichworte.
let CORPUS: Record<string, string[]> | null = null;
let corpusPromise: Promise<Record<string, string[]>> | null = null;

type RawLead = {
  titel?: string; buyer?: string; buyerShort?: string; natur?: string;
  beschreibung?: string; kw?: { w?: string }[];
};

function searchText(l: RawLead): string {
  const kw = Array.isArray(l.kw) ? l.kw.map((k) => k?.w || "").join(" ") : "";
  return `${l.titel || ""} ${l.buyer || ""} ${l.buyerShort || ""} ${l.natur || ""} ${l.beschreibung || ""} ${kw}`.toLowerCase();
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

export async function GET(req: Request) {
  const q = (new URL(req.url).searchParams.get("q") || "").trim().toLowerCase();

  // Ohne Query: die vollen Totale (unverändertes Verhalten).
  if (!q) {
    const json = await loadDataFile("branchen.json");
    return new NextResponse(json ?? "{}", {
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  }

  // Mit Query: Treffer je Branche zählen. Mehrere Wörter → UND (wie im Client, Zeile 507).
  const terms = q.split(/\s+/).filter(Boolean);
  const corpus = await loadCorpus();
  const counts: Record<string, number> = {};
  for (const b of BRANCHEN) {
    let n = 0;
    for (const text of corpus[b] || []) {
      if (terms.every((t) => text.includes(t))) n++;
    }
    counts[b] = n;
  }
  return NextResponse.json(counts, { headers: { "cache-control": "no-store" } });
}
