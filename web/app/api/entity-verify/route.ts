import { NextRequest, NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { loadSuppliers } from "@/lib/suppliers";
import { rateLimit, clientIp } from "@/lib/rateLimit";

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

// Der Endpunkt beantwortet „gehört diese Adresse zu dieser Firma?" — also ein Orakel, mit
// dem man Adressen durchprobieren könnte. Zum Registrieren braucht man ihn ein paar Mal,
// nicht hundertfach. 20 Anfragen je IP und Stunde reichen für jeden echten Ablauf.
const PRO_IP = 20;
const FENSTER_MS = 60 * 60 * 1000;

/** Gleiche Normalisierung wie beim Export (lower + trim), sonst trifft der Hash nie. */
const mailHash = (m: string) => createHash("sha256").update(m.trim().toLowerCase()).digest("hex").slice(0, 16);

export type VerifyErgebnis = {
  conf: "belegt" | "unbestaetigt";
  grund: string;
  /** Kann der Nutzer den Anspruch selbst per Domain belegen? Steuert den Hinweistext. */
  domainBekannt: boolean;
};

export async function POST(req: NextRequest) {
  const rl = rateLimit(`entityverify:${clientIp(req)}`, PRO_IP, FENSTER_MS);
  if (!rl.ok) {
    return NextResponse.json({ error: "zu viele Anfragen" },
      { status: 429, headers: { "retry-after": String(rl.retryAfter) } });
  }

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

  // Stärkster Beleg zuerst: die Adresse selbst steht als Gewinner-Kontakt in den
  // Vergabedaten. Wer sie hat, IST der Kontakt, der die Zuschläge entgegengenommen hat —
  // und das trägt auch bei privaten Adressen, wo der Domain-Abgleich nichts hergibt
  // (gemessen: 2.518 der 2.522 Freemail-Firmen haben eine Adresse hinterlegt).
  if (s?.mailHashes?.includes(mailHash(email))) {
    return antwort({
      conf: "belegt", domainBekannt: !!bekannt,
      grund: "genau diese Adresse steht in den Vergabeunterlagen dieser Firma",
    });
  }
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
