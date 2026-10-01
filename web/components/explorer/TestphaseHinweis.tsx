"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSprache } from "@/lib/i18n";

/**
 * Testphasen-Hinweis im Kopf (Preismodell v1.9 §3a / §4.2). Quelle: /api/testphase.
 *   - laeuft noch (> 7 Tage): ruhige Restlaufzeit, KEIN Upgrade-Druck (§4.2).
 *   - endet in <= 7 Tagen: deutlicher Hinweis mit Nutzungsbezug + Upgrade-CTA (§3a).
 * Keine Testphase → nichts (die meisten Konten; dann ist es hier still).
 */
type Stand = { trial: boolean; tage_rest?: number; genutzt?: number; limit_free?: number };

export function TestphaseHinweis() {
  const { t } = useSprache();
  const [s, setS] = useState<Stand | null>(null);

  useEffect(() => {
    let weg = false;
    fetch("/api/testphase", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (!weg && d) setS(d); })
      .catch(() => { /* nicht angemeldet o. Ae. — kein Hinweis */ });
    return () => { weg = true; };
  }, []);

  if (!s || !s.trial) return null;
  const tage = s.tage_rest ?? 0;
  const bald = tage <= 7;
  const titel = t("{n} Vorgaenge aufgeschlossen. Danach {limit} im Monat.",
    { n: s.genutzt ?? 0, limit: s.limit_free ?? 3 });

  return (
    <Link className={`testphase ${bald ? "testphase-bald" : ""}`} href="/settings?sek=zahlung" title={titel}>
      {bald ? t("Testphase endet in {n} Tagen", { n: tage }) : t("Testphase: noch {n} Tage", { n: tage })}
    </Link>
  );
}
