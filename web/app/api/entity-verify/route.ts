import { NextRequest, NextResponse } from "next/server";
import { loadSuppliers } from "@/lib/suppliers";

/* Belegt-Prüfung des Identitäts-Anspruchs — bewusst SERVERSEITIG.
 *
 * Die Firmen-Domain stammt aus den Gewinner-Kontaktadressen der Vergabedaten und liegt nur
 * hier. Gäbe man sie im Suchergebnis mit heraus, wären die Kontaktdomains aller 15.727
 * Firmen über die Suche abgreifbar. Deshalb geht nur das Urteil zurück, nie die Domain.
 *
 * Belegt ist der Anspruch, wenn die Registrierungs-Domain der bekannten entspricht und diese
 * auf mindestens zwei Belegen beruht — 6.810 Firmen haben nur einen einzigen, das ist zu
 * dünn für eine automatische Freigabe. Alles andere wird „unbestaetigt" und kann per
 * Prüfantrag (identity_claims) von Hand geklärt werden.
 */

const FREEMAIL = new Set([
  "gmail", "gmx", "web", "outlook", "hotmail", "yahoo", "t-online", "icloud",
  "aol", "freenet", "arcor", "googlemail", "posteo", "mailbox", "live", "msn",
]);

const MIN_BELEGE = 2;

export type VerifyErgebnis = {
  conf: "belegt" | "unbestaetigt";
  grund: string;
  /** Kann der Nutzer den Anspruch selbst per Domain belegen? Steuert den Hinweistext. */
  domainBekannt: boolean;
};

export async function POST(req: NextRequest) {
  let body: { id?: string; email?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }

  const id = String(body.id ?? "").slice(0, 120);
  const email = String(body.email ?? "").slice(0, 254).toLowerCase();
  if (!id || !email.includes("@")) return NextResponse.json({ error: "id und email nötig" }, { status: 400 });

  const dom = email.split("@")[1] ?? "";
  const stamm = dom.split(".")[0] ?? "";

  const s = (await loadSuppliers()).find((x) => x.id === id);
  const bekannt = s?.domain ?? null;
  const belege = s?.domainBelege ?? 0;

  const antwort = (r: VerifyErgebnis) => NextResponse.json(r);

  if (bekannt && belege >= MIN_BELEGE && dom === bekannt) {
    return antwort({ conf: "belegt", grund: `über eure Firmen-Domain ${dom} bestätigt`, domainBekannt: true });
  }
  if (FREEMAIL.has(stamm)) {
    return antwort({
      conf: "unbestaetigt", domainBekannt: !!bekannt,
      grund: "private E-Mail-Adresse — sie lässt sich keiner Firma zuordnen",
    });
  }
  if (bekannt && belege >= MIN_BELEGE) {
    return antwort({
      conf: "unbestaetigt", domainBekannt: true,
      grund: `eure Adresse endet auf ${dom}; in den Vergabedaten dieser Firma steht eine andere Domain`,
    });
  }
  return antwort({
    conf: "unbestaetigt", domainBekannt: false,
    grund: `zu dieser Firma liegt uns keine Kontakt-Domain vor, mit der wir ${dom} abgleichen könnten`,
  });
}
