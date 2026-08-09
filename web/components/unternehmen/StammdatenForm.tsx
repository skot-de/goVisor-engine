"use client";
import { useEffect, useState } from "react";
import {
  loadStammdaten, saveStammdaten, computeKmu, RECHTSFORMEN,
  type Stammdaten, type Rechtsform,
} from "@/lib/supabase/unternehmen";

/* #27 Eignungsprofil — Phase 1: Stammdaten-Formular („Unser Unternehmen").
 * Firmenname/Entity sind bereits zugeordnet (user_profiles); hier die Eignungs-Stammdaten,
 * KMU wird LIVE berechnet (nie abgefragt). Persistenz in user_profiles.profile.stammdaten (RLS). */

const EUR = (v: number | null | undefined) => (v == null ? "" : String(v));

export function StammdatenForm() {
  const [loading, setLoading] = useState(true);
  const [noSession, setNoSession] = useState(false);
  const [company, setCompany] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<string | null>(null);
  const [sd, setSd] = useState<Stammdaten>({ sprache: "de" });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    loadStammdaten().then((r) => {
      if (!r) { setNoSession(true); setLoading(false); return; }
      setCompany(r.companyName); setConfidence(r.entityConfidence);
      setSd({ sprache: "de", ...r.stammdaten });
      setLoading(false);
    }).catch(() => { setNoSession(true); setLoading(false); });
  }, []);

  function set<K extends keyof Stammdaten>(k: K, v: Stammdaten[K]) {
    setSd((p) => ({ ...p, [k]: v })); setSaved(false);
  }
  function num(v: string): number | null {
    const n = Number(v.replace(/[^\d.,]/g, "").replace(/\./g, "").replace(",", "."));
    return v.trim() === "" || Number.isNaN(n) ? null : n;
  }

  async function onSave() {
    setSaving(true);
    const r = await saveStammdaten(sd);
    setSaving(false); setSaved(r.ok);
  }

  if (loading) return <div className="un-wrap"><p className="un-muted">Lädt …</p></div>;
  if (noSession) return <div className="un-wrap"><p className="un-muted">Bitte anmelden, um das Unternehmensprofil zu bearbeiten.</p></div>;

  const kmu = computeKmu(sd);

  return (
    <div className="un-wrap">
      <div className="un-head">
        <h1>Unser Unternehmen</h1>
        <p>Die Eignungs-Stammdaten Ihres Betriebs. Sie speisen Anforderungsabgleich, Textbausteine und
          Relevanz — einmal erfasst, überall verwendet.</p>
      </div>

      <section className="un-card">
        <div className="un-ident">
          <span className="un-firm">{company || "Unternehmen noch nicht zugeordnet"}</span>
          {confidence && <span className={`un-conf ${confidence === "belegt" ? "ok" : "warn"}`}>
            {confidence === "belegt" ? "Zuordnung gesichert" : "Zuordnung unsicher"}</span>}
        </div>

        <div className="un-grid">
          <label className="un-field">
            <span>Rechtsform</span>
            <select value={sd.rechtsform || ""} onChange={(e) => set("rechtsform", (e.target.value || null) as Rechtsform | null)}>
              <option value="">– wählen –</option>
              {RECHTSFORMEN.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <label className="un-field">
            <span>Gründungsjahr</span>
            <input type="number" inputMode="numeric" placeholder="z. B. 1998" value={sd.gruendungsjahr ?? ""}
              onChange={(e) => set("gruendungsjahr", e.target.value ? Number(e.target.value) : null)} />
          </label>
          <label className="un-field">
            <span>Mitarbeiterzahl</span>
            <input inputMode="numeric" placeholder="z. B. 45" value={EUR(sd.mitarbeiter)}
              onChange={(e) => set("mitarbeiter", num(e.target.value))} />
          </label>
          <label className="un-field">
            <span>Sprache</span>
            <select value={sd.sprache || "de"} onChange={(e) => set("sprache", e.target.value)}>
              <option value="de">Deutsch</option>
            </select>
          </label>
        </div>

        <div className="un-umsatz">
          <span className="un-sub">Umsatz der letzten drei Geschäftsjahre (€)</span>
          <div className="un-grid3">
            <label className="un-field"><span>jüngstes Jahr</span>
              <input inputMode="numeric" placeholder="z. B. 8.500.000" value={EUR(sd.umsatz_j1)} onChange={(e) => set("umsatz_j1", num(e.target.value))} /></label>
            <label className="un-field"><span>Vorjahr</span>
              <input inputMode="numeric" placeholder="" value={EUR(sd.umsatz_j2)} onChange={(e) => set("umsatz_j2", num(e.target.value))} /></label>
            <label className="un-field"><span>2 Jahre zuvor</span>
              <input inputMode="numeric" placeholder="" value={EUR(sd.umsatz_j3)} onChange={(e) => set("umsatz_j3", num(e.target.value))} /></label>
          </div>
        </div>

        <div className={`un-kmu ${kmu.ist_kmu ? "ok" : kmu.kategorie === "unbekannt" ? "unk" : "no"}`}>
          <strong>{kmu.label}</strong>
          <span>{kmu.begruendung}</span>
          <em>KMU-Status wird aus Umsatz und Mitarbeiterzahl berechnet (EU-Definition), nicht separat abgefragt.</em>
        </div>

        <div className="un-actions">
          <button className="un-save" onClick={onSave} disabled={saving}>{saving ? "Speichert …" : "Speichern"}</button>
          {saved && <span className="un-ok">✓ gespeichert</span>}
        </div>
      </section>
    </div>
  );
}
