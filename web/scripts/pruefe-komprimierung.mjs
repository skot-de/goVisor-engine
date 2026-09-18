// Kommen grosse Antworten komprimiert an — und entpacken sie sich zum Original?
//
// WARUM ES DIESE PRUEFUNG GIBT. `next start` gzippt statische Dateien, aber KEINE
// API-Antwort. Gemessen am 2026-09-18 mit angemeldeter Sitzung:
//
//     /api/leads?branche=bau      46.044.875 Bytes   Content-Encoding: KEINE
//     /api/plz-geo                 1.463.245 Bytes   Content-Encoding: KEINE
//     /_next/static/chunks/*.js        1.905 Bytes   Content-Encoding: gzip
//
// 43,9 MB roh sind bei 30 Mbit/s 12,3 Sekunden — genau die Zeit, die ein Nutzer nach der
// Anmeldung gemeldet hat. Ein Kommentar in der Route nannte „5,6 MB gzip"; das war die
// Groesse, die eine Komprimierung ERGEBEN WUERDE, nicht die, die ankommt.
//
// ⚠ DIE GEFAEHRLICHE SEITE. Setzt jemand `Content-Encoding` und der Rumpf ist NICHT so
// kodiert (oder wird zusaetzlich komprimiert), zeigt der Browser keine Fehlermeldung — er
// zeigt eine kaputte Seite. Deshalb prueft diese Sonde nicht die Kopfzeile, sondern
// ENTPACKT und vergleicht Byte fuer Byte gegen die unkomprimierte Fassung.
//
// Aufruf (Server muss laufen, Sitzung siehe scripts/pruefkonto.py):
//     node web/scripts/pruefe-komprimierung.mjs "<cookie-zeile>"
import http from "node:http";
import { gunzipSync, brotliDecompressSync } from "node:zlib";

const cookie = process.argv[2] || process.env.PRUEF_COOKIE || "";
const basis = process.env.PRUEF_BASIS || "http://127.0.0.1:3000";
if (!cookie) {
  console.log("  … keine Sitzung uebergeben — uebersprungen. (scripts/pruefkonto.py)");
  process.exit(0);
}

const ROUTEN = ["/api/leads?branche=sicherheit", "/api/plz-geo", "/api/doc-analysis"];
let fehler = 0;
const klage = (m) => { console.error("  ✗ " + m); fehler++; };

/* ⚠ NICHT `fetch`. Node entpackt Antworten mit `Content-Encoding` selbsttaetig — die
 * erste Fassung dieser Sonde bekam also bereits ausgepackte Bytes, versuchte sie erneut
 * zu entpacken und meldete sechsmal „vermutlich doppelt kodiert". Der Fehler lag in der
 * Pruefung, nicht im Produkt; ein Vergleich mit `curl --compressed` war zur selben Zeit
 * Byte fuer Byte gruen. `node:http` reicht den Rumpf roh durch, und genau den wollen wir. */
function hole(pfad, enc) {
  return new Promise((fertig, schiefgegangen) => {
    const u = new URL(basis + pfad);
    const anfrage = http.request(
      { hostname: u.hostname, port: u.port, path: u.pathname + u.search, method: "GET",
        headers: { cookie, "accept-encoding": enc } },
      (a) => {
        const stuecke = [];
        a.on("data", (d) => stuecke.push(d));
        a.on("end", () => fertig({
          status: a.statusCode, enc: a.headers["content-encoding"] || null,
          vary: a.headers.vary || "", rumpf: Buffer.concat(stuecke),
        }));
      });
    anfrage.on("error", schiefgegangen);
    anfrage.end();
  });
}

for (const pfad of ROUTEN) {
  const klar = await hole(pfad, "identity");
  if (klar.status !== 200) { klage(`${pfad}: HTTP ${klar.status} ohne Komprimierung.`); continue; }
  if (klar.enc) klage(`${pfad}: liefert auch bei \`identity\` \`${klar.enc}\` — das verletzt die Aushandlung.`);

  for (const [angebot, erwartet, aus] of [["br", "br", brotliDecompressSync],
                                          ["gzip", "gzip", gunzipSync]]) {
    const a = await hole(pfad, angebot);
    if (a.enc !== erwartet) {
      klage(`${pfad}: bei \`Accept-Encoding: ${angebot}\` kommt \`${a.enc || "nichts"}\` `
          + `statt \`${erwartet}\`. Die Antwort geht roh ueber die Leitung.`);
      continue;
    }
    // ⚠ DAS IST DIE EIGENTLICHE PRUEFUNG. Eine falsche Kopfzeile faellt auf; ein Rumpf,
    // der sich nicht entpacken laesst, zeigt sich erst im Browser als kaputte Seite.
    let entpackt;
    try { entpackt = aus(a.rumpf); }
    catch (e) { klage(`${pfad} (${angebot}): Rumpf laesst sich nicht entpacken — ${e.message}. `
                    + "Vermutlich doppelt kodiert."); continue; }
    if (!entpackt.equals(klar.rumpf)) {
      klage(`${pfad} (${angebot}): entpackt ${entpackt.length} Bytes, unkomprimiert sind es `
          + `${klar.rumpf.length}. Die Antworten sind NICHT identisch.`);
      continue;
    }
    // Ohne `Vary` liefert jeder Zwischenspeicher dieselbe Kodierung an alle weiter.
    if (!/accept-encoding/i.test(a.vary)) {
      klage(`${pfad} (${angebot}): \`Vary: Accept-Encoding\` fehlt.`);
    }
    const spar = (100 - 100 * a.rumpf.length / klar.rumpf.length).toFixed(0);
    console.log(`  ${pfad.padEnd(32)} ${angebot.padEnd(5)} `
              + `${(klar.rumpf.length / 1048576).toFixed(2)} → ${(a.rumpf.length / 1048576).toFixed(2)} MB  (-${spar} %)`);
  }
}

console.log(fehler ? `\n✗ ${fehler} Befund(e)`
                   : "\n✓ Komprimiert ausgeliefert und Byte fuer Byte wiederherstellbar");
process.exit(fehler ? 1 : 0);
