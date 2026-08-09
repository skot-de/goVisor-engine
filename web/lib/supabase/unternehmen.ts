"use client";
import { createClient } from "./client";

/* #27 Eignungsprofil — Stammdaten („Unser Unternehmen").
 *
 * Bewusst KEIN paralleles profile_company: die Stammdaten leben im vorhandenen
 * user_profiles.profile (jsonb, RLS über die Session) unter dem Schlüssel `stammdaten`.
 * Firmenname/Entity/Regionen/CPV/Wertgrenzen sind bereits Spalten in user_profiles
 * (einmal erfasst, überall verwendet — Akzeptanz #3). KMU wird BERECHNET, nie abgefragt (#27 §3). */

export type Rechtsform =
  | "GmbH" | "GmbH & Co. KG" | "AG" | "UG (haftungsbeschränkt)" | "OHG" | "KG"
  | "GbR" | "e.K." | "Einzelunternehmen" | "eG" | "Sonstige";

export const RECHTSFORMEN: Rechtsform[] = [
  "GmbH", "GmbH & Co. KG", "AG", "UG (haftungsbeschränkt)", "OHG", "KG",
  "GbR", "e.K.", "Einzelunternehmen", "eG", "Sonstige",
];

export type Stammdaten = {
  rechtsform?: Rechtsform | null;
  // Umsatz der letzten drei Geschäftsjahre (in €), j1 = jüngstes
  umsatz_j1?: number | null;
  umsatz_j2?: number | null;
  umsatz_j3?: number | null;
  mitarbeiter?: number | null;
  gruendungsjahr?: number | null;
  sprache?: string; // V1: "de"
  erfasst_am?: string | null; // Erfassungsdatum (Aktualität, #27 §9)
};

export type KmuResult = {
  ist_kmu: boolean;
  kategorie: "kleinstunternehmen" | "kleines_unternehmen" | "mittleres_unternehmen" | "grossunternehmen" | "unbekannt";
  label: string;
  begruendung: string;
};

// EU-Definition (Empfehlung 2003/361/EG): Schwellen an Mitarbeiterzahl UND (Umsatz ODER Bilanzsumme).
// Wir kennen nur den Umsatz → Umsatz-Kriterium; Bilanzsumme bleibt außen vor (konservativ, transparent).
export function computeKmu(s: Stammdaten): KmuResult {
  const ma = s.mitarbeiter;
  // jüngster verfügbarer Jahresumsatz (EU: letztes abgeschlossenes Geschäftsjahr)
  const umsatz = [s.umsatz_j1, s.umsatz_j2, s.umsatz_j3].find((v) => v != null && v > 0) ?? null;
  if (ma == null || umsatz == null) {
    return { ist_kmu: false, kategorie: "unbekannt", label: "unbekannt",
             begruendung: "Mitarbeiterzahl und Umsatz nötig, um den KMU-Status zu berechnen." };
  }
  const MIO = 1_000_000;
  const fmt = (v: number) => `${(v / MIO).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Mio €`;
  let kat: KmuResult["kategorie"], label: string;
  if (ma < 10 && umsatz <= 2 * MIO) { kat = "kleinstunternehmen"; label = "Kleinstunternehmen"; }
  else if (ma < 50 && umsatz <= 10 * MIO) { kat = "kleines_unternehmen"; label = "Kleines Unternehmen"; }
  else if (ma < 250 && umsatz <= 50 * MIO) { kat = "mittleres_unternehmen"; label = "Mittleres Unternehmen"; }
  else { kat = "grossunternehmen"; label = "Großunternehmen"; }
  const ist_kmu = kat !== "grossunternehmen";
  const begruendung = ist_kmu
    ? `KMU: ja — ${ma} Beschäftigte (< 250) und ${fmt(umsatz)} Umsatz (≤ 50 Mio €).`
    : `KMU: nein — ${ma} Beschäftigte oder ${fmt(umsatz)} Umsatz überschreiten die EU-Schwellen (250 / 50 Mio €).`;
  return { ist_kmu, kategorie: kat, label, begruendung };
}

/* ─────────────────────────── Erweitertes Profil-Modell (#27 §5–§10) ───────────────────────────
 * Alles lebt im selben user_profiles.profile jsonb — ein Datenpunkt, einmal erfasst (Akzeptanz #3).
 * Drei Zustände (§8): "angegeben" (Standard) · "belegt" (Nachweis hinterlegt) · "abgeleitet"
 * (vorbefüllt aus öffentlichen Daten — zählt erst nach Bestätigung, §7.1/§15). */

