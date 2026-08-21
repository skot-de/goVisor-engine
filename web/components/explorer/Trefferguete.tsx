"use client";
import { useEffect, useMemo, useState } from "react";
import { loadProfile, saveProfile } from "@/lib/supabase/auth";
import { parseWert } from "@/lib/explorerCore";
import { loadDeclarations, declare, confirmDeclarations, needsConfirmation, ageMonths, type Declaration } from "@/lib/supabase/declarations";
import { loadOutcomes, reportOutcome, removeOutcome, computeBilanz, type UserOutcome, type OutcomeResult, type LossReason } from "@/lib/supabase/outcomes";
import { useSprache } from "@/lib/i18n";
import "./trefferguete.css";

/* Feature #11 „Treffergüte" — Sektion im Strategie-Bereich, Gruppe „Wir".
 * Block 1: offene Angaben nach gemessener Wirkung (§4.1/§7). Block 2: gemessen vs. erklärt +
 * „Stimmt so" (§4.2). Block 3: privates Tracking + Reziprozität (§4.3). Block 4: Grenzen (§4.4).
 * KEIN Prozentscore, keine Gamifizierung (§3, AC1). */

type Lead = Record<string, unknown>;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Profile = any;

const eur = (v?: number | null) => (v == null ? "—" : v >= 1e6 ? (v / 1e6).toFixed(1).replace(".", ",") + " Mio €" : Math.round(v).toLocaleString("de-DE") + " €");
const MIN_AFFECTED = 3;            // §7.4 Untergrenze für Block 1
const BUERG_QUOTE = 0.05;

function leadValue(l: Lead): number | null {
  const v = (l as { volumen?: { wert?: string } }).volumen?.wert;
  return v ? (parseWert(v) ?? null) : null;
}
function fordertBuergschaft(l: Lead): boolean {
  const a = (l as { aufwand?: { buergschaft?: string } }).aufwand;
  if (a?.buergschaft && /^ja/i.test(String(a.buergschaft))) return true;
  return !!(l as { bgForm?: unknown }).bgForm;
}

type Gap = { key: string; label: string; affected: number; text: string; kind: "buerg" | "betrag"; };

// §7 Wirkungsberechnung — betroffene Lead-Menge je offener Angabe. Immer „betrifft N Leads" (AC5).
// `pre` = nächtlich vorberechnete Werte (user_gap_effects, #11 §7) — bevorzugt, sonst On-Demand.
// `label`/`text` bleiben hier UNübersetzt (Modul-Ebene, sonst friert die Sprache ein) — sie sind
// die Übersetzungsschlüssel und werden erst an der Render-Stelle durch `t()` geschickt.
function computeGaps(leads: Lead[], p: Profile, pre?: Record<string, number>): Gap[] {
  if (!p) return [];
  const gaps: Gap[] = [];
  // Bürgschaftsrahmen (§4.1 Beispiel): Leads fordern Bürgschaft, Rahmen nicht hinterlegt.
  if (p.buergschaft == null) {
    const n = pre?.buergschaft ?? leads.filter(fordertBuergschaft).length;
    if (n >= MIN_AFFECTED) gaps.push({ key: "buergschaft", label: "Bürgschaftsrahmen", affected: n, kind: "buerg",
      text: "{n} eurer Leads fordern eine Bürgschaft. Ohne die Höhe, die eure Bank stellt, können wir nicht prüfen, welche davon für euch in Frage kommen." });
  }
  // Größter Auftrag allein (§4.1 Beispiel): Leads über einer hohen Schwelle, Alleingrenze unbekannt.
  if (p.maxAlleine == null) {
    const SCHWELLE = 2_000_000;
    const n = pre?.maxAlleine ?? leads.filter((l) => { const v = leadValue(l); return v != null && v > SCHWELLE; }).length;
    if (n >= MIN_AFFECTED) gaps.push({ key: "maxAlleine", label: "Größter Auftrag, den ihr allein stemmt", affected: n, kind: "betrag",
      text: "{n} Leads liegen über 2 Mio €. Wir wissen nicht, ob das für euch allein realistisch ist oder nur mit Partner." });
  }
  return gaps.sort((a, b) => b.affected - a.affected);   // §4.1 nach betroffener Anzahl
}

