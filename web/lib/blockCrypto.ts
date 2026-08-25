import { createCipheriv, createDecipheriv, randomBytes } from "crypto";

/* Envelope-Verschlüsselung für die Bausteine (Ticket #23 §12.3).
 *
 * **Was hier geschützt wird und was nicht.** Geschützt ist der Inhalt IM DATENBESTAND: wer
 * einen Dump der Tabelle in die Hand bekommt, hält Chiffrat. NICHT geschützt ist er gegen
 * den laufenden Server — der hat den Schlüssel, sonst könnte er die Bausteine nicht
 * ausliefern. Wer das anders will, braucht Verschlüsselung im Browser mit einem Schlüssel,
 * den der Server nie sieht; das ist ein anderes Verfahren mit anderen Folgen (vergessenes
 * Passwort = verlorene Bausteine) und ausdrücklich NICHT das, was §12.3 beschreibt.
 *
 * **Warum ein Schlüssel je Satz (das „Envelope").** Der Inhalt wird mit einem frisch
 * gewürfelten Datenschlüssel verschlüsselt, und nur DIESER wird mit dem Hauptschlüssel
 * eingeschlagen. Das hat zwei Gründe: ein Hauptschlüssel lässt sich austauschen, ohne
 * einen einzigen Baustein neu zu verschlüsseln (nur die Umschläge), und kein Schlüssel
 * sieht mehr Daten als einen Baustein. Direkt mit dem Hauptschlüssel zu verschlüsseln wäre
 * kürzer und nähme beides.
 *
 * Aufbau des Chiffrats:
 *
 *     Byte  0        Version (1)
 *     Byte  1..12    IV des Umschlags
 *     Byte 13..44    Datenschlüssel, mit dem Hauptschlüssel verschlüsselt
 *     Byte 45..60    Auth-Tag des Umschlags
 *     Byte 61..72    IV des Inhalts
 *     Byte 73..88    Auth-Tag des Inhalts
 *     ab   89        Chiffrat des Inhalts
 */

const VERSION = 1;
const ALGO = "aes-256-gcm";

/** Fehlt der Schlüssel, wird NICHT im Klartext gespeichert — es wird gar nicht gespeichert.
 *  Ein stiller Rückfall auf Klartext wäre der schlimmste denkbare Ausgang: die Spalte heisst
 *  `content_encrypted`, und niemand würde nachsehen. */
export class KeinSchluessel extends Error {
  constructor() {
    super("BLOCKS_KEK ist nicht gesetzt — Bausteine werden nicht gespeichert. "
          + "32 zufällige Bytes, base64: `openssl rand -base64 32`.");
    this.name = "KeinSchluessel";
  }
}

function hauptschluessel(): Buffer {
  const roh = process.env.BLOCKS_KEK || "";
  if (!roh) throw new KeinSchluessel();
  const k = Buffer.from(roh, "base64");
  if (k.length !== 32) {
    throw new Error(`BLOCKS_KEK muss 32 Byte sein (base64), ist ${k.length}.`);
  }
  return k;
}

export function verschluessele(klartext: string): Buffer {
  const kek = hauptschluessel();
  const dek = randomBytes(32);

  const umschlagIv = randomBytes(12);
  const u = createCipheriv(ALGO, kek, umschlagIv);
  const dekChiffre = Buffer.concat([u.update(dek), u.final()]);
  const umschlagTag = u.getAuthTag();

  const iv = randomBytes(12);
  const c = createCipheriv(ALGO, dek, iv);
  const inhalt = Buffer.concat([c.update(klartext, "utf8"), c.final()]);
  const tag = c.getAuthTag();

  return Buffer.concat([Buffer.from([VERSION]), umschlagIv, dekChiffre, umschlagTag,
                        iv, tag, inhalt]);
}

export function entschluessele(daten: Buffer): string {
  if (daten.length < 89) throw new Error("Chiffrat zu kurz.");
  if (daten[0] !== VERSION) throw new Error(`Unbekannte Fassung ${daten[0]}.`);
  const kek = hauptschluessel();

  const u = createDecipheriv(ALGO, kek, daten.subarray(1, 13));
  u.setAuthTag(daten.subarray(45, 61));
  const dek = Buffer.concat([u.update(daten.subarray(13, 45)), u.final()]);

  const c = createDecipheriv(ALGO, dek, daten.subarray(61, 73));
  c.setAuthTag(daten.subarray(73, 89));
  return Buffer.concat([c.update(daten.subarray(89)), c.final()]).toString("utf8");
}
