"use client";

import Link from "next/link";
import { useEffect, useState, type Dispatch, type SetStateAction, type ReactNode, type ChangeEvent } from "react";
import { useSprache } from "@/lib/i18n";
import { uploadNachweis, signedNachweisUrl, removeNachweis } from "@/lib/supabase/storage";
import {
  loadProfil, computeKmu, RECHTSFORMEN,
  saveStammdaten, saveZielrichtung, saveBranchen, saveExclusions, saveRole,
  saveReferences, saveCertificates, saveAttribute, confirmReference,
  fetchVorbefuellung, applyPrefillReferences, saveIdentityCorrection,
  wirkung, daysUntil,
  type Profil, type ProfilContext, type Stammdaten, type Rechtsform, type Zustand,
  type Reference, type Certificate, type Exclusions, type Role, type Zielrichtung,
  type Prefill,
} from "@/lib/supabase/unternehmen";
import { catalogFor, requiredKeysFor, type CatalogItem } from "@/lib/unternehmen/catalog";
import { exportProfilJson, exportProfilPdf } from "@/lib/unternehmen/export";
import { BilanzTab, ChancenTab } from "./BilanzChancen";
import { MarktPanel } from "./MarktPanel";

/* #27 Eignungsprofil — „Unser Unternehmen". Ein Objekt, an einer Stelle gepflegt (§2).
 * Lädt das Profil einmal, hält es in State, jede Sektion speichert ihren Teil merge-sicher.
 *
 * Sprache: der deutsche Satz IST der Schlüssel (s. `lib/i18n`). Modul-Konstanten (ZIELE,
 * ROLLEN, ZERT_TYPEN) bleiben deutsch definiert und werden erst beim Rendern übersetzt —
 * bei der Definition übersetzt wäre die Sprache beim Import eingefroren. */