const BUERG_BANDS: { label: string; v: number }[] = [
  { label: "bis 50.000 €", v: 50_000 }, { label: "bis 250.000 €", v: 250_000 },
  { label: "bis 1 Mio €", v: 1_000_000 }, { label: "darüber", v: 5_000_000 },
];

export function Trefferguete({ aktiveBranche }: { aktiveBranche: string }) {
  const { t } = useSprache();
  const [loading, setLoading] = useState(true);
  const [noSession, setNoSession] = useState(false);
  const [profile, setProfile] = useState<Profile>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [decls, setDecls] = useState<Declaration[]>([]);
  const [outcomes, setOutcomes] = useState<UserOutcome[]>([]);
  const [preGaps, setPreGaps] = useState<Record<string, number> | undefined>(undefined);   // §7 vorberechnet
  const [effect, setEffect] = useState<string | null>(null);   // §7.3 einmalige Wirkungsmeldung

  async function reloadAll() {
    const [pr, dc, oc] = await Promise.all([loadProfile().catch(() => null), loadDeclarations().catch(() => []), loadOutcomes().catch(() => [])]);
    setProfile(pr); setDecls(dc); setOutcomes(oc);
  }
  useEffect(() => {
    (async () => {
      const pr = await loadProfile().catch(() => null);
      if (pr === null) {
        // eingeloggt? loadProfile gibt null bei fehlender Session ODER leerem Profil — unterscheiden:
        const { createClient } = await import("@/lib/supabase/client");
        const { data: { user } } = await createClient().auth.getUser();
        if (!user) { setNoSession(true); setLoading(false); return; }
      }
      const [dc, oc] = await Promise.all([loadDeclarations().catch(() => []), loadOutcomes().catch(() => [])]);
      setProfile(pr); setDecls(dc); setOutcomes(oc);
      // Nächtlich vorberechnete Lücken-Wirkung (user_gap_effects) laden — bevorzugt vor On-Demand (§7).
      try {
        const { createClient } = await import("@/lib/supabase/client");
        const { data } = await createClient().from("user_gap_effects").select("gap_key, affected_leads");
        if (Array.isArray(data) && data.length) setPreGaps(Object.fromEntries(data.map((r: { gap_key: string; affected_leads: number }) => [r.gap_key, r.affected_leads])));
      } catch { /* Fallback: On-Demand-Rechnung */ }
      try { const r = await fetch(`/api/leads?branche=${encodeURIComponent(aktiveBranche)}`); const d = await r.json(); setLeads(Array.isArray(d?.leads) ? d.leads : Array.isArray(d) ? d : []); }
      catch { setLeads([]); }
      setLoading(false);
    })();
  }, [aktiveBranche]);

  const gaps = useMemo(() => computeGaps(leads, profile, preGaps), [leads, profile, preGaps]);

  // Inline-Erfassung (§4.1): Engine-Profilfeld setzen → Liste ändert sich sofort (AC6).
  async function fillGap(gap: Gap, value: number) {
    if (!profile) return;
    const before = gap.affected;
    const next = { ...profile, [gap.key]: value };
    const r = await saveProfile(next);
    if (r.ok) {
      // zusätzlich als Angabe protokollieren (einheitlicher Bestand §8.1)
      await declare({ kind: gap.key === "buergschaft" ? "guarantee" : "capacity", key: gap.key, value, source: "trefferguete" });
      setProfile(next);
      const after = computeGaps(leads, next).find((g) => g.key === gap.key)?.affected ?? 0;
      setEffect(t("{feld} hinterlegt. {n} Leads ändern damit ihre Relevanzstufe.", { feld: t(gap.label), n: before - after }));
      await reloadAll();
    }
  }

  if (loading) return <div className="tg-wrap"><p className="tg-muted">{t("Lädt …")}</p></div>;
  if (noSession) return <div className="tg-wrap"><p className="tg-muted">{t("Bitte anmelden, um die Treffergüte zu sehen.")}</p></div>;

  const zuBestaetigen = needsConfirmation(decls);

  return (
    <div className="tg-wrap">
      <div className="tg-head">
        <h4>{t("Treffergüte")}</h4>
        <p className="st-frage">{t("Warum passt manches nicht, und was ändert das?")}</p>
        <p className="tg-count">{gaps.length === 1
          ? t("{leads} Leads in eurer Liste · {n} offene Angabe mit spürbarer Wirkung", { leads: leads.length, n: gaps.length })
          : t("{leads} Leads in eurer Liste · {n} offene Angaben mit spürbarer Wirkung", { leads: leads.length, n: gaps.length })}</p>
      </div>

      {effect && <div className="tg-effect">{effect}</div>}

      {/* Block 1 — Was eure Liste jetzt ändern würde */}
      <section className="tg-block">
        <h5>{t("Was eure Liste jetzt ändern würde")}</h5>
        {!profile ? (
          <p className="tg-muted">{t("Noch kein Profil hinterlegt. Legt Schwerpunkte und Regionen an, dann rechnen wir die Wirkung offener Angaben gegen eure Liste.")}</p>
        ) : gaps.length === 0 ? (
          <p className="tg-muted">{t("Keine offenen Angaben mit spürbarer Wirkung. Was jetzt noch streut, liegt an der Datenlage der Vergabestellen (siehe unten).")}</p>
        ) : gaps.map((g) => (
          <div key={g.key} className="tg-gap">
            <div className="tg-gap-h"><span className="tg-gap-l">{t(g.label)}</span><span className="tg-gap-n">{t("betrifft {n} Leads", { n: g.affected })}</span></div>
            <p className="tg-gap-t">{t(g.text, { n: g.affected })}</p>
            {g.kind === "buerg"
              ? <div className="tg-pills">{BUERG_BANDS.map((b) => <button key={b.v} onClick={() => fillGap(g, b.v)}>{t(b.label)}</button>)}</div>
              : <BetragInput onSet={(v) => fillGap(g, v)} />}
          </div>
        ))}
      </section>

      {/* Block 2 — Was wir über euch wissen */}
      <section className="tg-block">
        <h5>{t("Was wir über euch wissen")}</h5>
        <GemessenErklaert profile={profile} decls={decls} zuBestaetigen={zuBestaetigen} onConfirm={async () => { await confirmDeclarations(); await reloadAll(); }} />
      </section>

      {/* Block 3 — Was ihr freischaltet: privates Tracking + Reziprozität */}
      <section className="tg-block">
        <h5>{t("Was ihr freischaltet")}</h5>
        <PrivatesTracking outcomes={outcomes} onChange={reloadAll} />
      </section>

      {/* Block 4 — Was wir nicht verbessern können */}
      <section className="tg-block tg-limits">
        <h5>{t("Was wir nicht verbessern können")}</h5>
        <table className="tg-limtab"><tbody>
          <tr><td>{t("Kein Auftragswert veröffentlicht")}</td><td>{t("35 % der Vergaben")}</td></tr>
          <tr><td>{t("Ausschreibung nicht mit Zuschlag verknüpfbar")}</td><td>49 %</td></tr>
          <tr><td>{t("Unterlegene Bieter nie veröffentlicht")}</td><td>{t("alle")}</td></tr>
          <tr><td>{t("Eignungsanforderungen nur im Fließtext")}</td><td>{t("ca. 63 %")}</td></tr>
        </tbody></table>
        <p className="tg-muted">{t("Daran ändert keine Angabe etwas. Wir schätzen an diesen Stellen nicht, sondern lassen sie leer.")}</p>
      </section>
    </div>
  );
}

