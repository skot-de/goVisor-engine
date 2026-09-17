"use client";
import { createClient } from "./client";

/* Der EINE Schreibweg auf `user_profiles.profile`.
 *
 * WARUM ES IHN GIBT. Der Blob wurde von zwei Stellen geschrieben, beide nach demselben
 * Muster: lesen, im Client aendern, ganzen Blob zurueckschreiben.
 *
 *     auth.ts         saveProfile   Passung, Regionen, Wertspanne
 *     unternehmen.ts  patchProfil   Eignungsangaben (#27), Historie
 *
 * Zwischen Lesen und Schreiben liegt ein Fenster. Schreibt die andere Stelle darin, ist
 * ihre Aenderung weg. `patchProfil` trug dazu den Kommentar „Verhindert Lost-Updates
 * zwischen Sektionen" — das stimmte nur gegen sich selbst.
 *
 * Zugeschlagen hat es am 2026-09-17 im Onboarding: `saveProfile` und die Uebernahme des
 * Eignungs-Checks liefen nebenlaeufig, der spaetere gewann, der Nutzer sah „0 von 7.013".
 * Dort wurden die Aufrufe gereiht — das behebt den einen Fall, nicht die Fehlerklasse.
 */

/** Fehlt die Datenbankfunktion, sagt PostgREST das mit diesem Code (bzw. dieser Meldung). */
function funktionFehlt(e: { code?: string; message?: string } | null): boolean {
  if (!e) return false;
  return e.code === "PGRST202" || /function .*merge_profile.* does not exist/i.test(e.message || "");
}

let gewarnt = false;

/**
 * Mischt `patch` in den Profil-Blob — atomar, wenn die Datenbank es kann.
 *
 * ⚠ FLACHER MERGE. Ein Schluessel im Patch ersetzt den gleichnamigen im Blob vollstaendig;
 * verschachtelte Objekte werden NICHT rekursiv gemischt. Das ist hier richtig, weil jedes
 * Feld genau einem Aufrufer gehoert. Wer das aendert, muss diesen Satz neu pruefen.
 *
 * ⚠ EIN FELD LOESCHEN heisst `{ feld: null }` schicken, nicht weglassen. Ein weggelassenes
 * Feld bleibt stehen — das ist der Sinn des Merges.
 */
export async function mischeProfilBlob(
  patch: Record<string, unknown>,
): Promise<{ ok: boolean; error?: string }> {
  const sb = createClient();
  const { data: { user } } = await sb.auth.getUser();
  if (!user) return { ok: false, error: "no-session" };
  if (!patch || typeof patch !== "object") return { ok: false, error: "patch-kein-objekt" };

  const { error } = await sb.rpc("merge_profile", { p_patch: patch });
  if (!error) return { ok: true };
  if (!funktionFehlt(error)) return { ok: false, error: error.message };

  /* ⚠ RUECKFALL, KEIN DAUERZUSTAND. Solange `supabase/0020_profil_atomar_mischen.sql`
   * nicht eingespielt ist, muss das Speichern trotzdem funktionieren — aber es hat dann
   * wieder das Fenster, das diese Datei abschaffen soll. Deshalb LAUT: eine Zeile im
   * Protokoll ist der Unterschied zwischen „Migration steht aus" und „wir haben nichts
   * gewonnen und niemand hat es gemerkt". Dieselbe Form wie der Rueckfall in
   * `lib/leadIndex.ts`. */
  if (!gewarnt) {
    console.error("[profil] `merge_profile` fehlt in der Datenbank — Rueckfall auf "
                + "Lesen-Aendern-Schreiben, das Lost-Update-Fenster ist wieder offen. "
                + "supabase/0020_profil_atomar_mischen.sql einspielen.");
    gewarnt = true;
  }
  const { data } = await sb.from("user_profiles").select("profile").eq("id", user.id).single();
  const vorher = (data?.profile as Record<string, unknown> | null) ?? {};
  const { error: e2 } = await sb.from("user_profiles")
    .update({ profile: { ...vorher, ...patch } }).eq("id", user.id);
  return { ok: !e2, error: e2?.message };
}

/**
 * Welche Schluessel der obersten Ebene hat `mutate` veraendert?
 *
 * ⚠ WOFUER. `patchProfil` nimmt eine beliebige Aenderungsfunktion entgegen und weiss
 * hinterher nicht, WAS sie angefasst hat. Den ganzen Blob zurueckzuschicken macht aus dem
 * Merge wieder ein Ueberschreiben — dann ist nichts gewonnen. Der Vergleich Schluessel fuer
 * Schluessel liefert den kleinstmoeglichen Patch.
 */
export function geaenderteFelder(
  vorher: Record<string, unknown>, nachher: Record<string, unknown>,
): Record<string, unknown> {
  const patch: Record<string, unknown> = {};
  for (const k of new Set([...Object.keys(vorher), ...Object.keys(nachher)])) {
    if (JSON.stringify(vorher[k]) !== JSON.stringify(nachher[k])) patch[k] = nachher[k] ?? null;
  }
  return patch;
}
