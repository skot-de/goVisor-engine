"use client";

import { useEffect, useState } from "react";

// Ticket #23 §9/§10 — Bausteinbibliothek (Ebene B). Liest die lokal gespeicherten Bausteine
// (localStorage.govisor.blocks, gefüllt vom Kombi-Button der Checkliste) und den Import aus alten
// Angeboten (über /api/blocks-import → PII-Schwärzung in govisor/blocks). Lokal-first; die
// verschlüsselte Supabase-Persistenz (profile_text_blocks) ist die Deploy-Schicht.

type Block = { theme: string; content: string; label?: string; lead_id?: string; saved_at?: string;
  origin?: string; keywords?: string[];
  /** Vergeben, sobald der Baustein auf dem Server liegt. Ohne ihn ist er nur im Browser. */
  id?: string };

/* Erkennungsmerkmal für den Abgleich. Lokale Bausteine haben keine ID — zwei Bausteine mit
 * demselben Thema und demselben Text sind derselbe. Bewusst kein Zeitstempel darin: derselbe
 * Text, zweimal gespeichert, soll nach dem Abgleich EINMAL dastehen. */
const merkmal = (b: Block) => `${b.theme}\u0000${b.content.trim()}`;

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

/**
 * `importOpen`/`onImport` kommen seit 2026-08-15 von AUSSEN — derselbe Grund wie bei den
 * Unternehmens-Reitern: der Knopf ist eine Werkzeugleiste, kein Inhalt, und gehoert in die
 * Bereichsleiste des Rahmens. Damit er dort stehen kann, muss der Zustand eine Ebene hoeher
 * liegen; sonst haette die Leiste keinen Zugriff darauf.
 *
 * Das aufklappende Feld selbst bleibt hier im Inhalt: es ist ein Arbeitsbereich mit
 * Textfeld, kein Werkzeug. In eine 45 px hohe Leiste passt es ohnehin nicht.
 */
