import { NextRequest, NextResponse } from "next/server";
import { createHash } from "node:crypto";
import { domainEigentuemer, loadSuppliers } from "@/lib/suppliers";
import { loadLanding } from "@/lib/outreach";
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
  /* `fremd` ist bewusst ein DRITTES Urteil und nicht bloss ein „unbestaetigt" mit
   * anderem Text. Fehlender Beleg und widersprechender Beleg sind verschiedene Dinge:
   * beim ersten wissen wir nichts, beim zweiten wissen wir etwas Gegenteiliges. Nur der
   * zweite rechtfertigt, jemanden aufzuhalten. */
  conf: "belegt" | "unbestaetigt" | "fremd";
  /** Bei `fremd`: wem die Domain nachweislich gehoert. */
  fremdeFirma?: string;
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

  let body: { id?: string; email?: string; token?: string };
  try { body = await req.json(); } catch { return NextResponse.json({ error: "ungültig" }, { status: 400 }); }

  const id = String(body.id ?? "").slice(0, 120);
  const token = String(body.token ?? "").slice(0, 64);
  const email = String(body.email ?? "").slice(0, 254).toLowerCase();
  if (!id || !email.includes("@")) return NextResponse.json({ error: "id und email nötig" }, { status: 400 });

  const dom = email.split("@")[1] ?? "";
  const stamm = dom.split(".")[0] ?? "";

  const s = (await loadSuppliers()).find((x) => x.id === id);
  const bekannt = s?.domain ?? null;
  const belege = s?.domainBelege ?? 0;

  const antwort = (r: VerifyErgebnis) => NextResponse.json(r);

  // ── ZUSTELLQUITTUNG: der staerkste Beleg von allen ────────────────────────────
  // Wir haben den Link an eine bestimmte Adresse geschickt. Wer sich mit GENAU dieser
  // Adresse registriert, kontrolliert das Postfach — das ist ein Beweis, kein Indiz, und
  // er kommt ohne Firmendomain aus. Damit sind auch die 47 % der Firmen erreichbar, zu
  // denen wir keine Domain haben; H. Klostermann Baugesellschaft ist eine davon.
  //
  // Reihenfolge zaehlt: diese Pruefung steht VOR allen anderen. Eine Domain kann geteilt
  // sein, eine Kontaktadresse aus den Vergabeunterlagen kann veraltet sein — die Adresse,
  // an die wir heute geschrieben haben, ist beides nicht.
  //
  // ⚠ Der Token allein belegt NICHTS. Er wird hier nur benutzt, um die erwartete Adresse
  // nachzuschlagen; bewiesen wird ueber die Adresse, die der Nutzer eintippt.
  if (token && /^[A-Za-z0-9_-]{1,64}$/.test(token)) {
    const l = await loadLanding(token).catch(() => null);
    if (l && l.id === id && l.zustellung) {
      if (l.zustellung.hash === mailHash(email)) {
        return antwort({
          conf: "belegt", domainBekannt: !!bekannt,
          grund: "an genau diese Adresse haben wir euch den Link geschickt",
        });
      }
      // Dieselbe DOMAIN wie unsere Zustelladresse. Etwas schwaecher als die Adresse
      // selbst, aber immer noch stark: die Domain haben nicht wir geraten, sondern wir
      // haben an sie geschrieben. Deckt die Kollegin ab, an die intern weitergeleitet
      // wurde — bei Firmen ohne hinterlegte Domain sonst der Regelfall.
      // Freemail-Domains stehen gar nicht erst im Datensatz (s. Generator).
      if (l.zustellung.domain && dom === l.zustellung.domain) {
        return antwort({
          conf: "belegt", domainBekannt: !!bekannt,
          grund: `an ${l.zustellung.domain} haben wir euch den Link geschickt`,
        });
      }
    }
  }

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
  // Eine per IMPRESSUM belegte Domain braucht die Belegzahl nicht.
  //
  // `MIN_BELEGE` ist eine Krücke für die schwächere Quelle: Domains aus Kontaktmails der
  // Vergabeunterlagen tragen gemessen 7,5 % Auftraggeber-Adressen, und mehrere Belege
  // machen einen Ausrutscher unwahrscheinlicher. Beim Impressum-Beleg entfällt dieser
  // Grund — er wurde gegen die Anbieterkennung der Domain selbst geprüft, an 200
  // verwürfelten Paaren mit 0,0 % Fehlbestätigungen. Ihn trotzdem an der Belegzahl zu
  // messen hiesse, die stärkere Quelle an der Schwäche der schwächeren zu bemessen.
  if (bekannt && dom === bekannt && s?.domainQuelle === "impressum") {
    return antwort({
      conf: "belegt", domainBekannt: true,
      grund: `${dom} ist im Impressum als eure Domain belegt`,
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
  // Gehoert die Domain nachweislich einer ANDEREN Firma? Das ist kein Grenzfall mehr.
  // Mehrdeutige Domains (458 von 7.631, meist Konzern-Fragmentierung wie LEONHARD WEISS
  // oder Siemens) stehen gar nicht erst im Index — sie taugen nicht als Vorwurf.
  const eigner = await domainEigentuemer(dom);
  if (eigner && eigner.id !== id) {
    return antwort({
      conf: "fremd", domainBekannt: !!bekannt, fremdeFirma: eigner.name,
      grund: `${dom} gehört in unseren Daten zu ${eigner.name}, nicht zu dieser Firma`,
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
