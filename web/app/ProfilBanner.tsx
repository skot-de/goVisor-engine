"use client";
/**
 * Dauerhafter Hinweis, dass gerade eine fremde Kundensicht aktiv ist.
 *
 * Das ist nicht Kosmetik, sondern der Kern der Sache. „Vorführung" und „Test" sehen in der App
 * fast identisch aus wie der Normalbetrieb — ohne stehenden Hinweis verwechselt man nach zehn
 * Minuten Testdaten mit echten. Der teuerste Fall ist nicht der falsche Klick, sondern die
 * falsche Erinnerung: man erzählt jemandem später eine Zahl, die aus einem Testprofil stammt.
 *
 * Deshalb: immer sichtbar, nicht wegklickbar, und mit dem Ausstieg direkt daneben.
 */
import { useEffect, useState } from "react";
import { gewaehltesProfil, darfSchreiben, type Testprofil } from "@/lib/testprofile";

export default function ProfilBanner() {
  const [profil, setProfil] = useState<Testprofil | null>(null);

  useEffect(() => {
    setProfil(gewaehltesProfil());
  }, []);

  if (!profil) return null;
  const nurLesen = !darfSchreiben(profil);

  return (
    <div className={`profil-banner ${nurLesen ? "profil-banner--lesen" : "profil-banner--test"}`}
         role="status">
      <span className="profil-banner-punkt" aria-hidden="true" />
      <span>
        Kundensicht <strong>{profil.name}</strong>
        {nurLesen ? " · nur lesen" : " · volle Rechte, Änderungen wirken"}
      </span>
      <a href="/start" className="profil-banner-raus">verlassen</a>
    </div>
  );
}