export function BausteinLibrary({ importOpen, onImport, theme, onTheme, onThemen }: {
  importOpen: boolean; onImport: (offen: boolean) => void;
  /** Das gewaehlte Thema — gefuehrt von der Seite, weil die Auswahl in der Bereichsleiste
   *  steht und damit ausserhalb dieser Komponente. */
  theme: string;
  onTheme: (t: string) => void;
  /** Meldet die Themen mit Anzahl nach oben, damit die Leiste sie beschriften kann.
   *  Die Zaehlung bleibt hier, weil hier die Bausteine liegen — eine zweite Zaehlung
   *  in der Seite waere eine zweite Wahrheit. */
  onThemen: (liste: { key: string; label: string; anzahl: number }[]) => void;
}) {
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string>("");

  /** Angemeldet und der Server antwortet — nur dann wird überhaupt hochgeschrieben. */
  const [amServer, setAmServer] = useState(false);
  const [hinweis, setHinweis] = useState("");

  /* LOKAL-FIRST, dann abgleichen. Die lokale Liste steht sofort; der Server kommt danach.
   * Umgekehrt (erst laden, dann anzeigen) sähe die Bibliothek bei jedem Aufruf für einen
   * Moment leer aus — und eine leere Bausteinbibliothek liest sich wie Datenverlust. */
  useEffect(() => {
    const lokal = load();
    setBlocks(lokal);
    (async () => {
      try {
        const r = await fetch("/api/blocks");
        const d = await r.json();
        // Ohne Anmeldung antwortet die Middleware mit 401 — dann bleibt alles im Browser.
        if (d.error) return;
        setAmServer(true);
        let ferne: Block[] = d.blocks || [];

        // Erstübernahme: was bisher nur im Browser lag, wandert einmalig hoch. Ohne diesen
        // Schritt wäre die Anmeldung ein Datenverlust — die Bibliothek stünde plötzlich leer.
        const bekannt = new Set(ferne.map(merkmal));
        const nurLokal = lokal.filter((b) => !bekannt.has(merkmal(b)));
        if (nurLokal.length) {
          const p = await fetch("/api/blocks", {
            method: "POST", headers: { "content-type": "application/json" },
            body: JSON.stringify({ blocks: nurLokal.slice(0, 200) }),
          });
          const pd = await p.json();
          if (pd.error) { setHinweis(pd.error); return; }
          ferne = (await (await fetch("/api/blocks")).json()).blocks || [];
        }
        save(ferne); setBlocks(ferne);
        if (d.unlesbar) {
          setHinweis(`${d.unlesbar} Baustein(e) konnten nicht entschlüsselt werden — `
                     + "vermutlich wurde der Hauptschlüssel gewechselt.");
        }
      } catch { /* Server nicht erreichbar → lokal weiterarbeiten */ }
    })();
  }, []);

  const counts: Record<string, number> = {};
  blocks.forEach((b) => { counts[b.theme] = (counts[b.theme] || 0) + 1; });
  const shown = theme ? blocks.filter((b) => b.theme === theme) : blocks;

  // Die Leiste oben braucht dieselben Zahlen. Gemeldet wird nur bei Aenderung des
  // Bestands — sonst laeuft die Seite in eine Endlosschleife aus Rendern und Melden.
  useEffect(() => {
    onThemen([{ key: "", label: "Alle", anzahl: blocks.length },
              ...THEMES.filter(([id]) => counts[id])
                       .map(([id, lbl]) => ({ key: id, label: lbl, anzahl: counts[id] }))]);
  }, [blocks]);   // eslint-disable-line react-hooks/exhaustive-deps

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
      let merged = [...fresh, ...blocks];
      if (amServer) {
        const p = await fetch("/api/blocks", {
          method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ blocks: fresh }),
        });
        const pd = await p.json();
        // ⚠ Der Import darf NICHT verlorengehen, wenn der Server nein sagt. Er bleibt dann
        // lokal, und der Hinweis sagt warum — statt still zu verschwinden.
        if (pd.error) setHinweis(pd.error);
        else merged = (await (await fetch("/api/blocks")).json()).blocks || merged;
      }
      save(merged); setBlocks(merged); setText(""); onImport(false);
      setMsg(`${fresh.length} Bausteine angelegt${d.skipped_personal ? ` · ${d.skipped_personal} Passagen übersprungen (überwiegend Personendaten)` : ""}.`);
    } catch { setMsg("Import fehlgeschlagen."); }
    setBusy(false);
  }

  function removeBlock(i: number) {
    const weg = shown[i];
    const idx = blocks.indexOf(weg);
    const next = blocks.filter((_, k) => k !== idx);
    save(next); setBlocks(next);
    // Auf dem Server wird ARCHIVIERT, nicht gelöscht (§9.2): ein Baustein kann in einem
    // alten Angebot stecken, das später noch zu begründen ist.
    if (amServer && weg?.id) {
      fetch(`/api/blocks?id=${encodeURIComponent(weg.id)}`, { method: "DELETE" }).catch(() => {});
    }
  }

  return (
    <div className="libwrap">
      <div className="sechead">
        <div><h1>Bausteine</h1><p>Eure Textbausteine für Angebote — gehören dem Unternehmen, nicht der einzelnen Person.</p></div>
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
      {hinweis && <div className="ii-msg" style={{ marginBottom: 12 }}>{hinweis}</div>}

      {blocks.length === 0 ? (
        /* LEERZUSTAND: das ZIEL zeigen, nicht die Luecke.
           Vorher stand hier ein umrandeter Kasten von 263x330 px, zu 90 % leer, mit dem
           Text schwebend in der Mitte — das liest sich als „kaputt", nicht als „bereit zum
           Fuellen". Und man erfuhr nirgends, WIE ein Baustein aussieht.
           Jetzt: die zwei Wege als Schritte, daneben zwei Beispielkarten in derselben Form
           wie die echten. Die Beispiele sind ausdruecklich als solche beschriftet — eine
           Vorschau, die man fuer eigene Daten halten koennte, waere eine Luege. */
        <div className="baust-leer">
          <div className="bl-text">
            <h3>Einmal schreiben, immer wieder verwenden</h3>
            <p>Jedes Angebot verlangt dieselben Passagen — Referenzen, Zertifikate,
              Datenschutz, Projektorganisation. Hier sammelt ihr sie einmal und setzt das
              nächste Angebot daraus zusammen.</p>
            <ol className="bl-wege">
              <li>
                <b>Beim Prüfen einer Ausschreibung</b>
                <span>In der Unterlagen-Checkliste „Kopieren &amp; abhaken" antippen — der
                  Textbaustein landet hier, mit Herkunft und Stichworten.</span>
              </li>
              <li>
                <b>Oder aus alten Angeboten</b>
                <span>Text einfügen, goVisor schneidet die wiederverwendbaren Passagen
                  heraus. Personenbezogene Angaben werden dabei ersetzt.</span>
                <button className="btn btn-p" onClick={() => onImport(true)}>
                  Aus alten Angeboten füllen
                </button>
              </li>
            </ol>
          </div>

          <div className="bl-vorschau" aria-hidden="true">
            <div className="bl-vk">So sieht die Bibliothek aus, wenn sie gefüllt ist</div>
            {[
              { t: "Referenzen", m: "aus altem Angebot · 12.03.2026",
                x: "Für die Stadtwerke Musterstadt haben wir zwischen 2023 und 2025 die "
                 + "Wartung von 140 Trafostationen übernommen — Reaktionszeit unter vier "
                 + "Stunden, Verfügbarkeit 99,4 %.",
                k: ["Wartung", "Energie", "SLA"] },
              { t: "Zertifikate & QM", m: "aus Checkliste · Lead 512883_2026",
                x: "Unser Qualitätsmanagement ist nach DIN EN ISO 9001:2015 zertifiziert "
                 + "(Zertifikat-Nr. 12 100 45678 TMS), gültig bis 08/2027.",
                k: ["ISO 9001", "QM"] },
            ].map((b, i) => (
              <div className="bcard bl-muster" key={i}>
                <div className="bh">
                  <div><div className="bt">{b.t}</div><div className="bm">{b.m}</div></div>
                </div>
                <div className="bx">{b.x}</div>
                <div className="bf">{b.k.map((k) => <span className="chip" key={k}>{k}</span>)}</div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="libgrid">
          {/* Die Themenliste stand hier als zweite Spalte — die dritte Bauform fuer
              „Abschnitt waehlen" im selben Produkt. Sie liegt jetzt in der
              Bereichsleiste, wie bei Strategie und Unternehmen. */}
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
