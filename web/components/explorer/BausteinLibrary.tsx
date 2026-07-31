"use client";

import { useEffect, useState } from "react";

// Ticket #23 §9/§10 — Bausteinbibliothek (Ebene B). Liest die lokal gespeicherten Bausteine
// (localStorage.govisor.blocks, gefüllt vom Kombi-Button der Checkliste) und den Import aus alten
// Angeboten (über /api/blocks-import → PII-Schwärzung in govisor/blocks). Lokal-first; die
// verschlüsselte Supabase-Persistenz (profile_text_blocks) ist die Deploy-Schicht.

type Block = { theme: string; content: string; label?: string; lead_id?: string; saved_at?: string;
  origin?: string; keywords?: string[] };

const THEMES: [string, string][] = [
  ["referenzen", "Referenzen"], ["unternehmensdarstellung", "Unternehmensdarstellung"],
  ["zertifikate_qm", "Zertifikate & QM"], ["datenschutz_avv", "Datenschutz & AVV"],
  ["projektorganisation", "Projektorganisation"], ["personal_qualifikation", "Personal & Qualifikation"],
  ["technische_ausstattung", "Technische Ausstattung"], ["nachhaltigkeit", "Nachhaltigkeit"],
  ["sonstiges", "Sonstiges"],
];
const KEY = "govisor.blocks";

function load(): Block[] {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
}
function save(b: Block[]) { try { localStorage.setItem(KEY, JSON.stringify(b)); } catch { /* voll */ } }

export function BausteinLibrary() {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [theme, setTheme] = useState<string>("");
  const [importOpen, setImportOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string>("");

  useEffect(() => { setBlocks(load()); }, []);

  const counts: Record<string, number> = {};
  blocks.forEach((b) => { counts[b.theme] = (counts[b.theme] || 0) + 1; });
  const shown = theme ? blocks.filter((b) => b.theme === theme) : blocks;

  async function runImport() {
    if (text.trim().length < 40) { setMsg("Zu wenig Text."); return; }
    setBusy(true); setMsg("");
    try {
      const r = await fetch("/api/blocks-import", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const d = await r.json();
      if (d.error) { setMsg(d.error); setBusy(false); return; }
      const fresh: Block[] = (d.blocks || []).map((b: Block) => ({ ...b, origin: "import",
        saved_at: new Date().toISOString() }));
      const merged = [...fresh, ...blocks];
      save(merged); setBlocks(merged); setText(""); setImportOpen(false);
      setMsg(`${fresh.length} Bausteine angelegt${d.skipped_personal ? ` · ${d.skipped_personal} Passagen übersprungen (überwiegend Personendaten)` : ""}.`);
    } catch { setMsg("Import fehlgeschlagen."); }
    setBusy(false);
  }

  function removeBlock(i: number) {
    const idx = blocks.indexOf(shown[i]);
    const next = blocks.filter((_, k) => k !== idx);
    save(next); setBlocks(next);
  }

  return (
    <div className="libwrap">
      <div className="sechead">
        <div><h1>Bausteine</h1><p>Eure Textbausteine für Angebote — gehören dem Unternehmen, nicht der einzelnen Person.</p></div>
        <div style={{ display: "flex", gap: 9 }}>
          <button className="btn btn-s" onClick={() => setImportOpen((v) => !v)}>Aus alten Angeboten importieren</button>
        </div>
      </div>

      {importOpen && (
        <div className="bcard libimport">
          <div className="ii-h">Text aus einem alten Angebot einfügen</div>
          <p className="ii-p">goVisor liest wiederverwendbare Passagen heraus. <b>Personenbezogene Angaben werden automatisch durch Platzhalter ersetzt</b> (z. B. [Projektleitung]); Lebensläufe werden nicht übernommen. Das Original wird nicht gespeichert.</p>
          <textarea className="ta" value={text} onChange={(e) => setText(e.target.value)} placeholder="Absätze aus einem früheren Angebot einfügen …" />
          <div className="ii-f">
            <button className="btn btn-p" disabled={busy} onClick={runImport}>{busy ? "Wird gelesen …" : "Importieren"}</button>
            {msg && <span className="ii-msg">{msg}</span>}
          </div>
        </div>
      )}
      {!importOpen && msg && <div className="ii-msg" style={{ marginBottom: 12 }}>{msg}</div>}

      {blocks.length === 0 ? (
        <div className="empty">
          <div className="eh">Noch keine Bausteine</div>
          <p>Hak in einer Unterlagen-Checkliste „Kopieren &amp; abhaken" an — der Textbaustein landet hier. Oder fülle die Bibliothek aus euren alten Angeboten.</p>
          <button className="btn btn-p" onClick={() => setImportOpen(true)}>Aus alten Angeboten füllen</button>
        </div>
      ) : (
        <div className="libgrid">
          <nav className="themes">
            <a className={theme === "" ? "on" : ""} onClick={() => setTheme("")}>Alle <span>{blocks.length}</span></a>
            {THEMES.filter(([id]) => counts[id]).map(([id, lbl]) => (
              <a key={id} className={theme === id ? "on" : ""} onClick={() => setTheme(id)}>{lbl} <span>{counts[id]}</span></a>
            ))}
          </nav>
          <div>
            {shown.map((b, i) => (
              <div className="bcard" key={i}>
                <div className="bh">
                  <div><div className="bt">{b.label || THEMES.find(([t]) => t === b.theme)?.[1] || "Baustein"}</div>
                    <div className="bm">{b.origin === "import" ? "aus altem Angebot" : (b.lead_id ? "aus Checkliste · Lead " + b.lead_id : "")} {b.saved_at ? "· " + new Date(b.saved_at).toLocaleDateString("de-DE") : ""}</div></div>
                  <button className="btn btn-q" onClick={() => removeBlock(i)}>Archivieren</button>
                </div>
                <div className="bx">{b.content}</div>
                {b.keywords && b.keywords.length > 0 && (
                  <div className="bf">{b.keywords.slice(0, 4).map((k) => <span className="chip" key={k}>{k}</span>)}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
