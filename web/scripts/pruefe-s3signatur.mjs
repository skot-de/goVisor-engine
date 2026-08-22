/* Die SigV4-Ableitung des Frontends gegen den dokumentierten AWS-Testvektor.
 *
 *     node web/scripts/pruefe-s3signatur.mjs
 *
 * Geprüft wird die ECHTE Funktion aus `lib/s3sign.js`, keine Abschrift — ein Test, der eine
 * Kopie prüft, geht grün, während die benutzte Fassung falsch ist. Deshalb liegt der Signierer
 * in Plain JS.
 *
 * Warum überhaupt ein Test: die Signatur ist von Hand gebaut. Ein Fehler darin sieht nicht wie
 * ein Fehler aus, sondern wie „HTTP 403" — also wie falsche Zugangsdaten, und man sucht
 * stundenlang an der falschen Stelle. Der Vektor stammt aus der AWS-Dokumentation und ist eine
 * feste Grösse; `tests/test_plumbing.py` prüft die Python-Seite gegen exakt denselben Wert.
 * Beide Seiten müssen übereinstimmen: das Skript lädt hoch, das Frontend liest.
 */
import { signaturSchluessel, signierterGet } from "../lib/s3sign.js";

const ERWARTET = "f4780e2d9f65fa895f9c67b32ce1baf0b0d8a43505a000a1a9e090d414db404d";
const hex = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");

let fehler = 0;
const pruefe = (name, bedingung) => {
  if (!bedingung) fehler++;
  console.log(`${bedingung ? "ok  " : "FEHL"}  ${name}`);
};

const k = await signaturSchluessel("wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
                                   "20120215", "us-east-1", "iam");
pruefe("Signaturschlüssel stimmt mit dem AWS-Vektor", hex(k) === ERWARTET);

const falsch = await signaturSchluessel("wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",
                                        "20120215", "iam", "us-east-1");
pruefe("vertauschte Kette ergibt einen anderen Schlüssel (der Test greift also)",
       hex(falsch) !== ERWARTET);

const z = { endpunkt: "https://konto.r2.cloudflarestorage.com", bucket: "govisor-data",
            keyId: "AKID", secret: "GEHEIM", region: "auto" };
const { url, kopf } = await signierterGet(z, "leads-bau.json");
pruefe("URL enthält Bucket und Pfad",
       url === "https://konto.r2.cloudflarestorage.com/govisor-data/leads-bau.json");
pruefe("Authorization nennt Schlüssel, Bereich und signierte Kopfzeilen",
       /^AWS4-HMAC-SHA256 Credential=AKID\/\d{8}\/auto\/s3\/aws4_request, /.test(kopf.Authorization)
       && kopf.Authorization.includes("SignedHeaders=host;x-amz-content-sha256;x-amz-date"));
pruefe("Zeitstempel hat das AWS-Format (20260822T101500Z)",
       /^\d{8}T\d{6}Z$/.test(kopf["x-amz-date"]));
const zweite = await signierterGet(z, "leads-it.json");
pruefe("andere Datei ergibt eine andere Signatur",
       zweite.kopf.Authorization !== kopf.Authorization);

console.log(fehler ? `\n${fehler} Prüfung(en) fehlgeschlagen.` : "\nSignatur stimmt.");
process.exit(fehler ? 1 : 0);
