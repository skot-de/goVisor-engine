import "server-only";
import { NextResponse } from "next/server";
import { brotliCompressSync, gzipSync, constants as zc } from "node:zlib";
import { ausSpeicher, inSpeicher } from "@/lib/dataSource";

/* Grosse Antworten komprimiert ausliefern — weil Next es fuer Route-Handler nicht tut.
 *
 * ⚠ GEMESSEN AM 2026-09-18, nicht angenommen. `next start` gzippt statische Dateien
 * (`/_next/static/...` kommt mit `Content-Encoding: gzip`), aber KEINE einzige
 * API-Antwort:
 *
 *     /api/leads?branche=bau      46.044.875 Bytes   Content-Encoding: KEINE
 *     /api/plz-geo                 1.463.245 Bytes   Content-Encoding: KEINE
 *     /_next/static/chunks/*.js        1.905 Bytes   Content-Encoding: gzip
 *
 * Die 43,9 MB der groessten Branchendatei gehen also ROH ueber die Leitung. Bei 30 Mbit/s
 * sind das 12,3 Sekunden — genau die Zeit, die ein Nutzer nach der Anmeldung gemeldet hat
 * („warum dauert das denn 12 sekunden?"). Ein Kommentar in `/api/leads` nannte „5,6 MB
 * gzip"; das war die Groesse, die eine Komprimierung ERGEBEN WUERDE, nicht die, die
 * ankommt. Ich habe sie am 2026-09-17 als Messwert weitergereicht, ohne sie zu messen.
 *
 * Gemessen an der echten Antwort (43,9 MB):
 *
 *     gzip level 6    5,56 MB   260 ms   -87 %
 *     brotli q=1      5,55 MB    66 ms   -87 %
 *     brotli q=4      3,76 MB   111 ms   -91 %   ← gewaehlt
 *     brotli q=5      3,51 MB   219 ms   -92 %
 *
 * q=4 ist der Knick: doppelt so schnell wie q=5 bei 7 % mehr Groesse, und gegenueber gzip
 * ein Drittel kleiner bei weniger als der halben Rechenzeit.
 */

/** Was der Client annimmt — in der Reihenfolge, in der wir es anbieten. */
function verfahren(req: Request): "br" | "gzip" | null {
  const a = (req.headers.get("accept-encoding") || "").toLowerCase();
  // ⚠ Auf Wortgrenzen pruefen. „brotli" enthaelt „br", und ein `includes("br")` haette
  // auch bei `Accept-Encoding: brotli-unbekannt` zugeschlagen.
  const kann = (w: string) => new RegExp(`(^|[,\\s])${w}\\s*(;|,|$)`).test(a);
  if (kann("br")) return "br";
  if (kann("gzip")) return "gzip";
  return null;
}

function presse(roh: Buffer, wie: "br" | "gzip"): Buffer {
  if (wie === "gzip") return gzipSync(roh, { level: 6 });
  return brotliCompressSync(roh, {
    params: {
      [zc.BROTLI_PARAM_QUALITY]: 4,
      // Der Groessenhinweis spart dem Kodierer eine Runde — kostenlos, weil wir die
      // Laenge ohnehin kennen.
      [zc.BROTLI_PARAM_SIZE_HINT]: roh.length,
    },
  });
}

/**
 * Antwort mit ausgehandelter Komprimierung.
 *
 * ⚠ `marke` IST DER ZWISCHENSPEICHER-SCHLUESSEL UND MUSS DIE DATEN EINDEUTIG BENENNEN.
 * Hier gehoert der ETag hinein, nicht der Routenname: sonst bekommt der naechste Nutzer
 * die Daten von gestern, und zwar ohne dass irgendetwas bricht. Ist keine Marke bekannt,
 * wird NICHT zwischengespeichert — lieber jedes Mal rechnen als einmal falsch ausliefern.
 *
 * ⚠ DAS VERFAHREN GEHOERT IN DEN SCHLUESSEL. Ein Brotli-Rumpf an einen Client, der nur
 * gzip kann, ist unlesbarer Datenmuell — und der Client meldet keinen Fehler, er zeigt
 * eine kaputte Seite.
 *
 * ⚠ `Vary: Accept-Encoding` ist Pflicht. Ohne diesen Kopf liefert jeder
 * Zwischenspeicher auf dem Weg dieselbe Kodierung an alle weiter.
 */
export function komprimiert(
  req: Request, rumpf: string, kopf: Record<string, string>, marke?: string | null,
): NextResponse {
  const wie = verfahren(req);
  const alle = { ...kopf, vary: "Accept-Encoding" };
  if (!wie) return new NextResponse(rumpf, { headers: alle });

  const schluessel = marke ? `gz:${marke}:${wie}` : null;
  let daten = schluessel ? ausSpeicher<Buffer>(schluessel) : undefined;
  if (!daten) {
    daten = presse(Buffer.from(rumpf, "utf8"), wie);
    if (schluessel) inSpeicher(schluessel, daten, daten.length);
  }
  // `Content-Length` ausdruecklich: sonst faellt die Antwort auf `chunked` zurueck und der
  // Browser kann keinen Fortschritt anzeigen — bei mehreren MB ist das der Unterschied
  // zwischen „laedt" und „haengt".
  return new NextResponse(daten as unknown as BodyInit, {
    headers: { ...alle, "content-encoding": wie, "content-length": String(daten.length) },
  });
}
