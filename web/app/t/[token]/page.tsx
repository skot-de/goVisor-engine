import Link from "next/link";
import { loadLanding, type Contract } from "@/lib/outreach";
import "../../outreach.css";

// Outreach-Landing: personalisierte, token-adressierte Auswertung je Zielfirma.
// Öffentlich (kein Konto nötig) — der Einstieg in den Vertriebs-Funnel. On-demand gerendert
// (liest die statische outreach.json), daher serverless-fähig ohne Python.

function Row({ c, gated }: { c: Contract; gated?: boolean }) {
  return (
    <tr>
      <td><div className="fn">{c.titel || "(ohne Titel)"}</div>{gated && <div className="fs">Bindung — Detail im Konto</div>}</td>
      <td>{c.buyer}</td>
      <td className="r m">{c.vol ?? "—"}{c.geschaetzt ? " *" : ""}</td>
      <td className={`r m ${c.soon ? "ov-soon" : ""}`}>{c.ende ?? "—"}</td>
    </tr>
  );
}

export default async function Page({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const d = await loadLanding(token);

  if (!d) {
    return (
      <div className="ov-body">
        <div className="ov-topbar"><span className="ov-logo">govisor</span></div>
        <div className="ov-miss">
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>Auswertung nicht gefunden</h1>
          <p style={{ fontSize: 14, lineHeight: 1.6 }}>Dieser Link ist ungültig oder abgelaufen.</p>
        </div>
      </div>
    );
  }

  const signup = `/login?t=${encodeURIComponent(token)}`;
  const anyEst = d.vertraege.some((c) => c.geschaetzt) || (d.wettbewerber?.vertraege.some((c) => c.geschaetzt) ?? false);

  return (
    <div className="ov-body">
      <div className="ov-pv">
        <svg viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="2.5" /></svg>
        <span><b>Auswertung für {d.name}</b> — erstellt aus öffentlichen Vergabedaten. Noch kein Konto.</span>
        <span className="r"><Link className="ov-pvbtn" href={signup}>Konto anlegen</Link></span>
      </div>

      <div className="ov-topbar"><span className="ov-logo">govisor</span><span className="ov-branche">Auswertung</span></div>

      <div className="ov-pagepad"><div className="ov-wrap">
        <div className="ov-finding">
          <div className="eyebrow">Auswertung · Stand {d.stand}</div>
          <h1>{d.finding.em
            ? (() => { const [a, b] = d.finding.headline.split(d.finding.em); return <>{a}<em>{d.finding.em}</em>{b}</>; })()
            : d.finding.headline}</h1>
          <div className="src">
            <svg viewBox="0 0 24 24"><path d="M12 8v5M12 17h.01" /><circle cx="12" cy="12" r="9" /></svg>
            Alles aus öffentlichen Vergabebekanntmachungen — keine Daten von Ihnen, kein Konto nötig.
          </div>
        </div>

        <div className="ov-kpis">
          <div className="ov-kpi"><div className="k">Zuschläge 36 Monate</div><div className="v">{d.kpi.wins36}</div><div className="s">gemessen</div></div>
          <div className="ov-kpi"><div className="k">Volumen 36 Monate</div><div className="v">{d.kpi.volSum ?? "—"}</div><div className="s">belegte Werte</div></div>
          {d.kpi.aus18N > 0 && <div className="ov-kpi"><div className="k">Läuft aus ≤ 18 Monate</div><div className="v g">{d.kpi.aus18N}</div><div className="s">{d.kpi.aus18Vol ?? ""}</div></div>}
        </div>

        {d.vertraege.length > 0 && (
          <div className="ov-card">
            <div className="ov-ch"><h2>Ihre laufenden Verträge</h2><span className="sub">öffentlich · vollständig</span></div>
            <table className="ov-tbl">
              <thead><tr><th>Vertrag</th><th>Vergabestelle</th><th className="r">Volumen</th><th className="r">Ende</th></tr></thead>
              <tbody>{d.vertraege.map((c, i) => <Row key={i} c={c} />)}</tbody>
            </table>
          </div>
        )}

        {d.wettbewerber && d.wettbewerber.vertraege.length > 0 && (
          <div className="ov-card">
            <div className="ov-ch"><h2>Ihr Hauptwettbewerber: {d.wettbewerber.name.split(" ").slice(0, 3).join(" ")}</h2><span className="sub">{d.wettbewerber.wins} Zuschläge</span></div>
            <div className="ov-gatewrap">
              <div className="ov-blur">
                <table className="ov-tbl">
                  <thead><tr><th>Vertrag</th><th>Vergabestelle</th><th className="r">Volumen</th><th className="r">Ende</th></tr></thead>
                  <tbody>{d.wettbewerber.vertraege.map((c, i) => <Row key={i} c={c} gated />)}</tbody>
                </table>
              </div>
              <div className="ov-gate"><div className="ov-gatebox">
                <div className="gt">Wo Ihr Wettbewerber angreifbar ist</div>
                <p>goVisor zeigt Ihnen, welche Verträge von {d.wettbewerber.name.split(" ")[0]} auslaufen — mit Vergabestelle, Volumen und Enddatum.</p>
                <Link className="ov-btn ov-btn-p" href={signup}>Konto anlegen — kostenlos</Link>
              </div></div>
            </div>
          </div>
        )}

        <div className="ov-closing">
          <h3>Diese Auswertung gehört Ihnen</h3>
          <p>Mit einem Konto bleibt sie erhalten: Ihre Verträge liegen in der Merkliste, Sie werden vor jedem Auslauf erinnert, und Sie sehen die passenden Ausschreibungen, bevor sie veröffentlicht werden.</p>
          <div className="acts">
            <Link className="ov-btn ov-btn-p" href={signup}>Konto anlegen — kostenlos</Link>
          </div>
          <div className="fine">Kostenlos dauerhaft nutzbar · keine Zahlungsdaten · Auswertung bereits eingerichtet</div>
        </div>
        {anyEst && <div className="ov-legend">* Volumen geschätzt / aus CPV-Median abgeleitet — nicht veröffentlicht.</div>}
      </div></div>
    </div>
  );
}
