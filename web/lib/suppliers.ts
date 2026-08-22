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

/* ⚠ KEIN EWIGER SPEICHER MEHR. Vorher hielt eine Modulvariable die geparste Datei bis zum
   Neustart der Instanz fest. Lokal harmlos, im Betrieb aber falsch: die Exporte laufen
   nachts, und eine laufende Instanz hätte bis zum nächsten Deployment die Zahlen von gestern
   ausgeliefert — ohne dass es jemand sieht, denn alte Daten sehen aus wie frische.
   Jetzt unter demselben Regime wie die Rohdateien (Verfallszeit + Byte-Budget). Gespeichert
   wird das GEPARSTE Ergebnis: das Parsen von 39 MB JSON ist teurer als der Abruf. */
export async function loadSuppliers(): Promise<Supplier[]> {
  const fertig = ausSpeicher<Supplier[]>("suppliers:geparst");
  if (fertig) return fertig;
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
    for (const s of await loadSuppliers()) {
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
