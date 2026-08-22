/* Gehört diese Domain dieser Firma? — Beleg über die Anbieterkennung.
 *
 * WARUM DAS GEHT. Wer eine geschäftsmäßige Website betreibt, muss eine Anbieterkennung
 * mit Namen und Anschrift führen: § 5 DDG (DE, vormals § 5 TMG), § 5 ECG (AT),
 * Art. 3 Abs. 1 lit. s UWG (CH), Wurzel ist Art. 5 der Richtlinie 2000/31/EG. Der seltene
 * Fall, in dem der Gesetzgeber uns die Datenquelle garantiert, statt dass wir raten.
 *
 * WAS HIER NICHT PASSIERT: DIE DOMAIN SUCHEN. Das ist die ungleich schwerere Aufgabe
 * (gemessen 33–42 % über Namensmuster) und hier gegenstandslos — der Nutzer tippt seine
 * Mailadresse selbst ein, die Domain steht fest. Zu klären ist allein, ob sie ihm gehört.
 *
 * WARUM ES SICH LOHNT. Gemessen am 2026-08-17 an 25 echten Firmen aus `notice_parties`:
 * die stärkste Verunreinigung unserer Kontaktdaten sind Gewinner, deren einzige hinterlegte
 * Mailadresse die Portaladresse ihres AUFTRAGGEBERS ist (7,5 % der Gewinner-Mails; 14 % der
 * Mail-Hashes hätten darüber falsch verifiziert). Der Check lehnte alle acht solchen Fälle
 * ab (LEONHARD WEISS, STRABAG, Siemens Mobility … auf `deutschebahn.com`) und liess die
 * zwei echten Bahn-Töchter durch. Er trennt genau dort, wo der Mail-Hash blind ist.
 *
 * ZEITBUDGET. Median 3,25 s, p90 5,25 s, Maximum 5,81 s — die Kandidatenpfade laufen
 * GLEICHZEITIG, die Gesamtzeit ist die langsamste einzelne Anfrage, nicht ihre Summe.
 * Das passt in das Fenster zwischen „Registrieren" und dem Klick auf den Bestätigungslink.
 *
 * DREI URTEILE, NICHT ZWEI. „Kein Beleg" und „widerlegt" sind verschiedene Dinge mit
 * verschiedenen Folgen. `hentschke-bau.de` und `cnhind.com` scheitern an kaputten
 * Zertifikaten der GEGENSEITE (auch mit curl). Wer das als „widerlegt" verbucht, sperrt
 * eine echte Firma aus, weil ihr Hoster schlampt.
 *
 * ⚠ ZWILLING: `govisor/impressum.py` hält dieselben Regeln für den Stapelbetrieb
 * (Anreicherung unserer eigenen Entitäten, offline). Ändert sich eine Regel — Pfadliste,
 * Faltung, Schwelle — muss sie in BEIDE Dateien. Diese hier ist die Fassung, die im
 * Deploy läuft; Python im Request-Pfad wäre nicht serverless-fähig (siehe `/firma`).
 */

export const BELEGT = "belegt";
export const WIDERLEGT = "widerlegt";
export const NICHT_PRUEFBAR = "nicht_pruefbar";
export type Urteil = typeof BELEGT | typeof WIDERLEGT | typeof NICHT_PRUEFBAR;

/* goVisor ist EU-weit geplant (CLAUDE.md) — die Anbieterkennung heisst nicht überall
 * „Impressum". Die Pflicht ist dieselbe, der Pfad nicht. Ohne diese Liste wäre der
 * Prüfer ein reines DE/AT/CH-Werkzeug. */
const PFADE = [
  "/impressum", "/impressum/", "/impressum.html", "/de/impressum",   // DE/AT/CH
  "/imprint", "/legal-notice", "/en/imprint",                        // englisch
  "/mentions-legales", "/fr/mentions-legales",                       // FR/BE/LU
  "/aviso-legal",                                                    // ES
  "/note-legali", "/it/note-legali",                                 // IT
  "/colofon", "/juridische-informatie",                              // NL/BE
  "/",                                                               // Startseite zuletzt
];

const KENNUNG = /impressum|imprint|mentions\s+l[ée]gales|aviso\s+legal|note\s+legali|colofon|legal\s+notice|anbieterkennzeichnung/i;

