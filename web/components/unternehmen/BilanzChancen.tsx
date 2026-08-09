"use client";
import { useEffect, useState } from "react";
import { loadBilanz, type BilanzData, type Breakdown } from "@/lib/supabase/bilanz";
import { catalogFor, type CatalogItem } from "@/lib/unternehmen/catalog";
import type { Profil } from "@/lib/supabase/unternehmen";

/* #28 — „Unsere Bilanz" (echte vs. sichtbare Quote aus eigenen Meldungen) und „Chancen"
 * (Anforderungs-Coverage). Kein Duplikat von #10/#25 — verweist dorthin (AC2). */

const eur = (v?: number | null) => (v == null ? "—" : v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio €" : Math.round(v).toLocaleString("de-DE") + " €");

/* ── Reiter Bilanz (§2) ── */
export function BilanzTab() {
  const [data, setData] = useState<BilanzData | null>(null);
  const [loading, setLoading] = useState(true);
  const [noSession, setNoSession] = useState(false);
  useEffect(() => { loadBilanz().then((r) => { if (!r) setNoSession(true); else setData(r.data); setLoading(false); }).catch(() => { setNoSession(true); setLoading(false); }); }, []);

  if (loading) return <p className="un-muted">Lädt …</p>;
  if (noSession || !data) return <p className="un-muted">Bitte anmelden, um die Bilanz zu sehen.</p>;

  const d = data;
  return (
    <div className="un-bilanz">
      {/* Zentrale Kennzahl: echte vs sichtbare Quote */}
      <section className="un-card">
        <div className="un-sec-head"><h2>Echte gegen sichtbare Quote</h2>
          <p className="un-sec-hint">Öffentlich sichtbar sind nur eure Gewinne. Die echte Quote kennt nur, wer die Teilnahmen meldet.</p></div>
        <div className="un-kpi-row">
          <div className="un-kpi"><span className="un-kpi-n">{d.sichtbare_gewinne.toLocaleString("de-DE")}</span><span className="un-kpi-l">sichtbare Gewinne (öffentl.)</span></div>
          <div className="un-kpi"><span className="un-kpi-n">{d.beworben}</span><span className="un-kpi-l">gemeldete Teilnahmen</span></div>
          <div className="un-kpi"><span className="un-kpi-n">{d.gewonnen}</span><span className="un-kpi-l">davon gewonnen</span></div>
          <div className="un-kpi big">
            <span className="un-kpi-n">{d.echte_quote == null ? "—" : d.echte_quote + " %"}</span>
            <span className="un-kpi-l">echte Gewinnquote</span></div>
        </div>
        {d.echte_quote == null
          ? <div className="un-hint-box">Für eine belastbare Quote fehlen noch <strong>{d.fehlend_bis_quote}</strong> Meldungen (ab 10). Meldet weitere Ergebnisse in der Treffergüte.</div>
          : <div className="un-hint-box">Diese Quote beruht auf {d.beworben} gemeldeten Teilnahmen. Verfahren, die ihr nicht gemeldet habt, fehlen — die tatsächliche Quote kann abweichen.</div>}
      </section>

      {/* Die nützlichste Aussage: bekannte vs neue Stellen (§2.3) */}
      {(d.bekannt_vs_neu.bekannt || d.bekannt_vs_neu.neu) && (
        <section className="un-card">
          <div className="un-sec-head"><h2>Wo sich Bewerbungen lohnen</h2></div>
          <div className="un-bd">
            {d.bekannt_vs_neu.bekannt && <BdRow b={d.bekannt_vs_neu.bekannt} />}
            {d.bekannt_vs_neu.neu && <BdRow b={d.bekannt_vs_neu.neu} />}
          </div>
        </section>
      )}

      {/* Aufschlüsselungen (≥5, immer mit Fallzahl) */}
      <BdSection title="Nach Vergabestelle" rows={d.nach_stelle} link="/strategy" linkLabel="→ Vergabestellen in der Strategie" />
      <BdSection title="Nach Auftragsgröße" rows={d.nach_groesse} />

      {/* Verlustgründe */}
      {d.verlustgruende.length > 0 && (
        <section className="un-card">
          <div className="un-sec-head"><h2>Verlustgründe</h2></div>
          <div className="un-bd">{d.verlustgruende.map((v) => (
            <div key={v.grund} className="un-bd-row"><span>{v.grund}</span><span className="un-bd-n">{v.n}×</span></div>))}</div>
        </section>
      )}

      {/* Volumen öffentlicher Aufträge über die Jahre (berechnet, AC6) */}
      {d.volumen_jahre.length > 0 && (
        <section className="un-card">
          <div className="un-sec-head"><h2>Volumen öffentlicher Aufträge</h2>
            <p className="un-sec-hint">Aus euren öffentlichen Zuschlägen berechnet — nicht abgefragt. Volumen nur, wo ein EUR-Wert veröffentlicht wurde.</p></div>
          <VolChart rows={d.volumen_jahre} />
        </section>
      )}
    </div>
  );
}

function BdRow({ b }: { b: Breakdown }) {
  return <div className="un-bd-row"><span>{b.label}</span><span className="un-bd-q">{b.quote} %<em>{b.won}/{b.n}</em></span></div>;
}
function BdSection({ title, rows, link, linkLabel }: { title: string; rows: Breakdown[]; link?: string; linkLabel?: string }) {
  if (rows.length === 0) return null;
  return (
    <section className="un-card">
      <div className="un-sec-head"><h2>{title}</h2></div>
      <div className="un-bd">{rows.slice(0, 8).map((b) => <BdRow key={b.label} b={b} />)}</div>
      {link && <a className="un-link" href={link}>{linkLabel}</a>}
    </section>
  );
}
function VolChart({ rows }: { rows: { jahr: number; wins: number; volumen: number | null }[] }) {
  const max = Math.max(...rows.map((r) => r.volumen || 0), 1);
  return (
    <div className="un-vol">
      {rows.map((r) => (
        <div key={r.jahr} className="un-vol-col">
          <div className="un-vol-bar" style={{ height: `${Math.round(60 * (r.volumen || 0) / max) + 2}px` }} title={r.volumen ? eur(r.volumen) : "kein Wert veröffentlicht"} />
          <span className="un-vol-v">{r.volumen ? eur(r.volumen) : "—"}</span>
          <span className="un-vol-j">{r.jahr}</span>
          <span className="un-vol-w">{r.wins} Zuschl.</span>
        </div>
      ))}
    </div>
  );
}

/* ── Reiter Chancen (§3) ── */
export function ChancenTab({ profil }: { profil: Profil }) {
  const catalog = catalogFor(profil.branchen.cpv);
  type Row = { it: CatalogItem; status: "erfuellt" | "nicht" | "offen" };
  const rows: Row[] = catalog.filter((it) => !it.quelleStammdaten).map((it) => {
    const a = profil.attributes[it.id];
    let status: Row["status"] = "offen";
    if (a && a.zustand !== "abgeleitet") {
      if (a.value === true || (typeof a.value === "string" && a.value.trim() !== "")) status = "erfuellt";
      else if (a.value === false) status = "nicht";
    }
    return { it, status };
  }).sort((a, b) => rank(a.status) - rank(b.status));

  return (
    <div className="un-chancen">
      <section className="un-card">
        <div className="un-sec-head"><h2>Eure Anforderungs-Abdeckung</h2>
          <p className="un-sec-hint">Was euer Segment üblicherweise fordert, mit eurem Status. „Nicht erfüllt" und häufig zuerst — das ist die Investitionsfrage.</p></div>
        <div className="un-chrows">
          {rows.map(({ it, status }) => (
            <div key={it.id} className={`un-chrow ${status}`}>
              <span className="un-chlabel">{it.label}{it.ko && <b className="un-koflag">K.-o.</b>}</span>
              <span className={`un-chstat ${status}`}>{status === "erfuellt" ? "erfüllt" : status === "nicht" ? "nicht erfüllt" : "unbeantwortet"}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Anforderungshäufigkeit im Markt (§3.2) — braucht die Korpus-Analyse (#23). Ehrlich benannt. */}
      <section className="un-card">
        <div className="un-sec-head"><h2>Häufigkeit im Markt</h2>
          <p className="un-sec-hint">Wie oft euer Segment einen Anforderungstyp fordert — aus analysierten Vergabeunterlagen (#23).</p></div>
        <div className="un-hint-box">
          Diese Auswertung nennt <strong>nie</strong> die Ausstattung anderer Firmen — nur, wie oft eine Anforderung
          in euren Verfahren vorkommt. Sie braucht genügend analysierte Unterlagen im Segment; die Korpus-Abdeckung
          reicht dafür aktuell noch nicht (Mindestfallzahl 10). Sie erscheint, sobald genug Verfahren analysiert sind —
          keine Aussage ohne belegte Fallzahl, keine Investitionsempfehlung, nur die Zahl.
        </div>
        <a className="un-link" href="/bausteine">→ Vergabeunterlagen analysieren</a>
      </section>
    </div>
  );
}
function rank(s: string): number { return s === "nicht" ? 0 : s === "offen" ? 1 : 2; }