export type Zustand = "angegeben" | "belegt" | "abgeleitet";
export type Zielrichtung = "bestand" | "ausgewogen" | "expandieren";
export type AnforderungsArt = "binaer" | "schwelle" | "sammlung" | "kennung";

// Referenz (Sammlung, §2/§7.1) — speist Anforderungsprüfung, Textbaustein „Referenzen", Relevanz.
export type Reference = {
  id: string;
  projekt?: string | null;
  auftraggeber?: string | null;
  wert?: number | null;
  von?: string | null;       // Jahr/Datum Beginn
  bis?: string | null;       // Jahr/Datum Ende
  cpv?: string | null;
  quelle: Zustand;           // "abgeleitet" bis bestätigt → "angegeben"
  bestaetigt?: boolean;      // abgeleitete Referenz vom Nutzer bestätigt
};

// Zertifikat (§8/§9) — K.-o.-Prüfung + Textbaustein „Zertifikate & QM".
export type Certificate = {
  id: string;
  typ?: string | null;       // ISO 9001, ISO 27001, SCC, Präqualifikation …
  nummer?: string | null;
  aussteller?: string | null;
  gueltig_bis?: string | null;   // Pflicht bei „ja"; Erinnerung 90 T vorher
  zustand: Zustand;          // belegt = Nachweis hinterlegt
  nachweis?: string | null;  // Referenz auf verschlüsselten Upload (V1: Kennung/Notiz)
};

// Antwort auf einen Anforderungstyp aus dem Katalog (§5.3).
export type AttributeAnswer = {
  art: AnforderungsArt;
  value: boolean | number | string | null;   // binär→bool, schwelle→zahl, kennung→text
  einheit?: string | null;                    // schwelle: € / Personen / …
  zustand: Zustand;
  gueltig_bis?: string | null;
  changed_at?: string | null;
  changed_by?: string | null;
};

// Ausschlusskriterien (§6.3) — wirken auf die Listenqualität.
export type Exclusions = {
  wert_min?: number | null;
  wert_max?: number | null;
  regionen_aus?: string[];   // NUTS-Präfixe / Bundesland-Codes, die ausfallen
  cpv_aus?: string[];        // abgewählte CPV-Zweige
  keine_bietergemeinschaft?: boolean;
};

// Ansprechpartner-Rolle je Nutzer (§4) — Adressat der Alerts.
export type Role = {
  rolle?: "bid_manager" | "vertrieb" | "geschaeftsfuehrung" | "sonstige" | null;
  segmente?: string[];
  regionen?: string[];
};

export type HistoryEntry = { feld: string; at: string; by: string | null };

export type Branchen = { cpv: string[]; vorgeschlagen?: string[] };  // §6.1 vorgeschlagen + editierbar

export type Profil = {
  stammdaten: Stammdaten;
  references: Reference[];
  certificates: Certificate[];
  attributes: Record<string, AttributeAnswer>;   // key = Katalog-Anforderungs-ID
  exclusions: Exclusions;
  zielrichtung: Zielrichtung;
  branchen: Branchen;
  role: Role;
  history: HistoryEntry[];
};

export type ProfilContext = {
  companyName: string | null;
  identityId: string | null;
  entityConfidence: string | null;
  userEmail: string | null;
};

const EMPTY_PROFIL: Profil = {
  stammdaten: { sprache: "de" },
  references: [], certificates: [], attributes: {},
  exclusions: {}, zielrichtung: "ausgewogen",
  branchen: { cpv: [] }, role: {}, history: [],
};

function coerceProfil(raw: Record<string, unknown> | null | undefined): Profil {
  const r = (raw ?? {}) as Partial<Profil>;
  return {
    ...EMPTY_PROFIL,
    ...r,
    stammdaten: { sprache: "de", ...(r.stammdaten ?? {}) },
    references: Array.isArray(r.references) ? r.references : [],
    certificates: Array.isArray(r.certificates) ? r.certificates : [],
    attributes: (r.attributes && typeof r.attributes === "object") ? r.attributes : {},
    exclusions: (r.exclusions && typeof r.exclusions === "object") ? r.exclusions : {},
    zielrichtung: r.zielrichtung ?? "ausgewogen",
    branchen: r.branchen ?? { cpv: [] },
    role: r.role ?? {},
    history: Array.isArray(r.history) ? r.history : [],
  };
}

