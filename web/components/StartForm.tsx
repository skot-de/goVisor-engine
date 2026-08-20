"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

/**
 * Der Schluss-Einstieg: ein Feld, ein Knopf.
 *
 * **Warum Firmenname und nicht E-Mail.** Die Vorlage (`INPUT/…/govisor-landing-v28.html`)
 * hatte hier ein E-Mail-Feld. Eine Adresse einzusammeln, bevor irgendjemand etwas gesehen
 * hat, ist der teuerste Moment im ganzen Trichter — und wir hätten nichts damit zu tun,
 * ausser sie zu speichern. Der Firmenname dagegen ist genau die erste Frage des
 * Onboardings („Wie heisst eure Firma?"); wer ihn hier tippt, hat den ersten Schritt
 * schon hinter sich, und wir bekommen keine personenbezogene Angabe in die Hand.
 *
 * Der Name wandert als Parameter weiter und wird dort NUR VORGESCHLAGEN: bestätigt wird er
 * über die Firmensuche wie jeder andere Treffer auch.
 */
export function StartForm() {
  const router = useRouter();
  const [name, setName] = useState("");

  return (
    <form
      className="lp-startform"
      onSubmit={(e) => {
        e.preventDefault();
        const w = name.trim();
        router.push(w ? `/onboarding?firma=${encodeURIComponent(w.slice(0, 120))}` : "/onboarding");
      }}
    >
      <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120}
             placeholder="Name eurer Firma" aria-label="Name eurer Firma" />
      <button type="submit" aria-label="Weiter zum Profil">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2.5"
                strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
    </form>
  );
}