/* Rechtsformen tragen NICHTS zur Zuordnung bei: „GmbH" steht in jedem zweiten Impressum
 * Europas und würde jede beliebige Domain bestätigen. */
const RECHTSFORM = /^(gmbh|ag|kg|ohg|mbh|se|ek|gbr|ug|co|kgaa|ggmbh|partg|mbb|bv|nv|sa|sas|sarl|srl|spa|plc|ltd|inc|oy|ab|as|aps|gesellschaft|aktiengesellschaft|company|societe|und|der|die|das|for|and)$/i;

const REGISTER = /\b(hrb|hra|fn\s*\d|ch-\d|register|registre|registro)\s*[\d.]/i;

const FRIST_MS = 5000;
const MAX_BYTES = 400_000;

/* ⚠ Muss auf BEIDE Seiten des Vergleichs: auf den Firmennamen UND auf den Seitentext.
 * Eine frühere Fassung faltete nur den Namen — „Ed. Züblin AG" wurde zu `zublin`, im
 * Seitentext blieb „züblin" und zerfiel beim Entfernen der Nicht-ASCII-Zeichen zu
 * „z blin". Ergebnis war WIDERLEGT für die eigene, korrekte Domain: ein Fehlurteil in
 * genau die Richtung, die einen echten Kunden aussperrt. */
export function falte(s: string): string {
  return s.toLowerCase()
    .replace(/ß/g, "s")
    .normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, " ");
}

/* „Bärmann" → „baermann". Deutsche Firmen schreiben ihren Namen im Web häufig in
 * Umschrift, weil Domains keine Umlaute vertragen: baermann-partner.de, mueller.de.
 * Die Faltung allein macht daraus `barmann` und trifft nie. Gemessen: einer von elf
 * falsch Widerlegten — und es betrifft jede Firma mit Umlaut im Namen. */
export function umschrift(s: string): string {
  return falte(s.toLowerCase().replace(/ä/g, "ae").replace(/ö/g, "oe")
    .replace(/ü/g, "ue").replace(/ß/g, "ss"));
}

/* ⚠ Untergrenze DREI Zeichen, nicht vier. Gemessen am 2026-08-17: bei vier fielen genau
 * die Kürzel weg, die eine Firma ausmachen — „NEC Deutschland GmbH" behielt nur
 * `deutschland`, „BFT Planung GmbH" nur `planung`. Beide wurden daraufhin auf einer
 * wildfremden Domain zu 100 % bestätigt. Die Regel warf das Unterscheidende weg und
 * behielt das Beliebige. */
/* Organisationszusätze. Was DAHINTER steht, benennt eine Untereinheit, keine Firma:
 * „Ed. Züblin AG Bereich Bonn", „MAN … GmbH - Verkauf Nutzfahrzeuge", „… Inh. Florian
 * Gripp". Gemessen die Ursache eines Teils der falsch Widerlegten: der Zusatz ist im
 * Namensbestand SELTENER als der Markenname und wurde deshalb zum Trägerwort — auf der
 * Firmenwebsite steht er aber nicht. */
const ZUSATZ = /\b(bereich|direktion|niederlassung|zweigniederlassung|werk|filiale|standort|geschaftsstelle|geschaeftsstelle|verkauf|vertrieb|region|abteilung|inh|inhaber|betriebsstatte|betriebsstaette|division|branch|succursale)\b/;

export function stamm(name: string, wie = falte): string {
  const f = wie(name);
  const m = f.match(ZUSATZ);
  return (m && m.index ? f.slice(0, m.index).trim() : f) || f;
}

export function kerne(name: string, wie = falte): string[] {
  return [...new Set(stamm(name, wie).split(" ")
    .filter((w) => w.length >= 3 && !RECHTSFORM.test(w) && !/^\d+$/.test(w)))];
}

/* Wie oft kommt ein Wort in 317.146 Firmennamen vor? Gemessen, nicht geraten — eine
 * handgeschriebene Stoppwortliste wäre sofort veraltet und gälte nur für Deutsch.
 * Gespeichert sind nur Wörter ab 20 Vorkommen; alles Seltenere fehlt und gilt damit
 * automatisch als unterscheidend. */