function BetragInput({ onSet }: { onSet: (v: number) => void }) {
  const { t } = useSprache();
  const [v, setV] = useState("");
  function commit() { const n = parseWert(v) ?? Number(v.replace(/[^\d]/g, "")); if (n) onSet(n); }
  return (
    <div className="tg-betrag">
      <input inputMode="numeric" placeholder={t("Betrag in €")} value={v} onChange={(e) => setV(e.target.value)} onKeyDown={(e) => e.key === "Enter" && commit()} />
      <button onClick={commit}>{t("übernehmen")}</button>
    </div>
  );
}

/* Block 2 — gemessen (aus Zuschlägen, im Profil) vs. erklärt (user_declarations) + „Stimmt so". */
function GemessenErklaert({ profile, decls, zuBestaetigen, onConfirm }: { profile: Profile; decls: Declaration[]; zuBestaetigen: Declaration[]; onConfirm: () => void }) {
  const { t } = useSprache();
  const felder: string[] = (profile?.cpvLabels || []).slice(0, 6);
  const regionen: string[] = (profile?.regionLabels || []);
  return (
    <div className="tg-ge">
      <div className="tg-ge-col">
        <span className="tg-ge-t">{t("Gemessen")} <em>{t("aus euren gewonnenen Vergaben")}</em></span>
        {felder.length === 0 && regionen.length === 0
          ? <p className="tg-muted">{t("Noch keine Historie zugeordnet, das Profil funktioniert auch ohne.")}</p>
          : <ul className="tg-ge-list">
              {felder.map((f) => <li key={f}>{f}</li>)}
              {regionen.length > 0 && <li>{t("Regionen")}: {regionen.join(", ")}</li>}
              {profile?.volMin != null && <li>{t("Volumenspanne ab {wert}", { wert: eur(profile.volMin) })}</li>}
            </ul>}
      </div>
      <div className="tg-ge-col">
        <span className="tg-ge-t">{t("Erklärt")} <em>{t("von euch angegeben")}</em></span>
        {decls.length === 0
          ? <p className="tg-muted">{t("Noch nichts erklärt. Offene Angaben oben füllen den Bestand.")}</p>
          : <ul className="tg-ge-list">
              {decls.map((d) => {
                const m = ageMonths(d);
                return <li key={`${d.kind}:${d.key}`}>{d.key} {typeof d.value === "number" ? `· ${eur(d.value)}` : d.value === true ? `· ${t("ja")}` : ""}{m != null && m >= 6 && <span className="tg-old" title={t("seit {n} Monaten unbestätigt", { n: m })}> ⚠</span>}</li>;
              })}
            </ul>}
        {zuBestaetigen.length > 0 && (
          <div className="tg-confirm">
            <span>{zuBestaetigen.length === 1
              ? t("Stand älter als 6 Monate, {n} Angabe. Stimmt das noch?", { n: zuBestaetigen.length })
              : t("Stand älter als 6 Monate, {n} Angaben. Stimmt das noch?", { n: zuBestaetigen.length })}</span>
            <button onClick={onConfirm}>{t("Stimmt so, alle bestätigen")}</button>
          </div>
        )}
      </div>
    </div>
  );
}

