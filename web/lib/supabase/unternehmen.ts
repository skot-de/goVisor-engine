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

export async function loadStammdaten(): Promise<{ stammdaten: Stammdaten; companyName: string | null; identityId: string | null; entityConfidence: string | null } | null> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return null;
  const { data } = await sb.from("user_profiles")
    .select("company_name, identity_id, entity_confidence, profile").eq("id", user.id).single();
  if (!data) return null;
  const profile = (data.profile as Record<string, unknown> | null) ?? {};
  const stammdaten = (profile.stammdaten as Stammdaten | undefined) ?? { sprache: "de" };
  return {
    stammdaten,
    companyName: (data.company_name as string) ?? null,
    identityId: (data.identity_id as string) ?? null,
    entityConfidence: (data.entity_confidence as string) ?? null,
  };
}

export async function saveStammdaten(stammdaten: Stammdaten): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  // profile jsonb merge-sicher lesen → stammdaten setzen → zurückschreiben
  const { data } = await sb.from("user_profiles").select("profile").eq("id", user.id).single();
  const profile = ((data?.profile as Record<string, unknown> | null) ?? {});
  profile.stammdaten = { ...stammdaten, sprache: stammdaten.sprache || "de", erfasst_am: new Date().toISOString().slice(0, 10) };
  const { error } = await sb.from("user_profiles").update({ profile }).eq("id", user.id);
  return { ok: !error, error: error?.message };
}