const TODAY = () => new Date().toISOString().slice(0, 10);

// Zentraler Merge-sicherer Schreiber: liest das Profil frisch, wendet `mutate` an,
// hängt einen History-Eintrag an und schreibt zurück. Verhindert Lost-Updates zwischen Sektionen.
async function patchProfil(feld: string, mutate: (p: Profil, by: string | null) => void): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  const { data } = await sb.from("user_profiles").select("profile").eq("id", user.id).single();
  const profile = coerceProfil(data?.profile as Record<string, unknown> | null);
  const by = user.email ?? null;
  mutate(profile, by);
  profile.history = [{ feld, at: new Date().toISOString(), by }, ...profile.history].slice(0, 200);
  const { error } = await sb.from("user_profiles").update({ profile }).eq("id", user.id);
  return { ok: !error, error: error?.message };
}

export async function loadProfil(): Promise<{ profil: Profil; ctx: ProfilContext } | null> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;
  const { data } = await sb.from("user_profiles")
    .select("company_name, identity_id, entity_confidence, profile").eq("id", user.id).single();
  if (!data) return null;
  return {
    profil: coerceProfil(data.profile as Record<string, unknown> | null),
    ctx: {
      companyName: (data.company_name as string) ?? null,
      identityId: (data.identity_id as string) ?? null,
      entityConfidence: (data.entity_confidence as string) ?? null,
      userEmail: user.email ?? null,
    },
  };
}

export async function loadStammdaten(): Promise<{ stammdaten: Stammdaten; companyName: string | null; identityId: string | null; entityConfidence: string | null } | null> {
  const r = await loadProfil();
  if (!r) return null;
  return { stammdaten: r.profil.stammdaten, companyName: r.ctx.companyName, identityId: r.ctx.identityId, entityConfidence: r.ctx.entityConfidence };
}

export async function saveStammdaten(stammdaten: Stammdaten): Promise<{ ok: boolean; error?: string }> {
  return patchProfil("stammdaten", (p) => {
    p.stammdaten = { ...stammdaten, sprache: stammdaten.sprache || "de", erfasst_am: TODAY() };
  });
}

export const saveReferences = (references: Reference[]) => patchProfil("references", (p) => { p.references = references; });
export const saveCertificates = (certificates: Certificate[]) => patchProfil("certificates", (p) => { p.certificates = certificates; });
export const saveExclusions = (exclusions: Exclusions) => patchProfil("exclusions", (p) => { p.exclusions = exclusions; });
export const saveZielrichtung = (z: Zielrichtung) => patchProfil("zielrichtung", (p) => { p.zielrichtung = z; });
export const saveBranchen = (cpv: string[]) => patchProfil("branchen", (p) => { p.branchen = { ...p.branchen, cpv }; });
export const saveRole = (role: Role) => patchProfil("role", (p) => { p.role = role; });

// Eine Katalog-Anforderung beantworten (§5.3). Stempelt Zustand + changed_by/at.
export function saveAttribute(key: string, ans: Omit<AttributeAnswer, "changed_at" | "changed_by">): Promise<{ ok: boolean; error?: string }> {
  return patchProfil(`attribute:${key}`, (p, by) => {
    p.attributes[key] = { ...ans, changed_at: new Date().toISOString(), changed_by: by };
  });
}

// Abgeleitete (vorbefüllte) Referenz bestätigen → zählt ab jetzt (§7.1/§15).
export function confirmReference(id: string): Promise<{ ok: boolean; error?: string }> {
  return patchProfil(`reference-confirm:${id}`, (p) => {
    const r = p.references.find((x) => x.id === id);
    if (r) { r.bestaetigt = true; r.quelle = "angegeben"; }
  });
}

/* ─────────────────────────── Vorbefüllung + Entity-Korrektur (§7.1/§7.3) ─────────────────────────── */