const nid = () => `r${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
const eur = (v?: number | null) => (v == null ? "—" : v.toLocaleString("de-DE", { maximumFractionDigits: 0 }) + " €");
const numIn = (v: string): number | null => {
  const n = Number(v.replace(/[^\d.,]/g, "").replace(/\./g, "").replace(",", "."));
  return v.trim() === "" || Number.isNaN(n) ? null : n;
};

export type UnTab = "profil" | "bilanz" | "chancen";

/**
 * `tab`/`onTab` kommen seit 2026-08-15 von AUSSEN. Grund: die Reiter sind Navigation, nicht
 * Inhalt — sie gehoeren in die Bereichsleiste des Rahmens, gleich hoch wie die Filterleiste
 * der Listen-Ansichten. Damit sie dort stehen koennen, muss der Zustand eine Ebene hoeher
 * liegen; sonst haette die Leiste keinen Zugriff darauf.
 */
export function UnternehmenView({ tab, onTab }: { tab: UnTab; onTab: (t: UnTab) => void }) {
  const { t } = useSprache();
  const [loading, setLoading] = useState(true);
  const [noSession, setNoSession] = useState(false);
  const [profil, setProfil] = useState<Profil | null>(null);
  const [ctx, setCtx] = useState<ProfilContext | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [lokaleFirma, setLokaleFirma] = useState<string | null>(null);

  useEffect(() => {
    try {
      const roh = localStorage.getItem("govisor.profile.v1");
      if (roh) setLokaleFirma((JSON.parse(roh) as { firma?: string }).firma ?? null);
    } catch { /* kaputter Eintrag ist kein Grund, die Seite zu blockieren */ }
    loadProfil().then((r) => {
      if (!r) { setNoSession(true); setLoading(false); return; }
      setProfil(r.profil); setCtx(r.ctx); setLoading(false);
    }).catch(() => { setNoSession(true); setLoading(false); });
  }, []);

  function toast(msg: string) { setFlash(msg); setTimeout(() => setFlash((m) => (m === msg ? null : m)), 2200); }
  // Nach erfolgreichem Save das Profil frisch nachladen, damit History/Zustände konsistent sind.
  async function refresh() { const r = await loadProfil(); if (r) { setProfil(r.profil); setCtx(r.ctx); } }

  if (loading) return <div className="un-wrap"><p className="un-muted">{t("Lädt …")}</p></div>;
  // „Bitte anmelden" war irreführend: der Explorer arbeitet auf dem lokalen Profil und
  // zeigt oben die Firma an — hier hieß es dann trotzdem, man sei nicht angemeldet.
  // Der Unterschied ist echt (dieses Profil liegt im Konto, nicht im Browser), also wird
  // er benannt statt behauptet, und mit dem Weg dorthin verbunden.
  if (noSession || !profil || !ctx) {
    return (
      <div className="un-wrap">
        <div className="un-gate">
          <h1>{t("Unser Unternehmen")}</h1>
          {lokaleFirma ? (
            <p>
              {t("Wir kennen euch in diesem Browser bereits als")} <b>{lokaleFirma}</b>{" "}
              {t("— die Lead-Liste ist darauf eingestellt. Das Eignungsprofil (Referenzen, Zertifikate, Nachweise) liegt aber in eurem")}{" "}
              <b>{t("Konto")}</b>
              {t(", nicht im Browser: nur so steht es auf jedem Gerät und dem ganzen Team zur Verfügung.")}
            </p>
          ) : (
            <p>
              {t("Hier pflegt ihr eure Eignungsangaben — Referenzen, Zertifikate, Nachweise. Sie liegen in eurem Konto und werden für Anforderungsabgleich, Textbausteine und Relevanz verwendet.")}
            </p>
          )}
          {/* DER MARKT IN ZAHLEN. Svens Vorschlag: allgemeine Marktdaten zeigen, solange
              das Unternehmen nicht angemeldet ist — dann sieht man, worum es geht, BEVOR
              man etwas eingibt. Echte Zahlen aus derselben Quelle wie die Akquise-Zaehler;
              erfundene waeren genau die Zierde, die das Produkt sonst vermeidet. */}
          <MarktPanel />

          {/* WAS DAS PROFIL BEWIRKT — vorher stand hier nur, WAS man eintraegt
              („Referenzen, Zertifikate, Nachweise"). Das ist eine Aufgabe, kein Grund.
              Drei Wirkungen, jede an einer Stelle im Produkt, die es schon gibt. */}
          <ul className="un-wirkt">
            <li>
              <b>{t("Relevanz statt Vollständigkeit")}</b>
              <span>{t("Die Lead-Liste sortiert nach eurem Feld und eurem Umkreis, statt alles zu zeigen.")}</span>
            </li>
            <li>
              <b>{t("Anforderungsabgleich")}</b>
              <span>{t("Aus den Vergabeunterlagen gelesene Nachweise werden gegen eure gehalten — was fehlt, steht sofort da.")}</span>
            </li>
            <li>
              <b>{t("Textbausteine, die schon ausgefüllt sind")}</b>
              <span>{t("Eure Angaben fließen in die Bausteinbibliothek, statt bei jedem Angebot neu getippt zu werden.")}</span>
            </li>
          </ul>

          <div className="un-gate-btns">
            <Link className="btn-haupt" href="/login">{t("Anmelden")}</Link>
            <Link className="btn-zweit" href="/onboarding">{t("Konto anlegen")}</Link>
          </div>
          {/* „Zurueck" ist keine gleichwertige Handlung — vorher sahen alle drei gleich aus.
              Ein Ausgang gehoert nicht neben den Eingang gestellt. */}
          <p className="un-muted">
            {t("Eure lokale Einstellung bleibt dabei erhalten.")}{" "}
            <Link href="/leads" className="un-zurueck">{t("Zurück zu den Leads")}</Link>
          </p>
        </div>
      </div>
    );
  }

  const cpv4 = profil.branchen.cpv;
  const catalog = catalogFor(cpv4);
  const w = wirkung(profil, requiredKeysFor(cpv4));

  return (
    <div className="un-wrap" id="un-print-root">
      <div className="un-head">
        <h1>{t("Unser Unternehmen")}</h1>
        <p>{t("Die Eignungsangaben eures Betriebs — einmal erfasst, überall verwendet: Anforderungsabgleich, Textbausteine und Relevanz greifen darauf zu.")}</p>
      </div>

      {tab === "profil" ? (
        <>
          <WirkungBanner w={w} />
          <IdentitaetSektion profil={profil} ctx={ctx} setProfil={setProfil} toast={toast} refresh={refresh} />
          <StammdatenSektion profil={profil} setProfil={setProfil} toast={toast} refresh={refresh} />
          <ZielrichtungSektion profil={profil} setProfil={setProfil} toast={toast} />
          <BranchenSektion profil={profil} setProfil={setProfil} toast={toast} />
          <KatalogSektion profil={profil} catalog={catalog} setProfil={setProfil} toast={toast} refresh={refresh} />
          <ReferenzenSektion profil={profil} setProfil={setProfil} toast={toast} refresh={refresh} />
          <ZertifikateSektion profil={profil} setProfil={setProfil} toast={toast} refresh={refresh} />
          <AusschluesseSektion profil={profil} setProfil={setProfil} toast={toast} />
          <RolleSektion profil={profil} setProfil={setProfil} toast={toast} />
          <ExportSektion profil={profil} ctx={ctx} />
        </>
      ) : tab === "bilanz" ? <BilanzTab /> : <ChancenTab profil={profil} />}

      {flash && <div className="un-flash">{flash}</div>}
    </div>
  );
}

/* ── Wirkung (§7.4) ── */
function WirkungBanner({ w }: { w: ReturnType<typeof wirkung> }) {
  const { t } = useSprache();
  const parts: string[] = [];
  if (w.offen > 0) parts.push(w.offen === 1 ? t("{n} Angabe fehlt", { n: w.offen }) : t("{n} Angaben fehlen", { n: w.offen }));
  if (w.abgeleitet_offen > 0) parts.push(w.abgeleitet_offen === 1
    ? t("{n} vorbefüllte Angabe unbestätigt", { n: w.abgeleitet_offen })
    : t("{n} vorbefüllte Angaben unbestätigt", { n: w.abgeleitet_offen }));
  if (w.abgelaufen > 0) parts.push(w.abgelaufen === 1
    ? t("{n} Zertifikat abgelaufen", { n: w.abgelaufen })
    : t("{n} Zertifikate abgelaufen", { n: w.abgelaufen }));
  if (w.ablaufend > 0) parts.push(w.ablaufend === 1
    ? t("{n} Zertifikat läuft in ≤ 90 Tagen ab", { n: w.ablaufend })
    : t("{n} Zertifikate laufen in ≤ 90 Tagen ab", { n: w.ablaufend }));
  if (parts.length === 0) return <div className="un-wirkung ok">{t("Profil vollständig gepflegt — alle Pflicht-Anforderungen beantwortet.")}</div>;
  return <div className="un-wirkung"><strong>{t("Zu erledigen:")}</strong> {parts.join(" · ")}</div>;
}

/* ── Identität + Vorbefüllung + Entity-Korrektur (§7.1/§7.3) ── */
function IdentitaetSektion({ profil, ctx, setProfil, toast, refresh }: SecP & { ctx: ProfilContext; refresh: () => Promise<void> }) {
  const { t } = useSprache();
  const [busy, setBusy] = useState(false);
  const [prefill, setPrefill] = useState<Prefill | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [showKorr, setShowKorr] = useState(false);

  async function loadPrefill() {
    if (!ctx.identityId) { setErr(t("Keine Firma zugeordnet — bitte zuerst die Zuordnung wählen.")); return; }
    setBusy(true); setErr(null);
    const r = await fetchVorbefuellung(ctx.identityId);
    setBusy(false);
    if ("error" in r && r.error) { setErr(r.error); return; }
    setPrefill(r as Prefill);
  }

  async function uebernehmen() {
    if (!prefill) return;
    // Referenzen (abgeleitet), CPV-Schwerpunkte als Branchen-Vorschlag, Umsatz-Näherung als abgeleitet.
    const refs = applyPrefillReferences(profil.references, prefill.references);
    const r1 = await saveReferences(refs);
    const cpv = Array.from(new Set([...profil.branchen.cpv, ...prefill.cpv_schwerpunkte.map((c) => c.code)]));
    await saveBranchen(cpv);
    if (r1.ok) { toast(t("{n} Referenzen als „abgeleitet\" übernommen — bitte bestätigen.", { n: prefill.references.length })); await refresh(); }
    else toast(t("Übernahme fehlgeschlagen."));
  }

  const conf = ctx.entityConfidence;
  return (
    <Section title={t("Zuordnung & Vorbefüllung")} hint={t("Eure Firma im Vergabegraph — Grundlage für die Vorbefüllung aus eigenen Zuschlägen.")}>
      <div className="un-ident">
        <span className="un-firm">{ctx.companyName || t("Unternehmen noch nicht zugeordnet")}</span>
        {conf && <span className={`un-conf ${conf === "belegt" ? "ok" : "warn"}`}>{conf === "belegt" ? t("Zuordnung gesichert") : t("Zuordnung unsicher")}</span>}
        <code className="un-idcode">{ctx.identityId || "—"}</code>
      </div>

      <div className="un-actions">
        <button className="un-btn" onClick={loadPrefill} disabled={busy || !ctx.identityId}>
          {busy ? t("Lädt Zuschläge …") : t("Aus eigenen Zuschlägen befüllen")}</button>
        <button className="un-btn ghost" onClick={() => setShowKorr((v) => !v)}>{t("Zuordnung korrigieren")}</button>
      </div>
      {err && <p className="un-err">{err}</p>}

      {prefill && (
        <div className="un-prefill">
          <p className="un-sub">{prefill.name} · {t("{n} Zuschläge belegt", { n: prefill.wins_total.toLocaleString("de-DE") })}</p>
          <div className="un-pf-grid">
            <div><span className="un-k">{t("Referenzen gefunden")}</span><span className="un-v">{prefill.references.length}</span></div>
            <div><span className="un-k">{t("CPV-Schwerpunkt")}</span><span className="un-v">{prefill.cpv_schwerpunkte[0]?.label ?? "—"}</span></div>
            <div><span className="un-k">{t("Hauptregion")}</span><span className="un-v">{prefill.regionen[0]?.label ?? "—"}</span></div>
            <div><span className="un-k">{t("Umsatz-Näherung")}</span><span className="un-v">{prefill.umsatz_naeherung ? eur(prefill.umsatz_naeherung) : "—"} <em className="un-note">{t("≈ Auftragsvol., {p}% belegt", { p: prefill.umsatz_coverage })}</em></span></div>
          </div>
          <button className="un-btn" onClick={uebernehmen}>{t("Referenzen + Schwerpunkte übernehmen (abgeleitet)")}</button>
          <p className="un-note">{t("Übernommene Angaben zählen erst nach Bestätigung (§7.1) — sie erscheinen unten als „abgeleitet\".")}</p>
        </div>
      )}

      {showKorr && <EntityKorrektur profil={profil} ctx={ctx} toast={toast} refresh={refresh} setProfil={setProfil} />}
    </Section>
  );
}

function EntityKorrektur({ ctx, toast, refresh }: SecP & { ctx: ProfilContext; refresh: () => Promise<void> }) {
  const { t } = useSprache();
  const [q, setQ] = useState("");
  const [matches, setMatches] = useState<{ id: string; name: string; wins: number; strong: boolean }[]>([]);
  const [busy, setBusy] = useState(false);

  async function search() {
    if (q.trim().length < 2) return;
    setBusy(true);
    try { const r = await fetch(`/api/entity-search?q=${encodeURIComponent(q)}`); const d = await r.json(); setMatches(d.matches || []); }
    catch { setMatches([]); }
    setBusy(false);
  }
  async function choose(m: { id: string; name: string; strong: boolean }) {
    const r = await saveIdentityCorrection(m.id, m.name, m.strong ? "belegt" : "unsicher");
    if (r.ok) { toast(t("Zuordnung auf „{name}\" korrigiert — Vorbefüllung neu berechenbar.", { name: m.name })); await refresh(); }
    else toast(t("Korrektur fehlgeschlagen."));
  }
  return (
    <div className="un-korr">
      <p className="un-note">{t("Falsche Gesellschaft zugeordnet? Firma suchen und richtige Identität wählen — die Korrektur wirkt auch auf den Entity-Graph (§7.3).")}</p>
      <div className="un-searchrow">
        <input placeholder={t("Firmenname suchen …")} value={q} onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()} />
        <button className="un-btn" onClick={search} disabled={busy}>{busy ? "…" : t("Suchen")}</button>
      </div>
      {matches.map((m) => (
        <div key={m.id} className={`un-match ${m.id === ctx.identityId ? "cur" : ""}`}>
          <span>{m.name} <em className="un-note">{t("{n} Zuschläge", { n: m.wins })}{m.id === ctx.identityId ? ` · ${t("aktuell")}` : ""}</em></span>
          {m.id !== ctx.identityId && <button className="un-btn ghost sm" onClick={() => choose(m)}>{t("wählen")}</button>}
        </div>
      ))}
    </div>
  );
}

/* ── Stammdaten (§3) ── */
function StammdatenSektion({ profil, setProfil, toast, refresh }: SecP & { refresh: () => Promise<void> }) {
  const { t } = useSprache();
  const [sd, setSd] = useState<Stammdaten>(profil.stammdaten);
  const [saving, setSaving] = useState(false);
  useEffect(() => setSd(profil.stammdaten), [profil.stammdaten]);
  const kmu = computeKmu(sd);
  function set<K extends keyof Stammdaten>(k: K, v: Stammdaten[K]) { setSd((p) => ({ ...p, [k]: v })); }
  async function save() {
    setSaving(true); const r = await saveStammdaten(sd); setSaving(false);
    if (r.ok) { toast(t("Stammdaten gespeichert.")); await refresh(); } else toast(t("Speichern fehlgeschlagen."));
  }
  return (
    <Section title={t("Stammdaten")} hint={t("Rechtsform, Kennzahlen — Basis für Schwellenprüfung, KMU-Status und Textbausteine.")}>
      <div className="un-grid">
        <label className="un-field"><span>{t("Rechtsform")}</span>
          <select value={sd.rechtsform || ""} onChange={(e) => set("rechtsform", (e.target.value || null) as Rechtsform | null)}>
            <option value="">{t("– wählen –")}</option>{RECHTSFORMEN.map((r) => <option key={r} value={r}>{r}</option>)}
          </select></label>
        <label className="un-field"><span>{t("Gründungsjahr")}</span>
          <input type="number" inputMode="numeric" placeholder={t("z. B. 1998")} value={sd.gruendungsjahr ?? ""}
            onChange={(e) => set("gruendungsjahr", e.target.value ? Number(e.target.value) : null)} /></label>
        <label className="un-field"><span>{t("Mitarbeiterzahl")}</span>
          <input inputMode="numeric" placeholder={t("z. B. 45")} value={sd.mitarbeiter ?? ""}
            onChange={(e) => set("mitarbeiter", numIn(e.target.value))} /></label>
        <label className="un-field"><span>{t("Sprache")}</span>
          <select value={sd.sprache || "de"} onChange={(e) => set("sprache", e.target.value)}><option value="de">{t("Deutsch")}</option></select></label>
      </div>
      <div className="un-umsatz">
        <span className="un-sub">{t("Umsatz der letzten drei Geschäftsjahre (€)")}</span>
        <div className="un-grid3">
          <label className="un-field"><span>{t("jüngstes Jahr")}</span><input inputMode="numeric" placeholder={t("z. B. 8.500.000")} value={sd.umsatz_j1 ?? ""} onChange={(e) => set("umsatz_j1", numIn(e.target.value))} /></label>
          <label className="un-field"><span>{t("Vorjahr")}</span><input inputMode="numeric" value={sd.umsatz_j2 ?? ""} onChange={(e) => set("umsatz_j2", numIn(e.target.value))} /></label>
          <label className="un-field"><span>{t("2 Jahre zuvor")}</span><input inputMode="numeric" value={sd.umsatz_j3 ?? ""} onChange={(e) => set("umsatz_j3", numIn(e.target.value))} /></label>
        </div>
      </div>
      <div className={`un-kmu ${kmu.ist_kmu ? "ok" : kmu.kategorie === "unbekannt" ? "unk" : "no"}`}>
        <strong>{t(kmu.label)}</strong><span>{kmu.begruendung}</span>
        <em>{t("KMU-Status wird aus Umsatz und Mitarbeiterzahl berechnet (EU-Definition), nicht separat abgefragt.")}</em>
      </div>
      <div className="un-actions"><button className="un-btn" onClick={save} disabled={saving}>{saving ? t("Speichert …") : t("Stammdaten speichern")}</button></div>
    </Section>
  );
}

/* ── Zielrichtung (§6.2) ──
 * Deutsch definiert, beim Rendern übersetzt (`t(z.label)`) — s. Kopfkommentar. */
const ZIELE: { k: Zielrichtung; label: string; hint: string }[] = [
  { k: "bestand", label: "Bestand halten", hint: "Gewichtung auf bekannte Vergabestellen und Felder; Auslauf-Radar priorisiert." },
  { k: "ausgewogen", label: "Ausgewogen", hint: "Standard — keine Verschiebung." },
  { k: "expandieren", label: "Expandieren", hint: "Zusätzliche CPV-Felder und Regionen, auch ohne Zuschläge dort." },
];
function ZielrichtungSektion({ profil, setProfil, toast }: SecP) {
  const { t } = useSprache();
  async function pick(z: Zielrichtung) {
    setProfil((p) => (p ? { ...p, zielrichtung: z } : p));
    const r = await saveZielrichtung(z); toast(r.ok ? t("Zielrichtung gespeichert.") : t("Speichern fehlgeschlagen."));
  }
  return (
    <Section title={t("Zielrichtung")} hint={t("Wer expandiert, braucht andere Leads als wer verteidigt — wirkt auf Relevanz und Empfehlung (#2/#26).")}>
      <div className="un-ziele">
        {ZIELE.map((z) => (
          <button key={z.k} className={`un-ziel ${profil.zielrichtung === z.k ? "on" : ""}`} onClick={() => pick(z.k)}>
            <strong>{t(z.label)}</strong><span>{t(z.hint)}</span>
          </button>
        ))}
      </div>
    </Section>
  );
}

/* ── Branchenzuordnung (§6.1) ── */
function BranchenSektion({ profil, setProfil, toast }: SecP) {
  const { t } = useSprache();
  const [neu, setNeu] = useState("");
  async function persist(cpv: string[]) { setProfil((p) => (p ? { ...p, branchen: { ...p.branchen, cpv } } : p)); const r = await saveBranchen(cpv); toast(r.ok ? t("Branchen gespeichert.") : t("Speichern fehlgeschlagen.")); }
  function add() { const c = neu.replace(/\D/g, "").slice(0, 4); if (c.length >= 2 && !profil.branchen.cpv.includes(c)) { persist([...profil.branchen.cpv, c]); setNeu(""); } }
  function remove(c: string) { persist(profil.branchen.cpv.filter((x) => x !== c)); }
  return (
    <Section title={t("Branchenzuordnung (CPV)")} hint={t("Vorschlag aus der eigenen Zuschlagshistorie, änderbar — steuert den Anforderungskatalog.")}>
      <div className="un-chips">
        {profil.branchen.cpv.length === 0 && <span className="un-muted">{t("Noch keine CPV-Schwerpunkte — über „Aus eigenen Zuschlägen befüllen\" oben oder manuell.")}</span>}
        {profil.branchen.cpv.map((c) => <span key={c} className="un-chip">CPV {c}<button onClick={() => remove(c)} aria-label={t("entfernen")}>×</button></span>)}
      </div>
      <div className="un-searchrow">
        <input placeholder={t("CPV-Code (z. B. 4500)")} value={neu} onChange={(e) => setNeu(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} maxLength={4} />
        <button className="un-btn ghost" onClick={add}>{t("hinzufügen")}</button>
      </div>
    </Section>
  );
}

/* ── Anforderungskatalog (§5) ── */
function KatalogSektion({ profil, catalog, setProfil, toast, refresh }: SecP & { catalog: CatalogItem[]; refresh: () => Promise<void> }) {
  const { t } = useSprache();
  const jahre = profil.stammdaten.gruendungsjahr ? new Date().getFullYear() - profil.stammdaten.gruendungsjahr : null;
  const refCount = profil.references.filter((r) => r.quelle !== "abgeleitet" || r.bestaetigt).length;
  const refSum = profil.references.filter((r) => r.quelle !== "abgeleitet" || r.bestaetigt).reduce((s, r) => s + (r.wert || 0), 0);

  function derived(it: CatalogItem): { text: string; ok: boolean } | null {
    switch (it.quelleStammdaten) {
      case "umsatz": { const v = profil.stammdaten.umsatz_j1; return { text: v ? eur(v) : t("nicht erfasst"), ok: v != null }; }
      case "mitarbeiter": { const v = profil.stammdaten.mitarbeiter; return { text: v != null ? t("{n} Personen", { n: v }) : t("nicht erfasst"), ok: v != null }; }
      case "jahre": return { text: jahre != null ? t("{n} Jahre", { n: jahre }) : t("nicht erfasst"), ok: jahre != null };
      case "referenzen": return { text: t("{n} Referenzen · {summe}", { n: refCount, summe: eur(refSum) }), ok: refCount > 0 };
      default: return null;
    }
  }
  return (
    <Section title={t("Anforderungskatalog")} hint={t("{n} branchenübliche Anforderungen — je Punkt eine Angabe (ja/nein/Wert). Ein „trifft nicht zu\" ist genauso verwertbar.", { n: catalog.length })}>
      <div className="un-kat">
        {catalog.map((it) => <KatalogZeile key={it.id} it={it} profil={profil} derived={derived(it)} setProfil={setProfil} toast={toast} refresh={refresh} />)}
      </div>
    </Section>
  );
}

function KatalogZeile({ it, profil, derived, toast, refresh }: { it: CatalogItem; profil: Profil; derived: { text: string; ok: boolean } | null } & Pick<SecP, "setProfil" | "toast"> & { refresh: () => Promise<void> }) {
  const { t } = useSprache();
  const a = profil.attributes[it.id];
  const [belegt, setBelegt] = useState(a?.zustand === "belegt");

  async function answer(value: boolean | number | string | null, zustand: Zustand = belegt ? "belegt" : "angegeben") {
    await saveAttribute(it.id, { art: it.art, value, zustand, einheit: it.einheit ?? null }); toast(t("Angabe gespeichert.")); await refresh();
  }
  return (
    <div className={`un-katrow ${it.ko ? "ko" : ""}`}>
      <div className="un-katlabel">
        <span>{t(it.label)}{it.ko && <b className="un-koflag" title={t("K.-o.-Kriterium")}>{t("K.-o.")}</b>}</span>
        {it.hinweis && <em className="un-note">{t(it.hinweis)}</em>}
      </div>
      <div className="un-katctrl">
        {derived ? (
          <span className={`un-derived ${derived.ok ? "ok" : "unk"}`}>{derived.text} <em>{t("aus Profil")}</em></span>
        ) : it.art === "binaer" ? (
          <div className="un-triple">
            <button className={a?.value === true ? "on" : ""} onClick={() => answer(true)}>{t("ja")}</button>
            <button className={a?.value === false ? "on no" : ""} onClick={() => answer(false)}>{t("nein")}</button>
            <button className={a == null ? "on unk" : ""} onClick={() => answer(null)}>{t("offen")}</button>
          </div>
        ) : it.art === "schwelle" ? (
          <input className="un-num" inputMode="numeric" defaultValue={a?.value != null ? String(a.value) : ""} placeholder={it.einheit || ""}
            onBlur={(e) => answer(numIn(e.target.value))} />
        ) : it.art === "kennung" ? (
          <input className="un-kennung" defaultValue={typeof a?.value === "string" ? a.value : ""} placeholder={t("Nummer / Kennung (leer = nein)")}
            onBlur={(e) => answer(e.target.value.trim() || null)} />
        ) : (
          <span className="un-derived ok">{t("→ Sektion „Referenzen\"")}</span>
        )}
        {!derived && it.art !== "sammlung" && (
          <label className="un-beleg"><input type="checkbox" checked={belegt} onChange={(e) => setBelegt(e.target.checked)} /> {t("belegt")}</label>
        )}
        {a?.zustand && <span className={`un-zst ${a.zustand}`}>{t(a.zustand)}</span>}
      </div>
    </div>
  );
}

/* ── Referenzen (Sammlung, §7.1) ── */
function ReferenzenSektion({ profil, setProfil, toast, refresh }: SecP & { refresh: () => Promise<void> }) {
  const { t } = useSprache();
  const [list, setList] = useState<Reference[]>(profil.references);
  useEffect(() => setList(profil.references), [profil.references]);

  function upd(id: string, patch: Partial<Reference>) { setList((l) => l.map((r) => (r.id === id ? { ...r, ...patch } : r))); }
  function add() { setList((l) => [{ id: nid(), quelle: "angegeben", projekt: "", auftraggeber: "", wert: null, von: null, bis: null, cpv: null }, ...l]); }
  function remove(id: string) { setList((l) => l.filter((r) => r.id !== id)); }
  async function save() { const r = await saveReferences(list); toast(r.ok ? t("Referenzen gespeichert.") : t("Speichern fehlgeschlagen.")); if (r.ok) await refresh(); }
  async function confirm(id: string) { const r = await confirmReference(id); if (r.ok) { toast(t("Referenz bestätigt — zählt jetzt.")); await refresh(); } }

  return (
    <Section title={t("Referenzen")} hint={t("Einmal erfasst, überall genutzt: Anforderungsprüfung, Referenz-Textbaustein, Relevanz.")}>
      <div className="un-actions"><button className="un-btn ghost" onClick={add}>{t("+ Referenz")}</button></div>
      {list.length === 0 && <p className="un-muted">{t("Noch keine Referenzen — oben aus eigenen Zuschlägen vorbefüllen oder manuell anlegen.")}</p>}
      {list.map((r) => (
        <div key={r.id} className={`un-ref ${r.quelle === "abgeleitet" && !r.bestaetigt ? "derived" : ""}`}>
          <div className="un-refgrid">
            <input placeholder={t("Projekt")} value={r.projekt || ""} onChange={(e) => upd(r.id, { projekt: e.target.value })} />
            <input placeholder={t("Auftraggeber")} value={r.auftraggeber || ""} onChange={(e) => upd(r.id, { auftraggeber: e.target.value })} />
            <input placeholder={t("Wert €")} inputMode="numeric" value={r.wert ?? ""} onChange={(e) => upd(r.id, { wert: numIn(e.target.value) })} />
            <input placeholder={t("von")} value={r.von || ""} onChange={(e) => upd(r.id, { von: e.target.value })} />
            <input placeholder={t("bis")} value={r.bis || ""} onChange={(e) => upd(r.id, { bis: e.target.value })} />
            <input placeholder="CPV" value={r.cpv || ""} onChange={(e) => upd(r.id, { cpv: e.target.value })} />
          </div>
          <div className="un-refmeta">
            {r.quelle === "abgeleitet" && !r.bestaetigt
              ? <><span className="un-zst abgeleitet">{t("abgeleitet")}</span><button className="un-btn ghost sm" onClick={() => confirm(r.id)}>{t("bestätigen")}</button></>
              : <span className="un-zst angegeben">{r.quelle === "abgeleitet" ? t("bestätigt") : t("angegeben")}</span>}
            <button className="un-x" onClick={() => remove(r.id)} aria-label={t("löschen")}>×</button>
          </div>
        </div>
      ))}
      <div className="un-actions"><button className="un-btn" onClick={save}>{t("Referenzen speichern")}</button></div>
    </Section>
  );
}

/* ── Zertifikate (§8/§9) ──
 * Die Werte sind gespeicherte Kennungen (`value=`), deshalb bleiben sie deutsch —
 * übersetzt wird nur das, was im Menü steht. */
const ZERT_TYPEN = ["ISO 9001", "ISO 14001", "ISO 27001", "ISO 45001", "SCC / SCP", "Präqualifikation (PQ-VOB)", "Präqualifikation (PQ-VOL)", "Berufshaftpflicht", "Sonstige"];
function ZertifikateSektion({ profil, setProfil, toast, refresh }: SecP & { refresh: () => Promise<void> }) {
  const { t } = useSprache();
  const [list, setList] = useState<Certificate[]>(profil.certificates);
  useEffect(() => setList(profil.certificates), [profil.certificates]);
  function upd(id: string, patch: Partial<Certificate>) { setList((l) => l.map((c) => (c.id === id ? { ...c, ...patch } : c))); }
  function add() { setList((l) => [{ id: nid(), zustand: "angegeben", typ: "", nummer: "", aussteller: "", gueltig_bis: null }, ...l]); }
  function remove(id: string) { setList((l) => l.filter((c) => c.id !== id)); }
  async function save() { const r = await saveCertificates(list); toast(r.ok ? t("Zertifikate gespeichert.") : t("Speichern fehlgeschlagen.")); if (r.ok) await refresh(); }
  // Auto-Persist nach Upload/Entfernen, damit die Nachweis-Referenz nicht verloren geht.
  async function persist(next: Certificate[]) { setList(next); await saveCertificates(next); }
  return (
    <Section title={t("Zertifikate & Nachweise")} hint={t("Ablaufdatum pflichtig — abgelaufene zählen nicht als erfüllt; Erinnerung 90 Tage vorher (§9). Nachweis optional, verschlüsselt und profilgebunden.")}>
      <div className="un-actions"><button className="un-btn ghost" onClick={add}>{t("+ Zertifikat")}</button></div>
      {list.length === 0 && <p className="un-muted">{t("Noch keine Zertifikate erfasst.")}</p>}
      {list.map((c) => {
        const dd = daysUntil(c.gueltig_bis); const abgelaufen = dd != null && dd < 0; const bald = dd != null && dd >= 0 && dd <= 90;
        return (
          <div key={c.id} className={`un-cert ${abgelaufen ? "expired" : bald ? "soon" : ""}`}>
            <div className="un-refgrid cert">
              <select value={c.typ || ""} onChange={(e) => upd(c.id, { typ: e.target.value })}>
                <option value="">{t("Typ wählen …")}</option>{ZERT_TYPEN.map((typ) => <option key={typ} value={typ}>{t(typ)}</option>)}
              </select>
              <input placeholder={t("Nummer")} value={c.nummer || ""} onChange={(e) => upd(c.id, { nummer: e.target.value })} />
              <input placeholder={t("Aussteller")} value={c.aussteller || ""} onChange={(e) => upd(c.id, { aussteller: e.target.value })} />
              <label className="un-inl"><span>{t("gültig bis")}</span><input type="date" value={c.gueltig_bis || ""} onChange={(e) => upd(c.id, { gueltig_bis: e.target.value || null })} /></label>
            </div>
            <div className="un-refmeta">
              <NachweisControl cert={c}
                onUploaded={(path) => persist(list.map((x) => (x.id === c.id ? { ...x, nachweis: path, zustand: "belegt" } : x)))}
                onRemoved={() => persist(list.map((x) => (x.id === c.id ? { ...x, nachweis: null, zustand: "angegeben" } : x)))}
                toast={toast} />
              {abgelaufen && <span className="un-zst expired">{t("abgelaufen")}</span>}
              {bald && <span className="un-zst soon">{t("läuft in {n} T ab", { n: dd })}</span>}
              {!abgelaufen && !bald && dd != null && <span className="un-zst angegeben">{t("gültig")}</span>}
              <button className="un-x" onClick={() => remove(c.id)} aria-label={t("löschen")}>×</button>
            </div>
          </div>
        );
      })}
      <div className="un-actions"><button className="un-btn" onClick={save}>{t("Zertifikate speichern")}</button></div>
    </Section>
  );
}

function NachweisControl({ cert, onUploaded, onRemoved, toast }: { cert: Certificate; onUploaded: (path: string) => void; onRemoved: () => void; toast: (m: string) => void }) {
  const { t } = useSprache();
  const [busy, setBusy] = useState(false);
  async function pick(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]; if (!f) return;
    setBusy(true); const r = await uploadNachweis(cert.id, f); setBusy(false);
    e.target.value = "";
    if (r.ok && r.path) { onUploaded(r.path); toast(t("Nachweis hochgeladen.")); } else toast(r.error || t("Upload fehlgeschlagen."));
  }
  async function view() {
    if (!cert.nachweis) return;
    const url = await signedNachweisUrl(cert.nachweis);
    if (url) window.open(url, "_blank", "noopener"); else toast(t("Nachweis nicht abrufbar."));
  }
  async function del() { if (!cert.nachweis) return; await removeNachweis(cert.nachweis); onRemoved(); toast(t("Nachweis entfernt.")); }
  if (cert.nachweis) {
    return (
      <span className="un-nachweis">
        <span className="un-zst belegt">{t("Nachweis")}</span>
        <button className="un-btn ghost sm" onClick={view}>{t("ansehen")}</button>
        <button className="un-btn ghost sm" onClick={del}>{t("entfernen")}</button>
      </span>
    );
  }
  return (
    <label className="un-upload">
      {busy ? t("Lädt …") : t("Nachweis hochladen")}
      <input type="file" accept="application/pdf,image/png,image/jpeg" onChange={pick} disabled={busy} hidden />
    </label>
  );
}

/* ── Ausschlusskriterien (§6.3) ── */
function AusschluesseSektion({ profil, setProfil, toast }: SecP) {
  const { t } = useSprache();
  const [ex, setEx] = useState<Exclusions>(profil.exclusions);
  useEffect(() => setEx(profil.exclusions), [profil.exclusions]);
  function set<K extends keyof Exclusions>(k: K, v: Exclusions[K]) { setEx((p) => ({ ...p, [k]: v })); }
  async function save() { const r = await saveExclusions(ex); toast(r.ok ? t("Ausschlüsse gespeichert.") : t("Speichern fehlgeschlagen.")); }
  return (
    <Section title={t("Ausschlusskriterien")} hint={t("Was bewusst nicht in Frage kommt — wenige Angaben, große Wirkung auf die Listenqualität.")}>
      <div className="un-grid">
        <label className="un-field"><span>{t("Mindest-Auftragswert (€)")}</span><input inputMode="numeric" value={ex.wert_min ?? ""} onChange={(e) => set("wert_min", numIn(e.target.value))} /></label>
        <label className="un-field"><span>{t("Höchst-Auftragswert (€)")}</span><input inputMode="numeric" value={ex.wert_max ?? ""} onChange={(e) => set("wert_max", numIn(e.target.value))} /></label>
      </div>
      <label className="un-field"><span>{t("Ausgeschlossene Regionen (NUTS/Bundesland, kommagetrennt)")}</span>
        <input value={(ex.regionen_aus || []).join(", ")} onChange={(e) => set("regionen_aus", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} placeholder={t("z. B. DE3, DE4")} /></label>
      <label className="un-field"><span>{t("Ausgeschlossene Leistungsarten (CPV, kommagetrennt)")}</span>
        <input value={(ex.cpv_aus || []).join(", ")} onChange={(e) => set("cpv_aus", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))} placeholder={t("z. B. 7100")} /></label>
      <label className="un-check"><input type="checkbox" checked={!!ex.keine_bietergemeinschaft} onChange={(e) => set("keine_bietergemeinschaft", e.target.checked)} /> {t("Keine Bietergemeinschaften (unterdrückt den Partner-Zusatz, #26 §3.4)")}</label>
      <div className="un-actions"><button className="un-btn" onClick={save}>{t("Ausschlüsse speichern")}</button></div>
    </Section>
  );
}

/* ── Ansprechpartner-Rolle (§4) ──
 * Deutsch definiert, beim Rendern übersetzt — s. Kopfkommentar. */
const ROLLEN: { k: NonNullable<Role["rolle"]>; label: string }[] = [
  { k: "bid_manager", label: "Bid-Manager" }, { k: "vertrieb", label: "Vertrieb" },
  { k: "geschaeftsfuehrung", label: "Geschäftsführung" }, { k: "sonstige", label: "Sonstige" },
];
function RolleSektion({ profil, setProfil, toast }: SecP) {
  const { t } = useSprache();
  const [role, setRole] = useState<Role>(profil.role);
  useEffect(() => setRole(profil.role), [profil.role]);
  async function save() { const r = await saveRole(role); toast(r.ok ? t("Rolle gespeichert.") : t("Speichern fehlgeschlagen.")); }
  return (
    <Section title={t("Meine Rolle")} hint={t("Adressat der Alerts (#9) — nur für Sie, keine Erfassung Dritter (§4).")}>
      <div className="un-grid">
        <label className="un-field"><span>{t("Rolle im Vergabeprozess")}</span>
          <select value={role.rolle || ""} onChange={(e) => setRole((p) => ({ ...p, rolle: (e.target.value || null) as Role["rolle"] }))}>
            <option value="">{t("– wählen –")}</option>{ROLLEN.map((r) => <option key={r.k} value={r.k}>{t(r.label)}</option>)}
          </select></label>
        <label className="un-field"><span>{t("Zuständige Regionen (kommagetrennt)")}</span>
          <input value={(role.regionen || []).join(", ")} onChange={(e) => setRole((p) => ({ ...p, regionen: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) }))} placeholder={t("optional")} /></label>
      </div>
      <div className="un-actions"><button className="un-btn" onClick={save}>{t("Rolle speichern")}</button></div>
    </Section>
  );
}

/* ── Export (§11) ── */
function ExportSektion({ profil, ctx }: { profil: Profil; ctx: ProfilContext }) {
  const { t } = useSprache();
  return (
    <Section title={t("Export")} hint={t("Eignungsübersicht mitnehmen — JSON (Datenmitnahme) und PDF (Nachweis bei Bewerbungen).")}>
      <div className="un-actions">
        <button className="un-btn ghost" onClick={() => exportProfilJson(profil, ctx)}>{t("JSON exportieren")}</button>
        <button className="un-btn ghost" onClick={() => exportProfilPdf(profil, ctx)}>{t("PDF (Druckansicht)")}</button>
      </div>
      <p className="un-note">{t("Ohne Textbausteine (eigener Export in #23) und ohne hochgeladene Nachweisdokumente.")}</p>
    </Section>
  );
}

/* ── Bausteine ── */
type SecP = { profil: Profil; setProfil: Dispatch<SetStateAction<Profil | null>>; toast: (m: string) => void };

/* `title`/`hint` kommen bereits übersetzt herein — sonst würde hier ein zweites Mal
 * nachgeschlagen und der englische Satz landete als Schlüssel im Katalog. */
function Section({ title, hint, children }: { title: string; hint?: string; children: ReactNode }) {
  return (
    <section className="un-card">
      <div className="un-sec-head"><h2>{title}</h2>{hint && <p className="un-sec-hint">{hint}</p>}</div>
      {children}
    </section>
  );
}
