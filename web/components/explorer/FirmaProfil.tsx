"use client";
import { useCallback, useEffect, useRef, useState } from "react";

/* Feature #25 — Firmenprofil. Rollen-agnostische Firmen-Detailseite, KEIN Navigationspunkt:
 * erreichbar aus der Wettbewerbstabelle, vom Amtsinhaber im Lead und vom Gewinner eines
 * Zuschlags (#24). Alle Kennzahlen sind gemessen (scripts/firma_profil.py); wo die Datenlage
 * dünn ist, benennt die Seite die Lage ehrlich statt tragende Zahlen vorzutäuschen. */

type Field = { label: string; pct: number };
type Sit = { buyer: string; leistung: string; auftraege: number; seit: number | null; bindung: string };
type Exp = { leadId: string; titel: string; buyer: string; vol: number | null; ende: string | null; mte: number; bindung: string; soon: boolean };
type Profil = {
  id: string; name: string; confidence: "belegt" | "unsicher"; aehnliche_namen: number | null;
  group_size: number; schwerpunkt: string | null; hauptregion: string | null; now_year: number;
  kpi: {
    wins36: number; wins_total: number; vol_sum: number | null; vol_cov: number;
    vol_avg: number | null; vol_median: number | null; verteidigung: number | null;
    verteidigung_base: number; markt_verteidigung: number; aus18_n: number; aus18_vol: number | null;
  };
  sits: Sit[]; n_vergabestellen: number; expiring: Exp[]; felder: Field[]; regionen: Field[];
  signale: { subcontracting: number; subcontracting_total: number; bietergemeinschaften: number; netzwerk: string };
  error?: string;
};
type Match = { id: string; name: string; wins: number; buyers: number | null; seit: number | null };

const nf = new Intl.NumberFormat("de-DE");
const eur = (v: number | null | undefined): string =>
  v == null ? "—"
  : v >= 1e9 ? (v / 1e9).toFixed(1).replace(".", ",") + " Mrd €"
  : v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio €"
  : nf.format(Math.round(v)) + " €";

const bindTag = (b: string): string =>
  b === "sehr fest" || b === "fest" ? "warn" : b === "schwach" ? "ok" : "";

const Icon = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24"><path d={d} /></svg>
);
const I_ARROW = "M4 12h16M14 6l6 6-6 6";
const I_INFO = "M12 8v5M12 17h.01";
const I_LOCK = "M8 10V7a4 4 0 018 0v3";

