"use client";
import { Dokumentbau } from "@/components/explorer/Dokumentbau";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../explorer.css";

/* Dokumente aus Bausteinen (Phase 1, Plan: `docs/funktion-dokument-bauen.md`).
 *
 * ⚠ EIGENE SEITE, ABER KEIN EIGENER EINTRAG IN DER HAUPTNAVIGATION. Ein Eintrag braechte
 * Aenderungen an `Rail.tsx` UND an `web/lib/i18n/messages/flat.*.json` mit sich, und diese
 * Dateien werden gerade von drei Zweigen gleichzeitig bearbeitet (`scripts/wer_macht_was.sh`).
 * Fremdes Gebiet fuer eine Funktion, die sich erst beweisen muss. Die Leiste steht deshalb auf
 * `bausteine` — dort kommt man her, und dort gehoert die Funktion hin.
 *
 * Sobald die Funktion bleibt, gehoert sie in die Navigation; das ist ein eigener, angesagter
 * Schritt.
 */
export default function DokumentePage() {
  return (
    <div className="app">
      <AppTop />
      <div className="body">
        <AppRail current="bausteine" />
        <div className="main seitenmain">
          <Dokumentbau />
        </div>
      </div>
    </div>
  );
}
