"use client";
import { useEffect, useState } from "react";
import { entscheide, entscheidung, widerspruch } from "@/lib/telemetrie";

/**
 * Einwilligungshinweis fuer die Messung (Stufe 2, s. 0036).
 *
 * ⚠ NOCH NICHT EINGEHAENGT, UND DAS IST ABSICHT. Dieser Hinweis verweist auf die
 *   Datenschutzerklaerung, und die gibt es in `web/app/` nicht. Ein Einwilligungshinweis,
 *   der auf eine 404-Seite zeigt, ist schlechter als keiner: er fragt nach Zustimmung zu
 *   etwas, das nirgends beschrieben steht, und das ist genau der Vorwurf, den man damit
 *   vermeiden will. `tests/test_telemetrie.py` haelt die Bedingung fest — sobald der
 *   Hinweis im Layout haengt, MUSS die Seite da sein, sonst wird die Suite rot.
 *
 * ⚠ WAS DER TEXT SAGEN MUSS, damit er nicht irreführt: dass auch bei „Nur Notwendiges"
 *   gemessen wird. Stufe 1 laeuft ohne Einwilligung weiter (cookielos, niemand wird
 *   wiedererkannt). Ein Hinweis, der „Nein" anbietet und dabei verschweigt, dass weiter
 *   gezaehlt wird, waere eine Falschangabe.
 *
 * ⚠ WER WIDERSPROCHEN HAT, WIRD NICHT GEFRAGT. Sendet der Browser „Global Privacy Control"
 *   oder „Do Not Track", erscheint dieser Hinweis gar nicht. Beides ist in der EU nicht
 *   bindend, aber wer ein maschinenlesbares Nein sendet und dann einen Hinweis vorgesetzt
 *   bekommt, ist zu Recht veraergert.
 */

/** Wohin der Hinweis verweist. Die Wache prueft, dass es diese Seite gibt. */
export const DATENSCHUTZ_PFAD = "/datenschutz";

export default function MessHinweis() {
  // ⚠ Erst nach dem ersten Rendern entscheiden. Cookies gibt es auf dem Server nicht; wer
  //   hier direkt rendert, erzeugt einen Hydration-Konflikt (Server zeigt den Hinweis,
  //   Client kennt die Entscheidung schon).
  const [zeigen, setZeigen] = useState(false);

  useEffect(() => {
    if (entscheidung() === null && !widerspruch()) setZeigen(true);
  }, []);

  if (!zeigen) return null;

  const waehle = (wert: "ja" | "nein") => { entscheide(wert); setZeigen(false); };

  return (
    <div role="dialog" aria-label="Hinweis zur Messung" className="messhinweis">
      <p className="messhinweis-text">
        Wir zählen anonym, wie unsere Seiten genutzt werden. Das brauchen wir, um sie zu
        verbessern, und dabei wird niemand wiedererkannt.
        {" "}
        <strong>Mit Ihrer Zustimmung</strong> dürfen wir zusätzlich erkennen, ob Sie
        wiederkommen, und sehen, über welchen Weg Sie zu uns gefunden haben. Dafür setzen wir
        ein Cookie. Sie können das jederzeit widerrufen.
      </p>
      <div className="messhinweis-knoepfe">
        <button type="button" className="messhinweis-ja" onClick={() => waehle("ja")}>
          Einverstanden
        </button>
        <button type="button" className="messhinweis-nein" onClick={() => waehle("nein")}>
          Nur das Nötige
        </button>
        <a className="messhinweis-mehr" href={DATENSCHUTZ_PFAD}>
          Was wir genau messen
        </a>
      </div>
    </div>
  );
}
