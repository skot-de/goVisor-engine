"use client";
import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { beginneSeite, starteTelemetrie } from "@/lib/telemetrie";

/**
 * Haengt die Telemetrie-Sammler ein. Gehoert einmal ins Wurzel-Layout.
 *
 * ⚠ RENDERT NICHTS. Kein Zaehlpixel, kein Script-Tag, kein Wrapper um `children`. Ticket 17
 *   §6.2 verlangt, dass Googlebot exakt dieselbe Seite bekommt wie ein Mensch; jedes
 *   zusaetzliche Element im Markup waere ein Unterschied — und ein Zaehlpixel waere obendrein
 *   nutzlos, weil Crawler es nicht laden. Die oeffentlichen Seiten werden deshalb
 *   SERVERSEITIG gezaehlt (s. `erfasseSeitenaufruf` in telemetrieSenke.ts), nicht hier.
 *
 * ⚠ `usePathname` STATT EINES EINMALIGEN EFFEKTS. Der App Router wechselt die Route ohne
 *   Neuladen. Ein Effekt mit leerer Abhaengigkeitsliste zaehlte eine ganze Sitzung als EINEN
 *   Seitenaufruf und verlor jede Verweildauer ausser der letzten.
 */
export default function Telemetrie() {
  const pfad = usePathname();

  useEffect(() => { starteTelemetrie(); }, []);
  useEffect(() => { if (pfad) beginneSeite(pfad); }, [pfad]);

  return null;
}
