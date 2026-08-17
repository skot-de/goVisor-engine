import { NextRequest, NextResponse } from "next/server";
import { rateLimit, clientIp } from "@/lib/rateLimit";
import { pruefeImpressum, domainErlaubt } from "@/lib/impressum";
import { loadSuppliers } from "@/lib/suppliers";
import { leseNachweis, schreibeNachweis } from "@/lib/supabase/domainProof";

/* Belegt die Anbieterkennung der Mail-Domain, dass sie zu der Firma gehört, auf deren
 * Profil der Nutzer landet?
 *
 * WANN DAS AUFGERUFEN WIRD. Nicht beim Tippen — dafür ist es mit gemessenen 3–6 s zu
 * langsam und der Nutzer würde warten. Sondern in dem Fenster, das ohnehin verstreicht:
 * zwischen „Registrieren" und dem Klick auf den Bestätigungslink. Das dauert Sekunden bis
 * Minuten, der Check ist in drei Sekunden fertig. Es ist geschenkte Zeit.
 *
 * WARUM DER SERVER UND NICHT DER BROWSER. Aus dem Browser wäre der Abruf fremder Seiten
 * durch CORS gesperrt, und der Firmenname darf nicht ans Frontend (die Zuordnung Domain →
 * Firma ist unser Datenbestand, nicht der des Besuchers). Zurück geht deshalb NUR das
 * Urteil, nie der Seiteninhalt und nie, welche Domain wir zu welcher Firma kennen.
 *
 * ⚠ SSRF. Die Domain kommt aus der Mailadresse, die der Nutzer eintippt. `domainErlaubt`
 * sperrt Namen ins private Netz und IP-Literale, und die Prüfung wiederholt sich nach
 * jeder Umleitung. Ohne das wäre dieser Endpunkt ein Portscanner für unser eigenes Netz.
 */

// Node-Laufzeit ist Pflicht: die SSRF-Abwehr loest die Domain per DNS auf, und das
// gibt es in der Edge-Laufzeit nicht. Ohne diese Zeile faellt der Schutz lautlos
// auf den schwaecheren Namensfilter zurueck.
export const runtime = "nodejs";

const PRO_IP = 10;
const FENSTER_MS = 60_000;

export async function POST(req: NextRequest) {
  // Strenger gedrosselt als `entity-verify`: jede Anfrage löst bis zu 15 ausgehende
  // Abrufe aus. Ungedrosselt wäre der Endpunkt ein Verstärker für fremde Ziele.
  const rl = rateLimit(`impressum:${clientIp(req)}`, PRO_IP, FENSTER_MS);
  if (!rl.ok) {
    return NextResponse.json({ error: "zu viele Anfragen" },
      { status: 429, headers: { "retry-after": String(rl.retryAfter) } });
  }

  let body: { id?: string; email?: string; firma?: string; ort?: string };
  try { body = await req.json(); } catch {
    return NextResponse.json({ error: "ungültig" }, { status: 400 });
  }

  const email = String(body.email ?? "").slice(0, 254).toLowerCase();
  const id = String(body.id ?? "").slice(0, 120);
  const dom = email.includes("@") ? email.split("@")[1] ?? "" : "";
  if (!domainErlaubt(dom)) {
    return NextResponse.json({ urteil: "nicht_pruefbar", grund: "keine prüfbare Domain" });
  }

  // Der Firmenname kommt aus UNSEREM Bestand, nicht aus der Anfrage — sonst könnte
  // jemand einen Namen mitschicken, der zufällig auf der fremden Seite steht, und sich
  // das Urteil „belegt" selbst besorgen.
  const s = id ? (await loadSuppliers()).find((x) => x.id === id) : null;
  if (!s?.name) {
    return NextResponse.json({ urteil: "nicht_pruefbar", grund: "Firma nicht bekannt" });
  }
  // Erst nachsehen, ob wir das schon wissen. Spart dem Nutzer die Wartezeit und der
  // fremden Firma bis zu 15 Abrufe — bei jeder einzelnen Registrierung.
  const bekannt = await leseNachweis(dom, id);
  if (bekannt) {
    return NextResponse.json({
      urteil: bekannt.urteil, grund: bekannt.pfad
        ? `Firmenname zu ${Math.round((bekannt.quote ?? 0) * 100)} % im Impressum unter ${bekannt.pfad}`
        : "bereits geprüft",
      sekunden: 0, ortBelegt: bekannt.ortBelegt, registerBelegt: bekannt.registerBelegt,
      ausSpeicher: true,
    });
  }

  // Aliase mitgeben: im Impressum steht oft die Kurzform („ZÜBLIN"), im Vergabedatensatz
  // die volle Firmierung („Ed. Züblin AG"). Gewertet wird die beste Übereinstimmung.
  const b = await pruefeImpressum(dom, [s.name, ...(s.aliases ?? [])].slice(0, 8));
  // Nicht abwarten: das Urteil steht fest und soll nicht auf die Datenbank warten.
  void schreibeNachweis(b, id);
  // Nur das Urteil zurück. `worte`/`pfad` blieben harmlos, aber sie verraten, wonach wir
  // suchen — und damit, wie man den Check gezielt bedient.
  return NextResponse.json({
    urteil: b.urteil, grund: b.grund, sekunden: Math.round(b.sekunden * 100) / 100,
    ortBelegt: b.ortBelegt, registerBelegt: b.registerBelegt,
  });
}
