import { createHash } from "crypto";
import { loadDataFile, ausSpeicher, inSpeicher } from "@/lib/dataSource";

/* Serverseitiger Lieferanten-Index (Onboarding-Matching). Einmal geladen, gecacht. */

export type Member = { name: string; conf: "belegt" | "unsicher"; method: string; wins: number };
export type Supplier = {
  id: string; name: string; aliases: string[]; wins: number;
  buyers: number | null; seit: number | null;
  fields: { cpv4: string; label: string | null; wins: number }[];
  fields6?: { cpv6: string; wins: number }[];   // CPV-6-Volltreffer-Menge (nur Codes, fürs Matching)
  regions: string[]; regionTyp?: 'regional'|'teilregional'|'bundesweit';
  volMedian: number | null;
  topBuyers?: { name: string; wins: number; seit: number; bis: number }[];
  topShare?: number | null;   // Anteil des größten Auftraggebers (Klumpenrisiko)
  // NUR SERVERSEITIG — nie ins Suchergebnis, sonst sind die Kontaktdomains aller
  // Firmen über die Suche abgreifbar. Auswertung ausschließlich in /api/entity-verify.
  domain?: string | null; domainBelege?: number;
  // Woher die Domain stammt. "kontakt" = aus Mailadressen der Vergabeunterlagen
  // abgeleitet (gemessen 7,5 % Auftraggeber-Adressen darin), "impressum" = gegen die
  // Anbieterkennung der Domain selbst geprüft (0,0 % Fehlbestätigungen an 200
  // verwürfelten Paaren). Die Verifikationsleiter gewichtet danach.
  domainQuelle?: "impressum" | "kontakt" | null; domainGeprueft?: string | null;
  // sha256(Adresse), auf 16 Hex-Zeichen gekürzt — Klartext liegt nirgends.
  mailHashes?: string[];
  members: Member[];
};

/* ── AUFGETEILT ────────────────────────────────────────────────────────────────────────
 *
 * ⚠ Bis zum 2026-08-25 lud jede dieser Routen die komplette `suppliers.json`: 46 MB,
 * 37.901 Firmen. Wofür — gemessen:
 *
 *   entity-group, entity-verify, impressum   `.find(x => x.id === id)`  → EINE Firma
 *   intern/claims                            bis zu 200 Nachschläge     → wenige Firmen
 *   entity-search                            sucht über Name/Aliasse, reichert die
 *                                            SECHS besten Treffer an
 *   domainEigentuemer                        alle Firmen, aber nur vier leichte Felder
 *
 * Fünf Felder tragen 91 % der Bytes (`fields` 25 %, `members` 20 %, `topBuyers` 17 %,
 * `fields6` 16 %, `mailHashes` 14 %) — und KEINE Route braucht mehr als eines davon.
 * Deshalb zweierlei: eine schlanke Basis für Suche und Domain-Index, eine Datei je Firma
 * für alles Übrige. */

/** Was Suche und Domain-Index brauchen — und sonst nichts. */
export type SupplierBasis = Pick<Supplier, "id" | "name" | "aliases" | "wins">
  & { domain?: string | null; domainBelege?: number };

/** Firmen-ID → Dateiname. MUSS mit `export_suppliers.suppliers_dateiname` übereinstimmen.
 *  Hash, weil die sonst übliche Säuberung `[^A-Za-z0-9_-]` → "" bei diesen Kennungen
 *  kollidiert (bei den Firmenprofilen gemessen: drei Paare unter 38.307). */
export function supplierDateiname(id: string): string {
  return createHash("sha1").update(id, "utf8").digest("hex");
}

/** Eine Firma, vollständig. `null`, wenn es sie nicht gibt. */
export async function loadSupplier(id: string): Promise<Supplier | null> {
  if (!id) return null;
  const schluessel = `supplier:${id}`;
  const fertig = ausSpeicher<Supplier | null>(schluessel);
  if (fertig !== undefined) return fertig;
  try {
    const roh = await loadDataFile(`suppliers/${supplierDateiname(id)}.json`);
    if (roh) return inSpeicher(schluessel, JSON.parse(roh) as Supplier, roh.length);
  } catch {
    /* faellt unten auf die Sammeldatei zurueck */
  }
  return (await loadSuppliers()).find((x) => x.id === id) ?? null;
}

