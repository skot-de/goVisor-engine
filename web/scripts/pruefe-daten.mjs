// Bremse vor dem Build: hat diese Umgebung ueberhaupt Daten?
//
// WARUM ES SIE GIBT. Seit dem 2026-08-18 liegt `web/data` nicht mehr in Git (294-MB-Datei,
// GitHub weist ueber 100 MB ab). Lokal ist das folgenlos, die Platte ist die Quelle. Auf
// einem Bauserver aber gibt es weder das Verzeichnis noch — solange niemand sie setzt — die
// Variable `DATA_BASE_URL`. Der Build liefe durch, das Deployment kaeme hoch, und die
// Anwendung waere leer. Die Outreach-Landings unter `/t/...` sind oeffentlich; dort faellt es
// als Erstes auf, und zwar dem Kunden.
//
// Lieber ein Build, der mit einer klaren Ansage abbricht, als ein Deployment, das aussieht,
// als sei alles in Ordnung. Genau diese Sorte Fehler — vorhanden, aber leer — hat in diesem
// Projekt schon einmal Monate ueberdauert (14 statt 4.499 Volltexte im Frontend).
import { existsSync } from "node:fs";

const basis = process.env.DATA_BASE_URL?.trim();
// Eine Datei, die JEDER Bestand hat und ohne die die Lead-Liste nichts zeigt.
const lokal = existsSync(new URL("../data/leads-bau.json", import.meta.url));

if (basis) {
  console.log(`  Daten: DATA_BASE_URL gesetzt (${basis.replace(/\/+$/, "")})`);
} else if (lokal) {
  console.log("  Daten: lokales web/data (kein DATA_BASE_URL — richtig fuer Entwicklung)");
} else {
  console.error(`
  ✖ ABBRUCH: Diese Umgebung hat keine Daten.

    web/data/ ist leer oder fehlt, und DATA_BASE_URL ist nicht gesetzt. Ein Build waere
    erfolgreich und die Anwendung trotzdem leer — Lead-Listen, Detailseiten und die
    oeffentlichen Outreach-Landings unter /t/... zeigen dann nichts.

    Zwei Wege:
      1. Objektspeicher befuellen und DATA_BASE_URL setzen  (s. docs/web-data-storage.md)
      2. lokal die Exporte laufen lassen                    (scripts/daily_leads.sh)
`);
  process.exit(1);
}