/* Block 3 §4.3.0 — der Eigenwert zuerst: privates Bewerbungs-Tracking, nützt ohne Gegenpool.
 * §4.3.1 Reziprozität als zweite Stufe (ehrlich leer, solange der Pool dünn ist). AC11. */
function PrivatesTracking({ outcomes, onChange }: { outcomes: UserOutcome[]; onChange: () => Promise<void> }) {
  const { t } = useSprache();
  const [form, setForm] = useState(false);
  const b = useMemo(() => computeBilanz(outcomes), [outcomes]);
  return (
    <div className="tg-track">
      <p className="tg-track-lead">{t("Ein privater Überblick über eure Bewerbungen. Beworben, gewonnen, verloren. Nur für euch sichtbar, unabhängig von anderen.")}</p>

      <div className="tg-bilanz">
        <div><span className="tg-b-n">{b.beworben}</span><span className="tg-b-l">{t("beworben")}</span></div>
        <div><span className="tg-b-n">{b.gewonnen}</span><span className="tg-b-l">{t("gewonnen")}</span></div>
        <div><span className="tg-b-n">{b.verloren}</span><span className="tg-b-l">{t("verloren")}</span></div>
        <div><span className="tg-b-n">{b.quote == null ? "—" : b.quote + " %"}</span><span className="tg-b-l">{t("Quote")}</span></div>
        <div><span className="tg-b-n">{eur(b.volumen_gewonnen)}</span><span className="tg-b-l">{t("Volumen gewonnen")}</span></div>
      </div>

      <div className="tg-recip">
        <span className="tg-ge-t">{t("Wettbewerbsdaten")} <em>{t("{n} von 3 Meldungen", { n: b.gemeldet })}</em></span>
        <p className="tg-muted">{t("Meldet ihr eure Ergebnisse, seht ihr ab 3 Meldungen die Wettbewerbsmenge eurer Vergabestellen, ab 10 eure Rangverteilung im Marktvergleich. Solange der Markt zu dünn meldet, bleibt dieser Teil leer, euer privates Tracking oben funktioniert trotzdem.")}</p>
        <p className="tg-note">{t("Eine Meldung kostet euch nichts, weder bei Verlust noch bei Gewinn. Sie fliesst nur anonym in die Wettbewerbsmenge ein, ohne Anbieterbezug.")}</p>
      </div>

      {outcomes.length > 0 && (
        <ul className="tg-out-list">
          {outcomes.slice(0, 8).map((o) => (
            <li key={o.lead_id}>
              <span>{o.titel || o.lead_id}</span>
              <span className={`tg-res ${o.result || (o.applied ? "open" : "dismiss")}`}>
                {o.result === "won" ? t("gewonnen")
                  : o.result === "lost" ? (o.rank ? t("verloren · Rang {n}", { n: o.rank }) : t("verloren"))
                  : o.result === "cancelled" ? t("aufgehoben") : o.applied ? t("beworben") : t("verworfen")}
              </span>
              <button className="tg-x" onClick={async () => { await removeOutcome(o.lead_id); await onChange(); }} aria-label={t("entfernen")}>×</button>
            </li>
          ))}
        </ul>
      )}

      {form
        ? <OutcomeForm onDone={async () => { setForm(false); await onChange(); }} onCancel={() => setForm(false)} />
        : <button className="tg-btn" onClick={() => setForm(true)}>{t("+ Ergebnis erfassen")}</button>}
    </div>
  );
}

