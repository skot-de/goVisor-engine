"use client";

import Link from "next/link";
import { useSprache } from "@/lib/i18n";
import type { Contract, Landing } from "@/lib/outreach";

/* Client-Hälfte der Outreach-Landing (die Server-Hälfte liegt in `page.tsx`).
 *
 * **Warum überhaupt geteilt.** `page.tsx` liest die vorberechnete `outreach.json` vom
 * Dateisystem und muss deshalb Server-Komponente bleiben. Die Oberflächensprache steht
 * aber im `localStorage` des Browsers, und `useSprache` ist ein Hook — auf dem Server
 * gibt es sie schlicht nicht. Also lädt der Server die Daten und reicht sie hier hinein;
 * übersetzt wird ausschließlich in dieser Datei.
 *
 * Nicht übersetzt und mit Absicht: `d.finding.headline`/`.em`, Firmen- und
 * Vergabestellen-Namen, Beträge und Daten — das sind Vergabedaten, keine Oberfläche. */

function Row({ c, gated }: { c: Contract; gated?: boolean }) {
  const { t } = useSprache();
  return (
    <tr>
      <td><div className="fn">{c.titel || t("(ohne Titel)")}</div>
        {gated && <div className="fs">{t("Bindung — Detail im Konto")}</div>}</td>
      <td>{c.buyer}</td>
      <td className="r m">{c.vol ?? "—"}{c.geschaetzt ? " *" : ""}</td>
      <td className={`r m ${c.soon ? "ov-soon" : ""}`}>{c.ende ?? "—"}</td>
    </tr>
  );
}

/** Unbekanntes oder abgelaufenes Token — kein Grund, den Rahmen wegzulassen. */
export function LandingMissing() {
  const { t } = useSprache();
  return (
    <div className="ov-body">
      <div className="ov-topbar"><span className="ov-logo">govisor</span></div>
      <div className="ov-miss">
        <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>{t("Auswertung nicht gefunden")}</h1>
        <p style={{ fontSize: 14, lineHeight: 1.6 }}>{t("Dieser Link ist ungültig oder abgelaufen.")}</p>
      </div>
    </div>
  );
}

export function LandingView({ d, token }: { d: Landing; token: string }) {
  const { t } = useSprache();
  const signup = `/login?t=${encodeURIComponent(token)}`;
  const anyEst = d.vertraege.some((c) => c.geschaetzt) || (d.wettbewerber?.vertraege.some((c) => c.geschaetzt) ?? false);

  return (
    <div className="ov-body">
      <div className="ov-pv">
        <svg viewBox="0 0 24 24"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="2.5" /></svg>
        <span><b>{t("Auswertung für {firma}", { firma: d.name })}</b> {t("— erstellt aus öffentlichen Vergabedaten. Noch kein Konto.")}</span>
        <span className="r"><Link className="ov-pvbtn" href={signup}>{t("Konto anlegen")}</Link></span>
      </div>

      <div className="ov-topbar"><span className="ov-logo">govisor</span><span className="ov-branche">{t("Auswertung")}</span></div>

      <div className="ov-pagepad"><div className="ov-wrap">
        <div className="ov-finding">
          <div className="eyebrow">{t("Auswertung · Stand {datum}", { datum: d.stand })}</div>
          <h1>{d.finding.em
            ? (() => { const [a, b] = d.finding.headline.split(d.finding.em); return <>{a}<em>{d.finding.em}</em>{b}</>; })()
            : d.finding.headline}</h1>
          <div className="src">
            <svg viewBox="0 0 24 24"><path d="M12 8v5M12 17h.01" /><circle cx="12" cy="12" r="9" /></svg>
            {t("Alles aus öffentlichen Vergabebekanntmachungen — keine Daten von Ihnen, kein Konto nötig.")}
          </div>
        </div>

        <div className="ov-kpis">
          <div className="ov-kpi"><div className="k">{t("Zuschläge 36 Monate")}</div><div className="v">{d.kpi.wins36}</div><div className="s">{t("gemessen")}</div></div>
          <div className="ov-kpi"><div className="k">{t("Volumen 36 Monate")}</div><div className="v">{d.kpi.volSum ?? "—"}</div><div className="s">{t("belegte Werte")}</div></div>
          {d.kpi.aus18N > 0 && <div className="ov-kpi"><div className="k">{t("Läuft aus ≤ 18 Monate")}</div><div className="v g">{d.kpi.aus18N}</div><div className="s">{d.kpi.aus18Vol ?? ""}</div></div>}
        </div>

        {d.vertraege.length > 0 && (
          <div className="ov-card">
            <div className="ov-ch"><h2>{t("Ihre laufenden Verträge")}</h2><span className="sub">{t("öffentlich · vollständig")}</span></div>
            <table className="ov-tbl">
              <thead><tr><th>{t("Vertrag")}</th><th>{t("Vergabestelle")}</th><th className="r">{t("Volumen")}</th><th className="r">{t("Ende")}</th></tr></thead>
              <tbody>{d.vertraege.map((c, i) => <Row key={i} c={c} />)}</tbody>
            </table>
          </div>
        )}

        {d.wettbewerber && d.wettbewerber.vertraege.length > 0 && (
          <div className="ov-card">
            <div className="ov-ch"><h2>{t("Ihr Hauptwettbewerber: {firma}", { firma: d.wettbewerber.name.split(" ").slice(0, 3).join(" ") })}</h2>
              <span className="sub">{t("{n} Zuschläge", { n: d.wettbewerber.wins })}</span></div>
            <div className="ov-gatewrap">
              <div className="ov-blur">
                <table className="ov-tbl">
                  <thead><tr><th>{t("Vertrag")}</th><th>{t("Vergabestelle")}</th><th className="r">{t("Volumen")}</th><th className="r">{t("Ende")}</th></tr></thead>
                  <tbody>{d.wettbewerber.vertraege.map((c, i) => <Row key={i} c={c} gated />)}</tbody>
                </table>
              </div>
              <div className="ov-gate"><div className="ov-gatebox">
                <div className="gt">{t("Wo Ihr Wettbewerber angreifbar ist")}</div>
                <p>{t("goVisor zeigt Ihnen, welche Verträge von {firma} auslaufen — mit Vergabestelle, Volumen und Enddatum.",
                      { firma: d.wettbewerber.name.split(" ")[0] })}</p>
                <Link className="ov-btn ov-btn-p" href={signup}>{t("Konto anlegen — kostenlos")}</Link>
              </div></div>
            </div>
          </div>
        )}

        <div className="ov-closing">
          <h3>{t("Diese Auswertung gehört Ihnen")}</h3>
          <p>{t("Mit einem Konto bleibt sie erhalten: Ihre Verträge liegen in der Merkliste, Sie werden vor jedem Auslauf erinnert, und Sie sehen die passenden Ausschreibungen, bevor sie veröffentlicht werden.")}</p>
          <div className="acts">
            <Link className="ov-btn ov-btn-p" href={signup}>{t("Konto anlegen — kostenlos")}</Link>
          </div>
          <div className="fine">{t("Kostenlos dauerhaft nutzbar · keine Zahlungsdaten · Auswertung bereits eingerichtet")}</div>
        </div>
        {anyEst && <div className="ov-legend">{t("* Volumen geschätzt / aus CPV-Median abgeleitet — nicht veröffentlicht.")}</div>}
      </div></div>
    </div>
  );
}