/** Alle Firmen, aber nur die leichten Felder. */
export async function loadSuppliersBasis(): Promise<SupplierBasis[]> {
  const fertig = ausSpeicher<SupplierBasis[]>("suppliers:basis");
  if (fertig) return fertig;
  try {
    const raw = await loadDataFile("suppliers-basis.json");
    if (raw) return inSpeicher("suppliers:basis", JSON.parse(raw) as SupplierBasis[], raw.length);
  } catch {
    /* s. u. */
  }
  return loadSuppliers();
}

/* ⚠ ÜBERGANG, kein Dauerzustand. Solange die aufgeteilten Dateien nicht im Datenspeicher
   liegen, müssen die Routen trotzdem antworten — das kostet dann aber wieder die vollen
   46 MB. Deshalb LAUT: eine Zeile im Protokoll ist der Unterschied zwischen „Übergang
   läuft" und „wir haben nichts gewonnen und niemand hat es gemerkt".

   ⚠ KEIN EWIGER SPEICHER. Vorher hielt eine Modulvariable die geparste Datei bis zum
   Neustart der Instanz fest. Lokal harmlos, im Betrieb falsch: die Exporte laufen nachts,
   und eine laufende Instanz hätte bis zum nächsten Deployment die Zahlen von gestern
   ausgeliefert — alte Daten sehen aus wie frische. */
let gewarnt = false;
export async function loadSuppliers(): Promise<Supplier[]> {
  const fertig = ausSpeicher<Supplier[]>("suppliers:geparst");
  if (fertig) return fertig;
  if (!gewarnt) {
    console.error("[suppliers] Rückfall auf suppliers.json (46 MB) — `suppliers/` bzw. "
                  + "suppliers-basis.json fehlen. export_suppliers.py laufen lassen und hochladen.");
    gewarnt = true;
  }
  try {
    const raw = (await loadDataFile("suppliers.json")) ?? "";
    return inSpeicher("suppliers:geparst", JSON.parse(raw) as Supplier[], raw.length);
  } catch {
    return [];
  }
}

/* ── Rückwärts-Index: Domain → Firma ─────────────────────────────────────────────────
 *
 * **Wofür.** Die Belegprüfung erkannte bisher „die Domain passt nicht zur hinterlegten",
 * konnte aber nicht sagen, WEM sie gehört. Der Unterschied ist erheblich: wer mit
 * `@bechtle.de` das Klostermann-Profil öffnet, ist kein Grenzfall, sondern eine falsche
 * Zuordnung, die man nicht stillschweigend durchwinken darf.
 *
 * **Warum Mehrdeutigkeit hier zählt.** Gemessen 2026-08-17: von 7.631 Domains mit
 * mindestens zwei Belegen gehören 458 (6,0 %) mehreren Identitäten — und die Beispiele
 * zeigen, dass das fast immer Konzern-Fragmentierung ist (LEONHARD WEISS zweimal,
 * MAN zweimal, Siemens zweimal), nicht zwei verschiedene Unternehmen. Eine Domain mit
 * mehreren Eigentümern taugt deshalb NICHT als Vorwurf. Sie fällt aus dem Index.
 *
 * Übrig bleiben die eindeutigen 94 %, und nur die können eine fremde Firma belegen.
 */
const MIN_BELEGE_INDEX = 2;

let DOMAIN_INDEX: Map<string, { id: string; name: string }> | null = null;

export async function domainEigentuemer(domain: string) {
  if (!DOMAIN_INDEX) {
    const zaehler = new Map<string, { id: string; name: string } | null>();
    for (const s of await loadSuppliersBasis()) {
      const d = (s.domain || "").toLowerCase();
      if (!d || (s.domainBelege ?? 0) < MIN_BELEGE_INDEX) continue;
      if (!zaehler.has(d)) zaehler.set(d, { id: s.id, name: s.name });
      // Zweite Identität auf derselben Domain → mehrdeutig, `null` sperrt sie dauerhaft.
      else if (zaehler.get(d)?.id !== s.id) zaehler.set(d, null);
    }
    DOMAIN_INDEX = new Map(
      [...zaehler].filter(([, v]) => v !== null) as [string, { id: string; name: string }][]);
  }
  return DOMAIN_INDEX.get((domain || "").toLowerCase()) ?? null;
}
