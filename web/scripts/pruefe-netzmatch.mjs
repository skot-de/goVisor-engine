/* Die Regeln der Partnersuche durchspielen. Läuft mit blossem `node`, ohne Bundler:
 *     node web/scripts/pruefe-netzmatch.mjs
 * Aufgerufen wird das ausserdem von tests/test_healyhudson.py, damit die Regeln unter einem
 * laufenden Test stehen und nicht nur unter einer Zusicherung auf den Quelltext.
 *
 * Warum diese Regeln zählen: eine Partnersuche, die Wettbewerber vorschlägt, ist schlimmer
 * als keine. Wer dieselben Lose abdeckt wie ich, bietet gegen mich. */
import { besterPartner } from "../lib/netzMatch.js";

const z = (u, id, lose, seit = "2026-08-01") =>
  ({ user_id: u, identity_id: id, lose, freigabe: false, created_at: seit });
const ich = z("ich", "grp:a", [1, 2]);

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

pruefe("Wettbewerber auf denselben Losen ist kein Partner",
  besterPartner(ich, [ich, z("b", "grp:b", [1, 2])]) === null);
pruefe("Ergänzung auf anderen Losen ist ein Partner",
  besterPartner(ich, [ich, z("b", "grp:b", [3, 4])]) !== null);
pruefe("Dieselbe Firmengruppe ist kein Partner",
  besterPartner(ich, [ich, z("b2", "grp:a", [3, 4])]) === null);
pruefe("Man selbst ist nie sein Partner", besterPartner(ich, [ich]) === null);
pruefe("Ohne Identität wird niemand ausgeschlossen",
  besterPartner(z("ich", null, [1]), [z("b", null, [2])]) !== null);
pruefe("Nur die freien Lose zählen als Deckung",
  besterPartner(ich, [z("b", "grp:b", [2, 3])])?.ergaenzt.join() === "3");
pruefe("Die grösste Ergänzung gewinnt",
  besterPartner(ich, [z("b", "grp:b", [3]), z("c", "grp:c", [3, 4, 5])])?.zeile.user_id === "c");
pruefe("Bei Gleichstand zählt die ältere Meldung",
  besterPartner(ich, [z("spaet", "grp:b", [3], "2026-08-10"),
                      z("frueh", "grp:c", [4], "2026-08-02")])?.zeile.user_id === "frueh");
pruefe("Ohne Lose auf der Gegenseite kein Treffer",
  besterPartner(ich, [z("b", "grp:b", [])]) === null);

console.log(fehler ? `\n${fehler} Regel(n) verletzt.` : "\nAlle Regeln halten.");
process.exit(fehler ? 1 : 0);
