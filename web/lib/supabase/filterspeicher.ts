"use client";
import { createClient } from "./client";
import { mischen as _mischen } from "../filterMischen.js";

/* Gespeicherte Filter ↔ user_filter (0022).
 *
 * Eine gespeicherte Sicht ist mehr als der Filterzustand: Grundraum, Schnellfilter,
 * Suchtext, Suchtoken und Sortierung gehoeren dazu. Wer nur `adv` sichert, bekommt eine
 * fremde Liste zurueck und haelt das Speichern fuer kaputt.
 *
 * ⚠ DER SUCHTEXT WIRD ROH GESPEICHERT, die Token daneben. Token sind ein Zwischenergebnis
 * und entstehen ausserdem nicht nur aus dem Text (ein Klick auf einen Kaeufer erzeugt auch
 * eines). Beides zu sichern ist die einzige Fassung, die dieselbe Liste zurueckgibt.
 *
 * ⚠ FASSUNG MITSPEICHERN. `Adv` waechst. Beim Lesen wird gegen die heutige Vorgabe
 * gemischt (s. `mischen`): fehlende Schluessel bekommen ihren Vorgabewert, unbekannte
 * fliegen raus. Ohne das laedt ein alter Filter scheinbar sauber und filtert anders. */

export const FILTER_FASSUNG = 1;

export type GespeicherterFilter = {
  id: string;
  name: string;
  fassung: number;
  zustand: Record<string, unknown>;
  zuletzt_genutzt: string | null;
};

/* ⚠ Die Mischung liegt in `lib/filterMischen.js`, in reinem JS — damit der Waechter
 * `pruefe-filtermischen.mjs` die ECHTE Funktion fahren kann und nicht nur Worte prueft.
 * Dieselbe Bauweise wie `filterMarken.js`. */
export function mischen<T extends Record<string, unknown>>(vorgabe: T, gespeichert: unknown): T {
  return _mischen(vorgabe, gespeichert) as T;
}

export async function ladeFilter(): Promise<GespeicherterFilter[]> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return [];
    const { data } = await sb.from("user_filter")
      .select("id, name, fassung, zustand, zuletzt_genutzt")
      .eq("user_id", user.id)
      .order("zuletzt_genutzt", { ascending: false, nullsFirst: false });
    return (data as GespeicherterFilter[]) || [];
  } catch { return []; }
}

/** Anlegen oder ueberschreiben. Gibt die Zeile zurueck, damit die Liste ohne Neuladen stimmt. */
export async function speichereFilter(
  name: string, zustand: Record<string, unknown>,
): Promise<GespeicherterFilter | null> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return null;
    const { data } = await sb.from("user_filter")
      .upsert({ user_id: user.id, name: name.trim().slice(0, 80),
                fassung: FILTER_FASSUNG, zustand, zuletzt_genutzt: new Date().toISOString() },
              { onConflict: "user_id,name" })
      .select("id, name, fassung, zustand, zuletzt_genutzt").single();
    return (data as GespeicherterFilter) || null;
  } catch { return null; }
}

export async function loescheFilter(id: string): Promise<void> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    await sb.from("user_filter").delete().eq("user_id", user.id).eq("id", id);
  } catch { /* no-op */ }
}

/** Nur den Zeitstempel anfassen, damit die Liste nach Gebrauch sortiert. */
export async function merkeGebrauch(id: string): Promise<void> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return;
    await sb.from("user_filter").update({ zuletzt_genutzt: new Date().toISOString() })
      .eq("user_id", user.id).eq("id", id);
  } catch { /* no-op */ }
}
