"use client";

import Link from "next/link";
import { useSprache } from "@/lib/i18n";

/**
 * Sperrschicht fuer einen Vorgang ueber dem Monatskontingent (Preismodell v1.9 §4.1 Blur /
 * §4.2 CTA). Legt sich ueber den (weichgezeichneten) Inhalt und nennt konkret, was diese
 * Ansicht liefert — nie ein generisches „Jetzt upgraden" (§4.2).
 *
 * ⚠ Nur fuer das MENGEN-Gate (3 Vorgaenge/Monat) gedacht. Die tier-basierte Premium-Redaktion
 * (Wettbewerb/Strategie) haelt die echten Werte serverseitig zurueck (lib/redact.ts) — ein
 * CSS-Blur allein waere dort per DevTools lesbar. Hier geht es um bereits sichtbare Lead-Daten,
 * deren tiefe Auswertung monatlich gestaffelt ist; dafuer ist Blur die richtige Form.
 */
export function KontingentSperre({ was }: { was: string }) {
  const { t } = useSprache();
  return (
    <div className="kgate-overlay" role="note">
      <div className="kgate-card">
        <b>{t("Monatskontingent erreicht")}</b>
        <p>{t("Dieser Vorgang ist neu. {was} gibt es unbegrenzt mit Analyse.", { was })}</p>
        <Link className="kgate-cta" href="/settings?sek=zahlung">{t("Unbegrenzt mit Analyse")}</Link>
        <span className="kgate-hint">{t("Schon aufgeschlossene Vorgaenge bleiben offen.")}</span>
      </div>
    </div>
  );
}