const LOSS: { k: LossReason; l: string }[] = [
  { k: "price", l: "Preis" }, { k: "quality", l: "Qualität" }, { k: "formal", l: "Formal" }, { k: "reference", l: "Referenzen" }, { k: "unknown", l: "unbekannt" },
];
function OutcomeForm({ onDone, onCancel }: { onDone: () => void; onCancel: () => void }) {
  const { t } = useSprache();
  const [titel, setTitel] = useState("");
  const [buyer, setBuyer] = useState("");
  const [wert, setWert] = useState("");
  const [applied, setApplied] = useState(true);
  const [result, setResult] = useState<OutcomeResult>("won");
  const [rank, setRank] = useState("");
  const [loss, setLoss] = useState<LossReason>("unknown");
  const [saving, setSaving] = useState(false);

  async function save() {
    if (!titel.trim()) return;
    setSaving(true);
    await reportOutcome({
      lead_id: `manual:${titel.trim().slice(0, 60)}:${buyer.trim().slice(0, 30)}`,
      applied, result: applied ? result : null,
      rank: result === "lost" && rank ? Number(rank) : null,
      loss_reason: result === "lost" ? loss : null,
      titel: titel.trim(), buyer_name: buyer.trim() || null, value_euro: wert ? (parseWert(wert) ?? null) : null,
    });
    setSaving(false); onDone();
  }
  return (
    <div className="tg-form">
      <div className="tg-form-grid">
        <input placeholder={t("Ausschreibung / Titel")} value={titel} onChange={(e) => setTitel(e.target.value)} />
        <input placeholder={t("Vergabestelle")} value={buyer} onChange={(e) => setBuyer(e.target.value)} />
        <input placeholder={t("Auftragswert €")} value={wert} onChange={(e) => setWert(e.target.value)} />
      </div>
      <div className="tg-form-row">
        <label className="tg-chk"><input type="checkbox" checked={applied} onChange={(e) => setApplied(e.target.checked)} /> {t("beworben")}</label>
        {applied && (
          <div className="tg-pills sm">
            {(["won", "lost", "cancelled"] as OutcomeResult[]).map((r) => (
              <button key={r} className={result === r ? "on" : ""} onClick={() => setResult(r)}>{r === "won" ? t("gewonnen") : r === "lost" ? t("verloren") : t("aufgehoben")}</button>
            ))}
          </div>
        )}
      </div>
      {applied && result === "lost" && (
        <div className="tg-form-row">
          <input className="tg-rank" inputMode="numeric" placeholder={t("Rang")} value={rank} onChange={(e) => setRank(e.target.value)} />
          <select value={loss} onChange={(e) => setLoss(e.target.value as LossReason)}>{LOSS.map((x) => <option key={x.k} value={x.k}>{t(x.l)}</option>)}</select>
        </div>
      )}
      <div className="tg-form-actions">
        <button className="tg-btn" onClick={save} disabled={saving || !titel.trim()}>{saving ? t("Speichert …") : t("Meldung speichern")}</button>
        <button className="tg-btn ghost" onClick={onCancel}>{t("Abbrechen")}</button>
      </div>
    </div>
  );
}
