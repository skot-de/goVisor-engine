"use client";
/**
 * Das eigene Firmenprofil — an EINER Stelle geladen, von jeder Seite lesbar.
 *
 * **Warum es das gibt.** Der Profil-Knopf hing bis 2026-08-16 an einem lokalen `useState`
 * in `ExplorerShell`. Er konnte deshalb nur dort stehen — und stand folglich auf
 * „Unternehmen", „Bausteine" und „Einstellungen" gar nicht, obwohl das die Seiten sind,
 * auf denen man am ehesten nach seinem Profil sucht. Das war kein Gestaltungsbeschluss,
 * sondern eine Folge davon, wo der Zustand zufällig lag.
 *
 * **Reihenfolge der Quellen — und warum.** Erst der angemeldete Nutzer (Supabase), dann
 * der lokale Zwischenspeicher. Umgekehrt sähe man beim Seitenwechsel kurz ein veraltetes
 * Profil aufblitzen. Der Zwischenspeicher ist trotzdem nötig: ohne ihn wäre der Knopf bei
 * JEDEM Seitenwechsel für einen Netzwerk-Umlauf lang leer, und ein Element, das erst
 * „Profil einrichten" zeigt und dann den Firmennamen, liest sich wie ein Fehler.
 */
import { useEffect, useState } from "react";
import { currentUser, loadProfile, type Profile } from "@/lib/supabase/auth";

export const PROFILE_KEY = "govisor.profile.v1";

/**
 * Signal an alle Profil-Anzeigen: der Zwischenspeicher hat sich geändert, bitte neu lesen.
 *
 * Nötig, weil der Hook sonst nur beim Einhängen liest. Beim Abmelden räumt die Shell den
 * Speicher, bleibt selbst aber eingehängt — ohne dieses Signal stünde der Firmenname des
 * abgemeldeten Nutzers weiter im Kopf, bis jemand die Seite neu lädt. Das `storage`-
 * Ereignis des Browsers hilft hier nicht: es feuert nur in ANDEREN Tabs, nie im eigenen.
 */
export const PROFIL_EREIGNIS = "govisor:profil";

/** Auslösen, wann immer PROFILE_KEY geschrieben oder entfernt wurde. */
export function profilGeaendert(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(PROFIL_EREIGNIS));
}

// Kein eigener Typ neben `Profile`: der hier gebrauchte Wert IST der aus dem Auth-Layer.
// Ein paralleler Typ waere die naechste Insel — er wuerde beim ersten Feldwechsel driften.
export type Profil = Profile;

/** Liest das Profil aus dem Zwischenspeicher — synchron, für den ersten Bildaufbau. */
function ausSpeicher(): Profil | null {
  if (typeof window === "undefined") return null;
  try {
    const roh = localStorage.getItem(PROFILE_KEY);
    return roh ? (JSON.parse(roh) as Profil) : null;
  } catch {
    return null;                       // ungültiger Inhalt → behandeln wie „keins"
  }
}

export function useProfil(): Profil | null {
  // Startwert bewusst `null` und NICHT `ausSpeicher()`: der Server rendert ohne
  // localStorage, ein abweichender erster Client-Aufbau wäre ein Hydrations-Fehler.
  const [profil, setProfil] = useState<Profil | null>(null);

  useEffect(() => {
    let abbruch = false;
    setProfil(ausSpeicher());          // sofort das Bekannte zeigen …
    (async () => {                     // … und dahinter den echten Stand holen
      const u = await currentUser().catch(() => null);
      if (!u || abbruch) return;
      const fern = await loadProfile().catch(() => null);
      if (!fern || abbruch) return;
      setProfil(fern);
      try {
        localStorage.setItem(PROFILE_KEY, JSON.stringify(fern));
      } catch {
        /* Speicherquote — der Knopf funktioniert auch ohne Zwischenspeicher */
      }
    })();
    function neuLesen() { setProfil(ausSpeicher()); }
    window.addEventListener(PROFIL_EREIGNIS, neuLesen);
    return () => {
      abbruch = true;
      window.removeEventListener(PROFIL_EREIGNIS, neuLesen);
    };
  }, []);

  return profil;
}