export function FirmaProfil() {
  const [id, setId] = useState<string | null>(null);
  const [data, setData] = useState<Profil | null>(null);
  const [loading, setLoading] = useState(false);
  const [q, setQ] = useState("");
  const [matches, setMatches] = useState<Match[]>([]);
  const [watched, setWatched] = useState(false);
  const deb = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Deep-Link ?id= beim Mount + bei Zurück/Vor
  useEffect(() => {
    const read = () => setId(new URLSearchParams(window.location.search).get("id"));
    read();
    window.addEventListener("popstate", read);
    return () => window.removeEventListener("popstate", read);
  }, []);

  // Profil laden, sobald eine Firma gewählt ist
  useEffect(() => {
    if (!id) { setData(null); return; }
    setLoading(true);
    fetch(`/api/firma?id=${encodeURIComponent(id)}`)
      .then((r) => r.json()).then(setData).catch(() => setData({ error: "Profil nicht ladbar" } as Profil))
      .finally(() => setLoading(false));
    try {
      const w = JSON.parse(localStorage.getItem("govisor.watchFirms") || "[]");
      setWatched(Array.isArray(w) && w.includes(id));
    } catch { setWatched(false); }
  }, [id]);

  const search = useCallback((val: string) => {
    setQ(val);
    if (deb.current) clearTimeout(deb.current);
    if (val.trim().length < 2) { setMatches([]); return; }
    deb.current = setTimeout(() => {
      fetch(`/api/entity-search?q=${encodeURIComponent(val)}`)
        .then((r) => r.json()).then((d) => setMatches(d.matches || [])).catch(() => setMatches([]));
    }, 180);
  }, []);

  const open = (fid: string) => {
    const u = new URL(window.location.href);
    u.searchParams.set("id", fid);
    window.history.pushState({}, "", u);
    setId(fid);
    setMatches([]); setQ("");
  };

  const toggleWatch = () => {
    if (!id) return;
    try {
      const w = new Set<string>(JSON.parse(localStorage.getItem("govisor.watchFirms") || "[]"));
      if (w.has(id)) w.delete(id); else w.add(id);
      localStorage.setItem("govisor.watchFirms", JSON.stringify([...w]));
      setWatched(w.has(id));
    } catch { /* ignore */ }
  };

  // ---- Picker (keine Firma gewählt) ----
  if (!id) {
    return (
      <div className="fp-wrap">
        <div className="fp-picker">
          <h1>Firmenprofil</h1>
          <p>Eine Detailseite, kein Navigationspunkt. Sonst erreichbar aus der Wettbewerbstabelle,
            vom Amtsinhaber im Lead und vom Gewinner eines Zuschlags. Hier zum Nachschlagen: Firma suchen.</p>
          <div className="fp-search">
            <svg viewBox="0 0 24 24" style={{ width: 15, height: 15, stroke: "currentColor", fill: "none", strokeWidth: 1.8, color: "var(--ink-400)" }}>
              <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
            </svg>
            <input autoFocus placeholder="Firma suchen — Name" value={q} onChange={(e) => search(e.target.value)} />
          </div>
          {matches.length > 0 && (
            <div className="fp-results">
              {matches.map((m) => (
                <button key={m.id} className="fp-res" onClick={() => open(m.id)}>
                  <span>
                    <span className="fn">{m.name}</span>
                    <span className="fs">{m.buyers ? `${m.buyers} Auftraggeber` : ""}{m.seit ? ` · seit ${m.seit}` : ""}</span>
                  </span>
                  <span className="fw">{nf.format(m.wins)} Zuschläge</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  if (loading || !data) return <div className="fp-load">Lade Firmenprofil …</div>;
  if (data.error) return (
    <div className="fp-wrap"><div className="fp-picker">
      <div className="fp-note fp-note-w"><Icon d={I_INFO} /><div>{data.error}</div></div>
      <p style={{ marginTop: 14 }}><a href="/firma" style={{ color: "var(--signal-deep)" }}>← andere Firma suchen</a></p>
    </div></div>
  );

  const k = data.kpi;
  const unsicher = data.confidence === "unsicher";
  const thin = k.wins_total < 8;               // Schwelle für belastbaren Schwerpunkt (§ f2)

  return (
    <div className="fp-wrap">
      <div className="fp-crumb"><a href="/leads">Akquise</a> › Firmenprofil › {data.name}</div>

      {/* Kopf */}
      <div className="fp-head">
        <div>
          <h1>{data.name}</h1>
          <div className="fp-meta">
            {unsicher
              ? <span className="fp-tag warn"><i />Zuordnung unsicher</span>
              : <span className="fp-tag ok"><i />Zuordnung gesichert</span>}
            {data.group_size > 1 && <span className="fp-tag">Konzern · {data.group_size} Gesellschaften zusammengefasst</span>}
            {data.schwerpunkt && <span className="fp-tag">Schwerpunkt {data.schwerpunkt}{data.hauptregion ? ` · ${data.hauptregion}` : ""}</span>}
          </div>
        </div>
        <div className="fp-acts">
          <button className={`fp-btn fp-btn-s fp-btn-sm`} onClick={toggleWatch}>{watched ? "✓ Beobachtet" : "Beobachten"}</button>
        </div>
      </div>

      {/* Ehrlichkeitsbanner bei unsicherer Zuordnung */}
      {unsicher && (
        <div className="fp-note fp-note-w" style={{ marginBottom: 16 }}>
          <Icon d={I_INFO} />
          <div><b>Diese Firma ist nicht eindeutig zuzuordnen.</b> Im Vergaberegister gibt es
            {data.aehnliche_namen && data.aehnliche_namen > 1 ? ` ${data.aehnliche_namen} ähnliche Namen` : " ähnliche Namen"} an
            unterschiedlichen Orten. Die Zahlen unten beziehen sich auf die wahrscheinlichste
            Zuordnung und können Aufträge anderer Gesellschaften enthalten.</div>
        </div>
      )}

      {/* KPI-Leiste */}
      <div className="fp-kpis">
        <div className="fp-kpi"><div className="k">Zuschläge 36 Monate</div><div className="v">{nf.format(k.wins36)}</div><div className="s">gemessen</div></div>
        <div className="fp-kpi"><div className="k">Volumen gesamt</div><div className="v">{eur(k.vol_sum)}</div><div className="s">{k.vol_sum ? `davon ${k.vol_cov} % mit echtem Wert` : "kein Wert veröffentlicht"}</div></div>
        <div className="fp-kpi"><div className="k">Ø Auftragswert</div><div className="v">{eur(k.vol_avg)}</div><div className="s">{k.vol_median ? `Median ${eur(k.vol_median)}` : "zu wenig Daten"}</div></div>
        <div className="fp-kpi"><div className="k">Verteidigungsquote</div>
          <div className={`v ${k.verteidigung != null && k.verteidigung > k.markt_verteidigung ? "warnc" : ""}`}>{k.verteidigung != null ? `${k.verteidigung} %` : "—"}</div>
          <div className="s">{k.verteidigung != null ? `Markt ${k.markt_verteidigung} %` : "keine Nachfolge auswertbar"}</div></div>
        <div className="fp-kpi"><div className="k">Läuft aus ≤ 18 Monate</div><div className="v okc">{nf.format(k.aus18_n)}</div><div className="s">{k.aus18_vol ? eur(k.aus18_vol) : "—"}</div></div>
      </div>

      {/* Verteidigungs-Deutung (nur wenn belastbar) */}
      {k.verteidigung != null && (
        <div className="fp-note fp-note-g" style={{ marginBottom: 14 }}>
          <Icon d={I_ARROW} />
          <div><b>{data.name} verteidigt {k.verteidigung > k.markt_verteidigung ? "überdurchschnittlich" : "unterdurchschnittlich"}.</b> {k.verteidigung} % der
            Verträge, die auslaufen, holt das Unternehmen zurück — marktüblich sind {k.markt_verteidigung} %.
            {k.verteidigung > k.markt_verteidigung ? " Angriffe lohnen dort, wo die Bindung schwach ist." : " Hier sind auslaufende Verträge eher angreifbar."}
            <div className="fp-mini">Basis: {k.verteidigung_base} auswertbare Nachfolgen · head_to_head</div></div>
        </div>
      )}

      {/* Wo festsitzt */}
      {data.sits.length > 0 && (
        <div className="fp-card">
          <div className="fp-ch"><h2>Wo {data.name.split(" ")[0]} festsitzt</h2><span className="sub">{data.n_vergabestellen} Vergabestellen</span></div>
          <div className="fp-cb tight">
            <table className="fp-tbl">
              <thead><tr><th>Vergabestelle</th><th>Leistung</th><th className="r">Aufträge</th><th className="r">seit</th><th className="r">Bindung</th></tr></thead>
              <tbody>
                {data.sits.map((s, i) => (
                  <tr key={i}>
                    <td><div className="fn">{s.buyer}</div></td>
                    <td>{s.leistung}</td>
                    <td className="r m">{nf.format(s.auftraege)}</td>
                    <td className="r m">{s.seit ?? "—"}</td>
                    <td className="r"><span className={`fp-tag ${bindTag(s.bindung)}`}>{s.bindung}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Was ausläuft (Pro) */}
      <div className="fp-card">
        <div className="fp-ch"><h2>Was bei {data.name.split(" ")[0]} ausläuft</h2><span className="fp-pro">Pro</span><span className="sub">nächste 24 Monate</span></div>
        <div className="fp-cb tight">
          {data.expiring.length > 0 ? (
            <table className="fp-tbl">
              <thead><tr><th>Vertrag</th><th>Vergabestelle</th><th className="r">Volumen</th><th className="r">Ende</th></tr></thead>
              <tbody>
                {data.expiring.map((e, i) => (
                  <tr key={i}>
                    <td><div className="fn">{e.titel}</div><div className="fs">{e.bindung}</div></td>
                    <td>{e.buyer}</td>
                    <td className="r m">{eur(e.vol)}</td>
                    <td className={`r m ${e.soon ? "fp-soon" : "fp-later"}`}>{e.ende ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="fp-empty">Kein auslaufender Vertrag in den nächsten 24 Monaten bekannt.<br />
              <span style={{ color: "var(--ink-400)", fontSize: 12 }}>Auslauf entsteht nur, wo ein Vertragsende in den Daten steht.</span></div>
          )}
        </div>
      </div>

      <div className="fp-grid2">
        {/* Kopf an Kopf (Pro) — ohne eigenes Profil ehrlich leer */}
        <div className="fp-card">
          <div className="fp-ch"><h2>Kopf an Kopf</h2><span className="fp-pro">Pro</span></div>
          <div className="fp-cb">
            <div className="fp-empty">Noch keine gemeinsamen Verfahren bekannt.<br />
              <span style={{ color: "var(--ink-400)", fontSize: 12 }}>Meldet ihr eure Teilnahmen im Cockpit, entsteht dieser Vergleich mit der Zeit — aus euren Meldungen und den öffentlichen Zuschlägen dieser Firma.</span></div>
          </div>
        </div>

        {/* Wo stark */}
        <div className="fp-card">
          <div className="fp-ch"><h2>Wo {data.name.split(" ")[0]} stark ist</h2></div>
          <div className="fp-cb">
            {thin || data.felder.length === 0 ? (
              <div className="fp-empty">Aus {nf.format(k.wins_total)} Aufträgen lässt sich kein belastbarer Schwerpunkt ableiten.<br />
                <span style={{ color: "var(--ink-400)", fontSize: 12 }}>Ab etwa 8 Aufträgen zeigt goVisor eine Verteilung.</span></div>
            ) : (
              <>
                <div className="fp-bars">
                  {data.felder.map((f, i) => (
                    <div className="fp-brow" key={i}><span>{f.label.length > 26 ? f.label.slice(0, 25) + "…" : f.label}</span>
                      <div className="fp-btrack"><i style={{ width: f.pct + "%" }} /></div><span className="bv">{f.pct} %</span></div>
                  ))}
                </div>
                {data.regionen.length > 0 && <>
                  <div style={{ height: 1, background: "var(--line-2, #eef0ef)", margin: "14px 0" }} />
                  <div className="fp-bars">
                    {data.regionen.map((r, i) => (
                      <div className="fp-brow" key={i}><span>{r.label}</span>
                        <div className="fp-btrack"><i className="alt" style={{ width: r.pct + "%" }} /></div><span className="bv">{r.pct} %</span></div>
                    ))}
                  </div>
                </>}
              </>
            )}
          </div>
        </div>
      </div>

      {/* Weitere Signale */}
      <div className="fp-card">
        <div className="fp-ch"><h2>Weitere Signale</h2></div>
        <div className="fp-cb">
          <div className="fp-grid2" style={{ gap: 20 }}>
            <div className="fp-siglist">
              <div className="fp-sigrow"><span>Unterauftragsvergabe geregelt</span><span className="m">{data.signale.subcontracting} von {data.signale.subcontracting_total}</span></div>
              <div className="fp-sigrow"><span>Bietergemeinschaften</span><span className="m">{data.signale.bietergemeinschaften}</span></div>
              <div className="fp-sigrow"><span>Netzwerk</span><span style={{ color: "var(--ink-400)" }}>{data.signale.netzwerk}</span></div>
            </div>
            <div>
              <div className="fp-note fp-note-n" style={{ height: "100%" }}>
                <Icon d={I_INFO} />
                <div>{data.signale.subcontracting > data.signale.subcontracting_total / 3
                  ? `${data.name.split(" ")[0]} vergibt bei einem Teil der Aufträge Unteraufträge geregelt — mögliche Anknüpfung für ergänzende Leistungen.`
                  : `${data.name.split(" ")[0]} vergibt selten Unteraufträge weiter — hier ist eher Wettbewerb als Zusammenarbeit zu erwarten.`}
                  <div className="fp-mini">Abgeleitet · „geregelt" heißt: im Verfahren vorgesehen, kein Hinweis auf konkreten Bedarf</div></div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="fp-note fp-note-n">
        <svg viewBox="0 0 24 24"><rect x="4" y="10" width="16" height="10" rx="2" /><path d={I_LOCK} /></svg>
        <div>Alle Angaben stammen aus öffentlichen Vergabebekanntmachungen. goVisor zeigt keine Daten
          anderer Nutzer, keine Preise und keine Personen.</div>
      </div>
    </div>
  );
}
