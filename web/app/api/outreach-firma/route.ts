import { NextResponse } from "next/server";
import { loadLanding } from "@/lib/outreach";
import { bremse } from "@/lib/rateLimit";

/**
 * Firmenname zu einem Outreach-Token — für die Vorbelegung im Onboarding.
 *
 * **Warum es das gibt.** Wer über `/t/<token>` kommt, hat seine Firma und ihre Zahlen
 * gerade gesehen. Sie im nächsten Schritt neu eintippen zu lassen, verschenkt den einzigen
 * Vorteil dieses Wegs — und ist der Moment, in dem ein kalter Kontakt abspringt.
 *
 * **Warum das nichts Neues preisgibt.** Die Landing-Seite zeigt unter demselben Token
 * bereits Verträge, Wettbewerber und Volumina. Der Name allein ist strikt weniger.
 *
 * **Warum sie vor dem Anmelde-Tor liegen MUSS:** sie wird gebraucht, bevor es ein Konto
 * gibt. Das ist derselbe Grund wie bei `/api/entity-verify`.
 */
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  // Der Token ist zwar nicht zu raten, aber die Route liegt offen und liest je Aufruf eine
  // Datei. 30 pro Minute reichen für den einen Aufruf, den die Vorbelegung braucht.
  const zuViel = bremse(req, "outreachfirma", 30, 60_000);
  if (zuViel) return zuViel;
  const t = new URL(req.url).searchParams.get("t") ?? "";
  // Enges Muster: der Token wandert in einen Dateizugriff. Ohne die Prüfung wäre `../`
  // ein Weg aus dem Datenverzeichnis heraus.
  if (!/^[A-Za-z0-9_-]{1,64}$/.test(t)) {
    return NextResponse.json({ name: null }, { status: 400 });
  }
  const d = await loadLanding(t).catch(() => null);
  // Auch Identitaet und Vorbelegung: der warme Onboarding-Weg ueberspringt die
  // Firmensuche, braucht dafuer aber die Identitaet, an der die Landing haengt.
  // Das gibt nichts preis, was die Landing unter demselben Token nicht ohnehin zeigt.
  return NextResponse.json({
    name: d?.name ?? null,
    id: d?.id ?? null,
    vorbelegung: d?.vorbelegung ?? null,
  }, { headers: { "cache-control": "no-store" } });
}