let HAEUFIG: Record<string, number> | null = null;
async function haeufigkeit(w: string): Promise<number> {
  if (!HAEUFIG) {
    try {
      // ⚠ Über den Daten-Loader: auf einem Deployment kommt die Datei aus dem
      // Objektspeicher (DATA_BASE_URL). Ein direktes readFile fände dort nichts und
      // die Häufigkeiten wären still leer — die Namensprüfung würde stumpf.
      const { loadDataFile } = await import("@/lib/dataSource");
      HAEUFIG = JSON.parse((await loadDataFile("namenswoerter.json")) || "{}").zaehler || {};
    } catch { HAEUFIG = {}; }
  }
  return HAEUFIG?.[w] ?? 0;
}

/* Das Wort, das die Identität trägt: das seltenste im Firmennamen.
 *
 * Eine Quote von „die Hälfte der Wörter steht auf der Seite" ist wertlos, wenn die
 * getroffene Hälfte aus Allerweltswörtern besteht. Gemessen an 200 verwürfelten Paaren
 * kamen so 5,5 % durch — jedes einzelne über `planung`, `deutschland`, `technik`,
 * `systeme`, `solution`. Mit dieser Regel: 0,0 %. */
export async function traeger(k: string[]): Promise<string | null> {
  if (!k.length) return null;
  const mit = await Promise.all(k.map(async (w) => [w, await haeufigkeit(w)] as const));
  mit.sort((a, b) => a[1] - b[1] || b[0].length - a[0].length);
  return mit[0][0];
}

/* Alle Verweise, die zur Anbieterkennung führen. Warum Raten nicht reicht: gemessen
 * führt `matuczak.de` sein Impressum unter `/about/`, und keine noch so lange Pfadliste
 * hätte das getroffen. Ein Mensch braucht sie auch nicht — er liest den Fussbereich. */
