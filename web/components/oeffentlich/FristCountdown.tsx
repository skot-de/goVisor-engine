"use client";

import { useEffect, useState } from "react";

/**
 * Countdown bis zur Angebotsfrist, clientseitig (§6.1): nach Fristablauf wechselt die Anzeige
 * sofort auf „Frist abgelaufen", auch bevor die Seite neu gebaut wird. Server und Client
 * zeigen beim ersten Rendern dieselbe Zahl (aus `date`), damit kein Hydration-Sprung entsteht.
 *
 * `date` kommt als "TT.MM.JJJJ", `uhrzeit` optional als "HH:MM".
 */
export function FristCountdown({ date, uhrzeit }: { date: string; uhrzeit: string | null }) {
  const ziel = parse(date, uhrzeit);
  const [tage, setTage] = useState<number | null>(() => (ziel ? restTage(ziel) : null));

  useEffect(() => {
    if (!ziel) return;
    const t = setInterval(() => setTage(restTage(ziel)), 60_000);
    setTage(restTage(ziel));
    return () => clearInterval(t);
  }, [date, uhrzeit]); // eslint-disable-line react-hooks/exhaustive-deps

  if (tage == null) return null;
  if (tage < 0) return <span className="aus-frist-ab">Frist abgelaufen</span>;
  if (tage === 0) return <span className="aus-frist-rest">heute</span>;
  return <span className="aus-frist-rest">noch {tage} {tage === 1 ? "Tag" : "Tage"}</span>;
}

function parse(date: string, uhrzeit: string | null): Date | null {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})$/.exec(date);
  if (!m) return null;
  const [hh, mm] = (uhrzeit ?? "23:59").split(":").map((x) => Number(x) || 0);
  return new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]), hh, mm, 0, 0);
}

function restTage(ziel: Date): number {
  const jetzt = new Date();
  return Math.floor((ziel.getTime() - jetzt.getTime()) / 86_400_000);
}
