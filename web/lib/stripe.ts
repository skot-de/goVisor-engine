import "server-only";

/* Stripe (Ticket #6) — INTEGRATIONS-STUB. Ohne STRIPE_SECRET_KEY passiert nichts Echtes.
 * Zum Scharfschalten: `stripe`-SDK anbinden, die TODOs füllen und `UMGESETZT` auf `true`
 * setzen. Bewusst kein harter Dependency, damit der Build ohne Stripe-Account läuft.
 * Stripe dient der Karten-Hinterlegung und der Abo-Zahlung. Die Erfolgsprämie, für die
 * dieser Stub urspruenglich mitgedacht war, ist am 2026-08-21 gestrichen.
 *
 * ⚠ DER RIEGEL STAND VERKEHRT HERUM, UND ZWAR AN DER TEUERSTEN STELLE.
 *
 * Vorher lautete jede Funktion sinngemäß:
 *
 *     wenn kein Schlüssel  → { ok: false, stub: true }
 *     sonst                → { ok: true,  stub: false }      ← ohne irgendetwas zu tun
 *
 * Solange kein Schlüssel gesetzt ist, stimmt das. Der Tag, an dem jemand
 * `STRIPE_SECRET_KEY` in die Umgebung schreibt — also der Tag des Starts — war damit auch
 * der Tag, an dem `chargeSubscription` „Zahlung erfolgreich" meldet, ohne dass Geld fliesst.
 * Kein Fehler, kein Protokolleintrag: das System glaubt an eine Buchung, die es nie gab.
 * Ein Schlüssel in der Umgebung ist eben KEINE Aussage darüber, ob der Code, der ihn
 * benutzen soll, geschrieben wurde.
 *
 * Deshalb hängt das Scharfschalten jetzt an `UMGESETZT`, einer Zeile, die derjenige umlegt,
 * der die TODOs füllt — und nicht an einer Umgebungsvariablen, die jemand anders setzt.
 * Ist der Schlüssel da und `UMGESETZT` noch `false`, wird laut abgebrochen statt still
 * gelogen. Ein 500er beim ersten Klick ist die billigste denkbare Form dieses Fehlers.
 */

const KEY = process.env.STRIPE_SECRET_KEY;

/** Ist die Anbindung wirklich geschrieben? Zusammen mit den TODOs unten umlegen. */
const UMGESETZT = false;

/** Nur `true`, wenn Schlüssel UND Umsetzung da sind. */
export const stripeEnabled = UMGESETZT && !!KEY;

function pruefeStand(was: string): void {
  if (KEY && !UMGESETZT) {
    throw new Error(
      `Stripe: STRIPE_SECRET_KEY ist gesetzt, aber ${was} ist nicht implementiert `
      + "(web/lib/stripe.ts, UMGESETZT=false). Lieber laut abbrechen als eine Zahlung "
      + "melden, die nicht stattgefunden hat.");
  }
}

// Karte hinterlegen (SetupIntent) — für spätere Abo-Rechnung.
export async function createSetupIntent(userId: string): Promise<{ clientSecret: string | null; stub: boolean }> {
  pruefeStand("createSetupIntent");
  if (!stripeEnabled) return { clientSecret: null, stub: true };
  // TODO(Integration): const si = await stripe.setupIntents.create({ metadata: { userId } });
  //                    return { clientSecret: si.client_secret, stub: false }
  void userId;
  throw new Error("Stripe: createSetupIntent ist als umgesetzt markiert, aber leer.");
}

// Abo-Rechnung (kein Auto-Charge bei Success-Fee — das läuft über HITL + Rechnung).
export async function chargeSubscription(_userId: string, _amount: number): Promise<{ ok: boolean; stub: boolean }> {
  pruefeStand("chargeSubscription");
  if (!stripeEnabled) return { ok: false, stub: true };
  // TODO(Integration): stripe.invoices / paymentIntents …
  throw new Error("Stripe: chargeSubscription ist als umgesetzt markiert, aber leer.");
}