export type PrefillReference = {
  notice_id: string; projekt: string; auftraggeber: string | null; wert: number | null;
  von: number | null; bis: number | null; cpv: string | null; cpv_label: string | null;
};
export type Prefill = {
  id: string; name: string; confidence: string; wins_total: number;
  references: PrefillReference[];
  cpv_schwerpunkte: { code: string; label: string; pct: number }[];
  regionen: { code: string; label: string; pct: number }[];
  umsatz_naeherung: number | null; umsatz_coverage: number;
  entity_members: { entity_id: string; name: string | null; method: string; confidence: number | null; belegt: boolean }[];
  error?: string;
};

export async function fetchVorbefuellung(identityId: string): Promise<Prefill | { error: string }> {
  try {
    const r = await fetch(`/api/unternehmen/vorbefuellung?id=${encodeURIComponent(identityId)}`);
    return (await r.json()) as Prefill;
  } catch (e) {
    return { error: String((e as Error).message).slice(0, 160) };
  }
}

// Vorbefüllte Referenzen als „abgeleitet" ins Profil übernehmen (Dedupe über notice_id).
// Sie zählen erst nach Bestätigung (§7.1/§15).
export function applyPrefillReferences(existing: Reference[], prefill: PrefillReference[]): Reference[] {
  const seen = new Set(existing.map((r) => r.id));
  const derived: Reference[] = prefill
    .filter((p) => !seen.has(`ted:${p.notice_id}`))
    .map((p) => ({
      id: `ted:${p.notice_id}`, projekt: p.projekt, auftraggeber: p.auftraggeber,
      wert: p.wert, von: p.von ? String(p.von) : null, bis: p.bis ? String(p.bis) : null,
      cpv: p.cpv, quelle: "abgeleitet" as Zustand, bestaetigt: false,
    }));
  return [...existing, ...derived];
}

// Identitäts-Korrektur (§7.3): der Nutzer ordnet die Firma einer anderen Identität zu.
// Wirkung: Vorbefüllung wird neu berechnet; bestätigte Angaben bleiben (patchProfil rührt sie nicht an).
export async function saveIdentityCorrection(identityId: string, companyName: string | null, confidence: string): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  const patch: Record<string, unknown> = { identity_id: identityId, entity_confidence: confidence };
  if (companyName) patch.company_name = companyName;
  const { error } = await sb.from("user_profiles").update(patch).eq("id", user.id);
  if (error) return { ok: false, error: error.message };
  // History-Vermerk der Korrektur
  await patchProfil("entity-korrektur", () => { /* Zuordnung in Spalten, hier nur Protokoll */ });
  return { ok: true };
}

/* ─────────────────────────── Ableitungen (Wirkung, Ablauf) ─────────────────────────── */

// Tage bis Ablauf (negativ = abgelaufen). null wenn kein Datum.
export function daysUntil(iso?: string | null): number | null {
  if (!iso) return null;
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : "")).getTime();
  if (Number.isNaN(d)) return null;
  return Math.floor((d - Date.now()) / 86_400_000);
}

// Zertifikat gilt nur, wenn nicht abgelaufen (§9: abgelaufen zählt NICHT als erfüllt).
export function certValid(c: Certificate): boolean {
  const dd = daysUntil(c.gueltig_bis);
  return dd === null || dd >= 0;
}

// „Wirkung sichtbar machen" (§7.4): unbeantwortete Angaben + bald ablaufende Zertifikate.
// requiredKeys = Katalog-Anforderungen, die für die aktive Branche gelten.
export function wirkung(profil: Profil, requiredKeys: string[]): { offen: number; ablaufend: number; abgelaufen: number; abgeleitet_offen: number } {
  const answered = (k: string) => {
    const a = profil.attributes[k];
    if (!a) return false;
    if (a.zustand === "abgeleitet") return false;   // zählt erst nach Bestätigung
    return a.value !== null && a.value !== undefined && a.value !== "";
  };
  const offen = requiredKeys.filter((k) => !answered(k)).length;
  let ablaufend = 0, abgelaufen = 0;
  for (const c of profil.certificates) {
    const dd = daysUntil(c.gueltig_bis);
    if (dd === null) continue;
    if (dd < 0) abgelaufen++;
    else if (dd <= 90) ablaufend++;
  }
  const abgeleitet_offen = profil.references.filter((r) => r.quelle === "abgeleitet" && !r.bestaetigt).length
    + Object.values(profil.attributes).filter((a) => a.zustand === "abgeleitet").length;
  return { offen, ablaufend, abgelaufen, abgeleitet_offen };
}