const LINK = /<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>([\s\S]{0,80}?)<\/a>/gi;
export function impressumLinks(html: string): string[] {
  const out: string[] = [];
  for (const m of html.matchAll(LINK)) {
    const [, ziel, text] = m;
    if (/^(mailto:|tel:|javascript:|#)/i.test(ziel)) continue;
    if (KENNUNG.test(ziel) || KENNUNG.test(text.replace(/<[^>]+>/g, " "))) out.push(ziel);
    if (out.length >= 4) break;
  }
  return out;
}

/* Die Domain stammt aus der Mailadresse, die der Nutzer eintippt — aus fremder Eingabe.
 * Ein Server, der die ungeprüft abruft, ist ein SSRF-Loch: `foo@localhost` oder eine
 * Domain, die auf 169.254.169.254 zeigt, liesse ihn interne Dienste abfragen und das
 * Ergebnis auch noch zurückmelden. Wir können in der Edge-Runtime nicht auflösen, also
 * sperren wir über den Namen — plus die IP-Literale, die man direkt einsetzen könnte. */
const GESPERRT = /^(localhost|.*\.local|.*\.internal|.*\.localdomain)$/i;
const IP_LITERAL = /^\d{1,3}(\.\d{1,3}){3}$/;

export function domainErlaubt(d: string): boolean {
  if (!d || d.length > 253 || !d.includes(".") || /[/@\s:]/.test(d)) return false;
  if (GESPERRT.test(d)) return false;
  if (IP_LITERAL.test(d)) return false;          // niemand tippt eine IP als Mail-Domain
  return /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/.test(d);
}

/* ⚠ Der Namensfilter oben allein GENÜGT NICHT.
 *
 * Er stoppt `localhost` und getippte IPs — also die naiven Fälle. Der eigentliche
 * Angriff ist ein anderer: eine ganz normal aussehende Domain, deren A-Record der
 * Angreifer kontrolliert und auf `127.0.0.1` oder `169.254.169.254` (Cloud-Metadaten,
 * also Zugangsdaten) zeigen lässt. Dagegen hilft nur, wirklich aufzulösen und die
 * Adresse anzusehen. Der Python-Zwilling tut das seit jeher; hier fehlte es zunächst.
 *
 * Braucht die Node-Laufzeit — deshalb setzt `/api/impressum` ausdrücklich
 * `runtime = "nodejs"`. In der Edge-Laufzeit gäbe es kein DNS und die Prüfung fiele
 * lautlos auf den schwächeren Namensfilter zurück. */
function privat(ip: string): boolean {
  if (ip.includes(":")) {                                   // IPv6
    const l = ip.toLowerCase();
    return l === "::1" || l === "::" || l.startsWith("fe80") || l.startsWith("fc")
        || l.startsWith("fd") || l.startsWith("::ffff:");    // v4-gemappt: separat prüfen
  }
  const o = ip.split(".").map(Number);
  if (o.length !== 4 || o.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return true;
  return o[0] === 0 || o[0] === 10 || o[0] === 127
      || (o[0] === 169 && o[1] === 254)                      // Link-local + Metadaten
      || (o[0] === 172 && o[1] >= 16 && o[1] <= 31)
      || (o[0] === 192 && o[1] === 168)
      || (o[0] === 100 && o[1] >= 64 && o[1] <= 127)         // CGNAT
      || o[0] >= 224;                                        // Multicast + reserviert
}

export async function zieltOeffentlich(host: string): Promise<boolean> {
  if (!domainErlaubt(host)) return false;
  try {
    const { lookup } = await import("node:dns/promises");
    const treffer = await lookup(host, { all: true });
    return treffer.length > 0 && treffer.every((t) => !privat(t.address));
  } catch {
    return false;      // löst nicht auf → nicht prüfbar, nicht „widerlegt"
  }
}

async function hole(domain: string, pfad: string, signal: AbortSignal): Promise<string | null> {
  try {
    const r = await fetch(`https://${domain}${pfad}`, {
      signal, redirect: "follow",
      headers: {
        "user-agent": "goVisor/1.0 (+https://govisor.eu) Impressumspruefung",
        "accept-language": "de,en;q=0.8",
      },
    });
    if (!r.ok || !r.body) return null;
    const ziel = new URL(r.url).hostname.toLowerCase();
    // Umleitungen dürfen die Domain verlassen (viele Firmen liegen auf einer
    // Konzern-Domain), aber nicht ins private Netz zeigen. Auch hier wird
    // AUFGELÖST, nicht nur der Name geprüft: eine Umleitung ist der bequemste
    // Weg, an einem reinen Namensfilter vorbeizukommen.
    if (!(await zieltOeffentlich(ziel))) return null;
    const buf = await r.arrayBuffer();
    return new TextDecoder("utf-8", { fatal: false })
      .decode(buf.byteLength > MAX_BYTES ? buf.slice(0, MAX_BYTES) : buf);
  } catch {
    return null;   // DNS tot, Zertifikat kaputt, Zeitüberschreitung → nicht prüfbar
  }
}

export type Befund = {
  urteil: Urteil; domain: string; firma: string; sekunden: number;
  pfad?: string; quote: number; ortBelegt: boolean; registerBelegt: boolean;
  worte: string[]; grund: string;
};

/* `namen` nimmt bewusst mehrere Schreibweisen: im Impressum steht oft die Kurzform
 * („ZÜBLIN"), im Vergabedatensatz die volle Firmierung („Ed. Züblin AG"). Gewertet wird
 * die BESTE Übereinstimmung — eine gemittelte wäre schlechter, je mehr Aliase wir kennen,
 * und würde ausgerechnet die gut dokumentierten Firmen bestrafen. */
export async function pruefeImpressum(
  domainRoh: string, namen: string | string[], ort?: string | null, schwelle = 0.5,
): Promise<Befund> {
  const t0 = Date.now();
  const liste = (Array.isArray(namen) ? namen : [namen]).filter(Boolean);
  const firma = liste[0] ?? "";
  const domain = (domainRoh || "").trim().toLowerCase().replace(/^\.+/, "");
  const leer = (urteil: Urteil, grund: string): Befund => ({
    urteil, domain, firma, sekunden: (Date.now() - t0) / 1000,
    quote: 0, ortBelegt: false, registerBelegt: false, worte: [], grund,
  });

  if (!(await zieltOeffentlich(domain))) {
    return leer(NICHT_PRUEFBAR, "Domain löst nicht auf oder zeigt nicht ins öffentliche Netz");
  }
  // Zwei Lesarten je Name: gefaltet („barmann") und in Umschrift („baermann").
  const lesarten = liste.flatMap((n) => [kerne(n), kerne(n, umschrift)])
    .filter((k) => k.length > 0);
  if (!lesarten.length) {
    return leer(NICHT_PRUEFBAR, "Firmenname trägt nur Rechtsform, nichts Unterscheidendes");
  }
  const traegerWorte = new Set((await Promise.all(lesarten.map(traeger))).filter(Boolean) as string[]);

  const ac = new AbortController();
  const uhr = setTimeout(() => ac.abort(), FRIST_MS);
  // Explizite Annotation und Zuweisung ueber eine Funktion: TypeScript verengt eine
  // nur in einer Closure gesetzte Variable sonst auf `never`.
  const halten: { b: Befund | null } = { b: null };
  let kennungGelesen = false;          // ⚠ NUR echte Impressumsseiten, nie die Startseite
  let wegweiser: string[] = [];

  const bewerte = (pfad: string, text: string, istStartseite: boolean) => {
    /* Die Startseite darf BESTÄTIGEN, aber niemals WIDERLEGEN.
     *
     * Bestätigen: nur wenn sie selbst eine Anbieterkennung trägt. Ein Firmenname auf
     * irgendeiner Seite wäre sonst schon ein Beleg — das kann auch eine Referenz- oder
     * Partnerliste sein. Gemessen an 200 verwürfelten Paaren kam so KEIN einziges durch,
     * weil zusätzlich das seltene Trägerwort passen muss.
     *
     * Widerlegen: nie. Wer „Impressum" im Menü sieht und daraus schliesst, die Firma stehe
     * nicht drin, urteilt über eine Seite, die er nie gelesen hat — gemessen die Ursache
     * mehrerer Fehlurteile gegen echte Firmen. Dafür ist die Link-Verfolgung da. */
    if (istStartseite && !KENNUNG.test(text)) return;
    const flach = falte(text);
    const worte = new Set(flach.split(" "));
    for (const lesart of lesarten) {
      const gefunden = lesart.filter((w) => worte.has(w));
      // Ohne ein Trägerwort zählt der Treffer NICHT, egal wie hoch die Quote ist.
      if (!gefunden.some((w) => traegerWorte.has(w))) continue;
      const quote = gefunden.length / lesart.length;
      if (!halten.b || quote > halten.b.quote) {
        halten.b = {
          urteil: BELEGT, domain, firma, sekunden: 0, pfad, quote,
          ortBelegt: !!ort && flach.includes(falte(ort).trim()),
          registerBelegt: REGISTER.test(text), worte: gefunden, grund: "",
        };
      }
    }
    /* Eine Startseite ist KEIN Impressum, auch wenn „Impressum" im Menü steht. Wer sie
     * als gelesene Kennung wertet, urteilt WIDERLEGT, ohne je eine Anbieterkennung
     * gesehen zu haben — gemessen die Ursache mehrerer Fehlurteile gegen echte Firmen
     * (matuczak.de führt sein Impressum unter `/about/`). */
    if (!istStartseite && KENNUNG.test(text)) kennungGelesen = true;
  };

  try {
    const seiten = await Promise.all(
      PFADE.map(async (p) => [p, await hole(domain, p, ac.signal)] as const));
    for (const [pfad, text] of seiten) {
      if (!text) continue;
      if (pfad === "/") { wegweiser = impressumLinks(text); bewerte(pfad, text, true); }
      else bewerte(pfad, text, false);
    }
    // Dem Wegweiser folgen. Das ersetzt das Raten von Pfaden.
    if (!kennungGelesen && wegweiser.length) {
      const ziele = wegweiser.slice(0, 3).map((z) =>
        z.startsWith("/") ? z : "/" + z.split("/").slice(3).join("/"));
      for (const [i, text] of (await Promise.all(
        ziele.map((z) => hole(domain, z, ac.signal)))).entries()) {
        if (text) bewerte(ziele[i], text, false);
      }
    }
  } finally {
    clearTimeout(uhr);
  }

  const sek = (Date.now() - t0) / 1000;
  const treffer = halten.b;
  if (treffer && treffer.quote >= schwelle) {
    treffer.sekunden = sek;
    treffer.grund = `Firmenname zu ${Math.round(treffer.quote * 100)} % im Impressum unter ${treffer.pfad}`;
    return treffer;
  }
  if (kennungGelesen) {
    // Impressum da, nennt aber jemand anderen. DAS ist die Aussage, die Sicherheit
    // bringt, und der Fall, der die Portaladressen der Auftraggeber abfängt.
    const b = treffer ?? leer(WIDERLEGT, "");
    b.urteil = WIDERLEGT; b.sekunden = sek;
    b.grund = "Impressum gefunden, nennt diese Firma aber nicht";
    return b;
  }
  return leer(NICHT_PRUEFBAR,
    "kein Impressum erreichbar (Seite tot, Zertifikat kaputt oder Kennung nur per JavaScript)");
}
