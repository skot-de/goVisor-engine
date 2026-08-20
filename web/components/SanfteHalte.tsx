"use client";

import { useEffect } from "react";

/**
 * Sanftes Andocken an die Abschnittsanfänge.
 *
 * **Warum nicht `scroll-snap-type`.** CSS kennt genau zwei Stärken: `mandatory` zwingt,
 * `proximity` „schlägt vor". Gemessen am 2026-08-21 in Chrome zieht schon `proximity` aus
 * rund 300 px Entfernung — bei unseren Abständen fühlt es sich fast wie Zwang an, und Sven
 * wollte es „nicht ganz so sticky". Einen Regler für die Fangweite gibt es in CSS nicht.
 *
 * Also hier, mit drei Bedingungen, die zusammen den Unterschied ausmachen:
 *   1. Es zieht erst, wenn das Scrollen AUFGEHÖRT hat (140 ms Ruhe). Wer weiterscrollt,
 *      wird nie unterbrochen — das ist der eigentliche Unterschied zu CSS-Snap, der schon
 *      während der Bewegung eingreift.
 *   2. Es zieht nur aus {@link FANG} Pixeln Entfernung statt aus dreihundert.
 *   3. Es zieht nur, wenn der Weg kurz genug ist, um nicht als Sprung zu wirken.
 *
 * Aus dem Weg geht es bei `prefers-reduced-motion`, auf schmalen und niedrigen Fenstern,
 * und wenn eine Tastatureingabe oder ein Ankersprung läuft. Ein Abschnitt kann sich per
 * `lp-halt` selbst abmelden — das Werkzeug tut das, sobald seine Auswertung offen ist und
 * es höher wird als das Fenster.
 */
const FANG = 90;          // px: darunter wird angedockt, darüber bleibt alles, wie es ist
const RUHE = 140;         // ms ohne Scroll-Ereignis, bevor überhaupt geprüft wird
const KOPFHOEHE = 78;     // px: die klebende Kopfleiste, die über dem Abschnitt steht

export function SanfteHalte() {
  useEffect(() => {
    const schmal = window.matchMedia("(max-width: 900px), (max-height: 700px)");
    const ruhig = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (schmal.matches || ruhig.matches) return;

    let uhr: number | undefined;
    let eigenerLauf = 0;

    const pruefen = () => {
      // Nicht in die eigene sanfte Bewegung hineinregeln.
      if (Date.now() < eigenerLauf) return;
      const y = window.scrollY;
      if (y < 40 || y + window.innerHeight >= document.body.scrollHeight - 40) return;

      let bester: number | null = null;
      for (const el of document.querySelectorAll<HTMLElement>(".lp-halt")) {
        const ziel = Math.round(el.getBoundingClientRect().top + y - KOPFHOEHE);
        const weg = Math.abs(ziel - y);
        if (weg > 2 && weg <= FANG && (bester === null || weg < Math.abs(bester - y))) {
          bester = ziel;
        }
      }
      if (bester === null) return;
      eigenerLauf = Date.now() + 700;
      window.scrollTo({ top: bester, behavior: "smooth" });
    };

    const beiScroll = () => {
      window.clearTimeout(uhr);
      uhr = window.setTimeout(pruefen, RUHE);
    };
    window.addEventListener("scroll", beiScroll, { passive: true });
    return () => { window.removeEventListener("scroll", beiScroll); window.clearTimeout(uhr); };
  }, []);

  return null;
}
