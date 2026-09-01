"use client";
import { createClient } from "./client";

/* Beobachtete Vergabestellen (Aktivierung D).
 *
 * ⚠ KEINE VORHERSAGE. Das Übergabepapier schlägt vor: „Diese Stelle schreibt etwa alle vier
 * Jahre aus. Sollen wir euch erinnern?" Am 2026-09-01 nachgemessen ist dieser Satz nicht
 * belegbar: `contract_succession` liefert für jede grosse Vergabestelle einen Median-Abstand
 * von 1,0 Jahren, und das ist eine Eigenschaft des Nachfolge-Modells, kein Vertragszyklus.
 * `buyer_loyalty` und `retender_signal` tragen gar keine Zykluslänge.
 *
 * Die Beobachtung sagt deshalb nur zu, was sie halten kann: Bescheid geben, wenn die Stelle
 * etwas ausschreibt. Das ist weniger als im Papier und dafür wahr.
 *
 * ⚠ DER NAME IST DER SCHLÜSSEL, kleingeschrieben und getrimmt. Eine Entitäts-ID wäre
 * stabiler, aber der Lead-Export trägt sie nicht. Lieber ein Schlüssel, der gelegentlich zwei
 * Schreibweisen trennt, als einer, den niemand füllen kann. */
export const buyerKey = (name: string) => String(name || "").trim().toLowerCase().slice(0, 120);

export async function loadBuyerWatch(): Promise<Set<string>> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return new Set();
    const { data } = await sb.from("user_buyer_watch").select("buyer_key").eq("user_id", user.id);
    return new Set((data || []).map((r: { buyer_key: string }) => r.buyer_key));
  } catch { return new Set(); }
}

/** An- oder abschalten. Rückgabe: der neue Zustand, oder null wenn es nicht geklappt hat.
 *  ⚠ `null` heisst „nicht gespeichert" und muss die Oberfläche erreichen — ein stiller
 *  Fehlschlag liesse den Knopf umspringen, ohne dass irgendwo etwas steht. */
export async function toggleBuyerWatch(name: string, an: boolean): Promise<boolean | null> {
  try {
    const sb = createClient();
    const { data: { user } } = await sb.auth.getUser();
    if (!user) return null;
    const key = buyerKey(name);
    if (!key) return null;
    if (an) {
      const { error } = await sb.from("user_buyer_watch")
        .upsert({ user_id: user.id, buyer_key: key, buyer_name: name },
                { onConflict: "user_id,buyer_key" });
      return error ? null : true;
    }
    const { error } = await sb.from("user_buyer_watch")
      .delete().eq("user_id", user.id).eq("buyer_key", key);
    return error ? null : false;
  } catch { return null; }
}
