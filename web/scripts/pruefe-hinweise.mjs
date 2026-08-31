/* Die Hinweis-Logik — welcher beobachtete Lead löst wann eine Erinnerung aus?
 *
 *     node web/scripts/pruefe-hinweise.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/alerts.ts`. Ihr eigener Docstring sagt seit jeher
 * „reine Funktion, damit sie ohne Cron/Provider testbar ist" — getestet hat sie bis zum
 * 2026-08-31 trotzdem niemand. Ein Baustein, der für Prüfbarkeit gebaut und nie geprüft
 * wurde, ist dieselbe Fehlerklasse wie einer, den niemand aufruft.
 *
 * ⚠ Warum das hier zählt: ein Wecker, der nicht klingelt, meldet sich nicht. Der Nutzer
 * merkt es an dem Tag, an dem er die Frist verpasst hat — und dann ist es zu spät für eine
 * Fehlermeldung.
 */
import { dueAlerts, sentFlagFor, alertText } from "../lib/alerts.ts";

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

const FRISCH = { deadline_14d_sent: false, deadline_3d_sent: false, expiry_warn_sent: false };
const ALLES_AN = { deadline_warning_enabled: true, expiry_warning_enabled: true };
const typen = (lead, w = FRISCH, p = ALLES_AN) => dueAlerts(lead, w, p).map((a) => a.type);

// ── Das Fenster ────────────────────────────────────────────────────────────────
pruefe("14 Tage vorher → 14-Tage-Hinweis",
  typen({ id: "a", src: "f02", tage: 14 }).includes("deadline_14d"));
pruefe("3 Tage vorher → 3-Tage-Hinweis",
  typen({ id: "a", src: "f02", tage: 3 }).includes("deadline_3d"));
// ⚠ Ein Lead kurz vor der Frist darf den 14-Tage-Hinweis NICHT nachziehen — sonst bekommt
//   der Nutzer am Tag davor eine Mail, die „noch 14 Tage" behauptet.
pruefe("1 Tag vorher zieht keinen 14-Tage-Hinweis nach",
  !typen({ id: "a", src: "f02", tage: 1 }).includes("deadline_14d"));
pruefe("15 Tage vorher ist noch zu frueh",
  typen({ id: "a", src: "f02", tage: 15 }).length === 0);
pruefe("abgelaufene Frist loest nichts aus",
  typen({ id: "a", src: "f02", tage: -1 }).length === 0);

// ── ⚠ DER FUND VOM 2026-08-31 ──────────────────────────────────────────────────
// Die Bedingung lautete `lead.src === "f02"` — eine Aufzaehlung, die `f01` still ausliess.
// Gemessen: 18 offene Leads mit `src="f01"`, alle mit veroeffentlichter („echt") Frist,
// mehrere am selben Tag faellig. Die Oberflaeche zeigte ihnen eine Frist, der Hinweislauf
// uebersprang sie.
pruefe("f01 mit echter Frist bekommt einen Hinweis",
  typen({ id: "b", src: "f01", tage: 2 }).includes("deadline_3d"));
// Und eine kuenftige Quelle faellt nicht wieder stumm heraus.
pruefe("eine neue Quelle faellt nicht heraus",
  typen({ id: "c", src: "doe", tage: 10 }).includes("deadline_14d"));

// ── Auslauf ist etwas anderes ──────────────────────────────────────────────────
// `auslauf`-Leads haben keine Angebotsfrist; sie bekommen den Auslauf-Hinweis. Ohne diese
// Grenze wuerde aus „Vertrag endet in 90 Tagen" eine Angebotsfrist, die es nicht gibt.
pruefe("auslauf loest keinen Fristhinweis aus",
  !typen({ id: "d", src: "auslauf", tage: 5 }).some((t) => t.startsWith("deadline")));

// ── Schon verschickt heisst nicht noch einmal ──────────────────────────────────
pruefe("bereits verschickter Hinweis wiederholt sich nicht",
  typen({ id: "a", src: "f02", tage: 2 }, { ...FRISCH, deadline_3d_sent: true }).length === 0);
pruefe("abgeschaltete Erinnerung schweigt",
  typen({ id: "a", src: "f02", tage: 2 }, FRISCH,
        { ...ALLES_AN, deadline_warning_enabled: false }).length === 0);

// ── Die Flags gehoeren zum Typ ─────────────────────────────────────────────────
pruefe("sentFlagFor trifft das richtige Feld",
  sentFlagFor("deadline_3d") === "deadline_3d_sent"
  && sentFlagFor("deadline_14d") === "deadline_14d_sent");

// ── Der Text nennt Tage und Titel ──────────────────────────────────────────────
{
  const t = alertText({ type: "deadline_3d", leadId: "x", titel: "Turnhalle", days: 2 });
  pruefe("der Hinweistext nennt den Titel", String(t.betreff + t.zeile).includes("Turnhalle"));
}

console.log(fehler ? `\n${fehler} Pruefung(en) fehlgeschlagen` : "\nalle Pruefungen bestanden");
process.exit(fehler ? 1 : 0);
