import { createAdminClient } from "./admin";
import type { Befund, Urteil } from "@/lib/impressum";

/* Impressum-Nachweise lesen und schreiben.
 *
 * ⚠ NUR SERVERSEITIG. `domain_proof` hat bewusst KEINE RLS-Policy: die Tabelle ordnet
 * Domains zu Firmen zu, und wäre sie für `authenticated` lesbar, könnte jeder angemeldete
 * Nutzer die Kontaktdomains unseres gesamten Firmenbestands abgreifen. Zugriff läuft
 * ausschliesslich über den Secret-Key, der RLS umgeht — dieselbe Regel wie bei
 * `suppliers.domain` (siehe lib/suppliers.ts). Dieses Modul darf nie aus einer
 * Client-Komponente importiert werden.
 */

export type Nachweis = {
  urteil: Urteil; quote: number | null; pfad: string | null;
  ortBelegt: boolean; registerBelegt: boolean; geprueftAm: string; quelle: string;
};

/* Wie lange ein Nachweis gilt.
 *
 * Unterschiedlich je Urteil, und das ist der Punkt: ein BELEGT altert langsam (eine Firma
 * gibt ihre Domain selten auf, und das Impressum ändert sich noch seltener). Ein
 * NICHT_PRUEFBAR altert schnell, denn es sagt nur „gerade nicht erreichbar" — ein
 * abgelaufenes Zertifikat oder ein toter Server ist morgen vielleicht repariert, und wir
 * würden einen echten Kunden ohne Not auf dem kalten Weg lassen.
 *
 * WIDERLEGT liegt dazwischen: lange genug, um den Abruf zu sparen, kurz genug, damit eine
 * Firma nach einem Relaunch nicht ein Jahr lang an unserem Urteil hängt. */
const FRIST_TAGE: Record<Urteil, number> = {
  belegt: 90,
  widerlegt: 30,
  nicht_pruefbar: 1,
};

export async function leseNachweis(domain: string, identityId: string): Promise<Nachweis | null> {
  try {
    const { data } = await createAdminClient()
      .from("domain_proof")
      .select("urteil, quote, pfad, ort_belegt, register_belegt, geprueft_am, quelle")
      .eq("domain", domain).eq("identity_id", identityId).maybeSingle();
    if (!data) return null;
    const alter = (Date.now() - new Date(data.geprueft_am).getTime()) / 86_400_000;
    if (alter > (FRIST_TAGE[data.urteil as Urteil] ?? 1)) return null;
    return {
      urteil: data.urteil as Urteil, quote: data.quote, pfad: data.pfad,
      ortBelegt: data.ort_belegt, registerBelegt: data.register_belegt,
      geprueftAm: data.geprueft_am, quelle: data.quelle,
    };
  } catch {
    // Faellt der Cache aus, wird frisch geprueft — nie „belegt" angenommen und nie
    // abgelehnt. Ein kaputter Cache darf hoechstens langsam machen, nicht falsch.
    return null;
  }
}

export async function schreibeNachweis(
  b: Befund, identityId: string, quelle = "registrierung",
): Promise<void> {
  try {
    await createAdminClient().from("domain_proof").upsert({
      domain: b.domain, identity_id: identityId, urteil: b.urteil,
      quote: b.quote || null, pfad: b.pfad ?? null,
      ort_belegt: b.ortBelegt, register_belegt: b.registerBelegt,
      quelle, sekunden: b.sekunden, geprueft_am: new Date().toISOString(),
    }, { onConflict: "domain,identity_id" });
  } catch {
    // Schreiben ist Beiwerk, nicht Bedingung: das Urteil steht bereits fest und darf dem
    // Nutzer nicht deshalb vorenthalten werden, weil die Datenbank gerade klemmt.
  }
}
