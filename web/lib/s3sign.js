/* AWS Signature Version 4 für einen einzelnen GET — das Gegenstück zu `kopf_bauen` in
 * `scripts/upload_web_data.py`. Beide Seiten sprechen damit denselben Speicher: das Skript
 * lädt hoch, diese Datei liest.
 *
 * WARUM ES DAS BRAUCHT. `DATA_BASE_URL` allein verlangt einen ÖFFENTLICH lesbaren Speicher —
 * `loadDataFile` machte ein blankes `fetch`. Unter dieser Basis liegt aber `suppliers.json`
 * mit den Kontaktdomains von 16.454 Firmen, ausdrücklich als „NUR SERVERSEITIG" markiert
 * (lib/suppliers.ts), dazu 6.563 Dokumentvolltexte und 253 MB LLM-Auswertungen. Ein offener
 * Bucket hätte die Ratenbremse auf `/api/entity-search` mit einem einzigen GET umgangen.
 *
 * WARUM VON HAND UND NICHT MIT DEM AWS-SDK. Dieselbe Begründung wie im Upload-Skript: das SDK
 * zieht viel mit für eine Aufgabe, die vierzig Zeilen sind. Und ein Fehler in der Signatur
 * sieht nicht wie ein Fehler aus, sondern wie „HTTP 403", also wie falsche Zugangsdaten —
 * man sucht dann an der falschen Stelle. Deshalb steht sie an einer nachlesbaren Stelle und
 * unter einem Test gegen den dokumentierten AWS-Vektor.
 *
 * WebCrypto statt `node:crypto`, damit es auch in der Edge-Laufzeit trägt.
 *
 * ⚠ KEIN `server-only` und KEIN Zugriff auf `process.env` hier: beides machte die Datei für
 * blosses `node` unladbar, und der Test wäre wieder eine Abschrift statt der echten Funktion.
 * Diese Datei rechnet nur. Wer die Zugangsdaten liest, ist `dataSource.ts` — und die trägt
 * `server-only`, damit ein Import aus einer Client-Komponente den Build bricht statt still
 * `undefined` einzusetzen.
 *
 * ⚠ BEWUSST PLAIN JS, wie `lib/netzMatch.js`: so prüft `scripts/pruefe-s3signatur.mjs` die
 * ECHTE Ableitung mit blossem `node`, nicht eine Abschrift davon. Ein Test, der eine Kopie
 * prüft, geht grün, während die benutzte Fassung falsch ist.
 */

const LEER_HASH = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";

async function hmac(schluessel, msg) {
  const k = await crypto.subtle.importKey(
    "raw", schluessel, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return crypto.subtle.sign("HMAC", k, new TextEncoder().encode(msg));
}

function hex(b) {
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

async function sha256(text) {
  return hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
}

/** Der Signaturschlüssel (Datum → Region → Dienst → aws4_request). Getrennt, weil genau
 *  diese Kette der AWS-Testvektor prüft. */
export async function signaturSchluessel(secret, tag, region, dienst = "s3") {
  let k = new TextEncoder().encode(`AWS4${secret}`);
  for (const teil of [tag, region, dienst, "aws4_request"]) k = await hmac(k, teil);
  return k;
}

/**
 * @typedef {{endpunkt: string, bucket: string, keyId: string, secret: string,
 *            region: string}} S3Zugang
 */

/** URL und Kopfzeilen für einen signierten GET auf `pfad`.
 * @param {S3Zugang} z @param {string} pfad
 * @returns {Promise<{url: string, kopf: Record<string,string>}>} */
export async function signierterGet(z, pfad) {
  const host = z.endpunkt.split("://")[1].replace(/\/+$/, "");
  const kanonUri = `/${z.bucket}/${pfad.replace(/^\/+/, "")}`;
  const url = `${z.endpunkt.replace(/\/+$/, "")}${kanonUri}`;

  const jetzt = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
  const stempel = jetzt.endsWith("Z") ? jetzt : `${jetzt}Z`;
  const tag = stempel.slice(0, 8);

  /** @type {Record<string,string>} */
  const kopf = {
    host, "x-amz-content-sha256": LEER_HASH, "x-amz-date": stempel,
  };
  const namen = Object.keys(kopf).sort();
  const signierte = namen.join(";");
  const kanonKopf = namen.map((k) => `${k}:${kopf[k]}\n`).join("");
  const kanon = `GET\n${kanonUri}\n\n${kanonKopf}\n${signierte}\n${LEER_HASH}`;

  const bereich = `${tag}/${z.region}/s3/aws4_request`;
  const zuSignieren = `AWS4-HMAC-SHA256\n${stempel}\n${bereich}\n${await sha256(kanon)}`;
  const signatur = hex(await hmac(await signaturSchluessel(z.secret, tag, z.region), zuSignieren));

  kopf["Authorization"] = `AWS4-HMAC-SHA256 Credential=${z.keyId}/${bereich}, `
    + `SignedHeaders=${signierte}, Signature=${signatur}`;
  return { url, kopf };
}
