"use client";

import { useEffect, useState } from "react";
import { useSprache } from "@/lib/i18n";

/**
 * Vorgangs-Zaehler im Kopf (Preismodell v1.9 §4.2 „2 von 3 Vorgaengen diesen Monat").
 * Quelle: GET /api/kontingent (lib/kontingent.ts). Aktualisiert sich bei 'kontingent:changed'
 * (feuert lib/kontingentClient.ts nach einer Freischaltung).
 *
 * ⚠ ZEIGT SICH NUR BEI BEGRENZUNG. Ist das Limit null (bezahlte Stufe ODER Paywall aus =
 * heutiger Zustand), rendert die Komponente NICHTS — kein „unbegrenzt"-Chrom fuer alle.
 * Damit ist sie heute unsichtbar und wird erst mit scharfer Paywall + Free-Stufe sichtbar.
 */
type Stand = { verbraucht: number; limit: number | null; offen: number | null };

export function Kontingent() {
  const { t } = useSprache();
  const [stand, setStand] = useState<Stand | null>(null);

  useEffect(() => {
    let weg = false;
    const laden = () => fetch("/api/kontingent", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!weg && d && typeof d.verbraucht === "number") setStand(d); })
      .catch(() => { /* nicht angemeldet o. Ae. — dann kein Zaehler */ });
    laden();
    const auf = () => laden();
    window.addEventListener("kontingent:changed", auf);
    return () => { weg = true; window.removeEventListener("kontingent:changed", auf); };
  }, []);

  // Unbegrenzt (Paywall aus / bezahlte Stufe) → nichts anzeigen.
  if (!stand || stand.limit == null) return null;

  const voll = stand.verbraucht >= stand.limit;
  return (
    <span className={`kontingent ${voll ? "kontingent-voll" : ""}`}
      title={t("Freie Vorgaenge diesen Monat. Ein aufgeschlossener Vorgang bleibt dauerhaft offen.")}>
      <span className="kontingent-zahl">{stand.verbraucht}/{stand.limit}</span>
      <span className="kontingent-lbl">{t("Vorgaenge")}</span>
    </span>
  );
}
