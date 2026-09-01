"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { buildProfile } from "@/lib/profileEngine";
import { pwPruefung } from "@/lib/passwort";
import { lesen as checkLesen, verwerfen as checkVerwerfen, alsProfilfelder }
  from "@/lib/checkUebergabe";
import { uebernimmCheck } from "@/lib/supabase/unternehmen";
import { LAENDER } from "@/components/explorer/FilterPanel";
import { register, saveProfile, currentUser } from "@/lib/supabase/auth";
import { track, EV } from "@/lib/analytics";
import { useSprache } from "@/lib/i18n";
import Link from "next/link";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../explorer.css";
import "../zugang.css";
import { CheckMitbringsel } from "@/components/CheckMitbringsel";
import "../landing-oeffentlich.css";
import { staatenAufzaehlung } from "@/lib/staaten";

/* Onboarding — portiert aus INPUT/Design/govisor-onboarding-v1.4.html.
   Registrierung + Firmen-Matching + Profil in einem ganzseitigen Flow. Die Demo-ENTITIES
   der Vorlage sind hier durch das echte Matching (/api/entity-search, /api/entity-group)
   ersetzt; E-Mail/Passwort sind UI-Stub bis Supabase-Auth (Ticket #6). */

const PROFILE_KEY = "govisor.profile.v1";

type Feld = { cpv4: string; label: string | null; wins: number };
type Feld6 = { cpv6: string; wins: number };
type Match = {
  id: string; name: string; wins: number; buyers: number | null; seit: number | null;
  fields: Feld[]; fields6?: Feld6[]; regions: string[];
  regionTyp?: 'regional'|'teilregional'|'bundesweit'|null; volMedian: number | null; strong: boolean;
  topBuyers?: { name: string; wins: number; seit: number; bis: number }[];
  topShare?: number | null;
};
type Member = { name: string; conf: "belegt" | "unsicher"; method: string; wins: number };

const BRANCHEN: { k: string; n: string; x: string }[] = [
  { k: "it", n: "IT & Software", x: "Software, Hardware, Rechenzentrum, Managed Services" },
  { k: "bau", n: "Bau & Infrastruktur", x: "Hoch- und Tiefbau, Gewerke, Sanierung" },
  { k: "medizin", n: "Medizin & Gesundheit", x: "Geräte, Verbrauchsmaterial, Klinikdienste" },
  { k: "beratung", n: "Beratung & Dienstleistung", x: "Planung, Gutachten, Facility, Personal" },
  { k: "sicherheit", n: "Sicherheit & Verteidigung", x: "Schutz, Funk, Wach- und Sicherheitsdienste" },
  { k: "energie", n: "Energie & Versorgung", x: "Strom, Wärme, Wasser, Netze" },
];
const REGIONEN: string[] = ["Bundesweit", "Bund (Bundesbehörden)", ...LAENDER.map((l) => l[1])];
const nameToNuts = (name: string) => name === "Bund (Bundesbehörden)" ? "BUND" : (LAENDER.find((l) => l[1] === name)?.[0] || null);

const FREEMAIL = ["gmail", "gmx", "web", "outlook", "hotmail", "yahoo", "t-online", "icloud"];
const GENERIK = ["stadt", "gemeinde", "kreis", "arge", "vergabekammer", "firma", "mail", "info"];
function domainStamm(mail: string): string | null {
  const dom = (mail.split("@")[1] || "").split(".")[0].toLowerCase();
  if (!dom || FREEMAIL.includes(dom) || GENERIK.includes(dom)) return null;
  return dom;
}
/* Wie gut ist der Anspruch auf eine Firma belegt?
 *
 * Vorher stand überall hart `entityConfidence: "confirmed"` — mit einer Gmail-Adresse
 * konnte jeder „ja, wir sind CANCOM" anklicken und bekam ein als belegt markiertes Profil.
 * Die Abstufung kennt die Engine längst (⚠-Guard, Ticket #11 §4.2), sie wurde nur nie befüllt.
 *
 * Geprüft wird SERVERSEITIG gegen die Firmen-Domain aus den Vergabedaten (51,5 % der Firmen
 * haben eine). Sie darf nicht ins Frontend — sonst wären die Kontaktdomains aller Firmen
 * über die Suche abgreifbar. Deshalb kommt hier nur das Urteil zurück.
 */
type Beleg = { conf: "belegt" | "unbestaetigt" | "fremd"; grund: string;
               domainBekannt: boolean; fremdeFirma?: string };

/* Zweiter, unabhaengiger Beleg: die Anbieterkennung der Mail-Domain (§ 5 DDG und die
 * europaeischen Entsprechungen). Er beantwortet genau die Frage, die der Mail-Hash offen
 * laesst — gehoert das, was hinter dem @ steht, dieser Firma?
 *
 * Gemessen am 2026-08-17: Median 3,25 s, p90 5,25 s. Zu langsam, um beim Tippen darauf zu
 * warten, aber muehelos schnell genug fuer das Fenster bis zum Klick auf den
 * Bestaetigungslink. Deshalb wird er hier gestartet und ERST SPAETER eingesammelt.
 *
 * Der entscheidende Fund: er faengt die Faelle ab, in denen die einzige hinterlegte
 * Mailadresse einer Firma die Portaladresse ihres AUFTRAGGEBERS ist (7,5 % der
 * Gewinner-Mails). Acht von acht solcher Faelle wurden abgelehnt, die zwei echten
 * Konzerntoechter derselben Domain durchgelassen. */
type ImpressumUrteil = { urteil: "belegt" | "widerlegt" | "nicht_pruefbar"; grund: string };

async function pruefeImpressumWeb(id: string, email: string): Promise<ImpressumUrteil> {
  try {
    const r = await fetch("/api/impressum", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ id, email }),
    });
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch {
    // Faellt der Check aus, gilt NICHT „widerlegt" — sonst sperrt eine kaputte Leitung
    // auf unserer Seite einen echten Kunden aus.
    return { urteil: "nicht_pruefbar", grund: "Prüfung gerade nicht möglich" };
  }
}

async function pruefeBeleg(id: string, email: string, token?: string | null): Promise<Beleg> {
  try {
    const r = await fetch("/api/entity-verify", {
      method: "POST", headers: { "content-type": "application/json" },
      // Der Token dient nur dem Nachschlagen der Zustelladresse, nicht als Berechtigung.
      body: JSON.stringify({ id, email, token: token || undefined }),
    });
    if (!r.ok) throw new Error(String(r.status));
    return await r.json();
  } catch {
    // Fällt der Abgleich aus, wird NICHT stillschweigend „belegt" angenommen.
    return { conf: "unbestaetigt", grund: "Prüfung gerade nicht möglich", domainBekannt: false };
  }
}

const norm = (s: string) => s.toLowerCase().replace(/[^a-zäöüß0-9]/g, "");
/** Kurzform fuer die Zusammenfassung: 1.000.000 → „1 Mio €". */
const eur = (n: number) => n >= 1_000_000 ? `${(n / 1_000_000).toLocaleString("de-DE",
  { maximumFractionDigits: 1 })} Mio €` : `${n.toLocaleString("de-DE")} €`;


type Screen = "mail" | "firma" | "vorschlag" | "kandidaten" | "profil" | "branche" | "region" | "fertig";
const SCHRITTE: [string, string][] = [["mail", "Konto"], ["firma", "Firma"], ["profil", "Profil"], ["fertig", "Fertig"]];
const stufeVon = (s: Screen) =>
  ({ mail: 0, firma: 1, vorschlag: 1, kandidaten: 1, profil: 2, branche: 1, region: 1, fertig: 3 }[s] ?? 0);

async function suche(q: string): Promise<Match[]> {
  if (q.trim().length < 2) return [];
  try {
    const d = await fetch(`/api/entity-search?q=${encodeURIComponent(q.trim())}`).then((r) => r.json());
    return d.matches || [];
  } catch { return []; }
}


/* Was wir über eine Firma wissen — die eine Stelle, an der der Wiedererkennungs-Moment
 * entsteht. „200 Zuschläge" beeindruckt niemanden; die eigenen Auftraggeber namentlich
 * zu lesen schon. Jede Zahl kommt aus den Vergabedaten, nichts ist geschätzt.
 * Der typische Auftragswert fehlt bei den meisten Firmen bewusst (nur 1.033 von 30.509
 * haben genug verschiedene belegte Werte) — lieber keine Zahl als eine erfundene. */
function FirmaFakten({ m }: { m: Match }) {
  const { t } = useSprache();
  const jahre = m.seit ? new Date().getFullYear() - m.seit : null;
  const eur = (v: number) =>
    v >= 1e6 ? t("{n} Mio €", { n: (v / 1e6).toFixed(1).replace(".", ",") })
             : t("{n} Tsd €", { n: Math.round(v / 1000) });
  const klumpen = (m.topShare ?? 0) >= 0.4 ? m.topBuyers?.[0] : null;

  return (
    <div className="fakten">
      <div className="fk-zahlen">
        <div className="fk-z"><b>{m.wins.toLocaleString("de-DE")}</b><span>{t("Zuschläge")}</span></div>
        <div className="fk-z"><b>{(m.buyers ?? 0).toLocaleString("de-DE")}</b><span>{t("Auftraggeber")}</span></div>
        {m.seit ? <div className="fk-z"><b>{jahre}</b><span>{t("Jahre am Markt")}</span></div> : null}
        {m.volMedian ? <div className="fk-z"><b>{eur(m.volMedian)}</b><span>{t("typischer Auftrag")}</span></div> : null}
      </div>

      {m.topBuyers?.length ? (
        <div className="fk-block">
          <h4>{t("Eure größten Auftraggeber")}</h4>
          <ul className="fk-kunden">
            {m.topBuyers.map((k) => (
              <li key={k.name}>
                <span className="fk-kn">{k.name}</span>
                <span className="fk-kw">{k.wins} {k.wins === 1 ? t("Auftrag") : t("Aufträge")} · {k.seit === k.bis ? k.seit : `${k.seit}–${k.bis}`}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Das ist kein Schmuck, sondern der Grund, warum jemand uns braucht: wer 98 % seiner
          Aufträge von einer Stelle bekommt, hat ein Risiko, das er selten beziffert sieht. */}
      {klumpen ? (
        <div className="fk-warn">
          <b>{t("{p} % eurer Zuschläge kommen von {firma}.", { p: Math.round((m.topShare ?? 0) * 100), firma: klumpen.name })}</b>
          <span>{t("Fällt dieser Auftraggeber weg, fehlt der Großteil. Genau dafür zeigen wir euch, wo es vergleichbare Ausschreibungen gibt.")}</span>
        </div>
      ) : null}

      {m.regionTyp && m.regions?.length ? (
        <p className="fk-fuss">
          {t("Schwerpunkt {wo}, aus euren Zuschlägen abgeleitet.",
             { wo: m.regionTyp === "regional" ? t("regional") : t("in mehreren Regionen") })}
        </p>
      ) : m.regionTyp === "bundesweit" ? (
        <p className="fk-fuss">{t("Bundesweit tätig, aus euren Zuschlägen abgeleitet.")}</p>
      ) : null}
    </div>
  );
}

export default function OnboardingPage() {
  const { t } = useSprache();
  const router = useRouter();
  const [screen, setScreen] = useState<Screen>("mail");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [authFehler, setAuthFehler] = useState<string | null>(null);
  const [eingabe, setEingabe] = useState("");
  const [ausDomain, setAusDomain] = useState(false);
  const [matches, setMatches] = useState<Match[]>([]);      // Autocomplete / Kandidaten
  const [acOpen, setAcOpen] = useState(false);
  const [matched, setMatched] = useState<Match | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [aktiv, setAktiv] = useState<Set<string>>(new Set());
  const [branche, setBranche] = useState<string | null>(null);
  const [regionen, setRegionen] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [offen, setOffen] = useState<string | null>(null);      // aufgeklappte Kandidaten-Karte
  const [keineDavon, setKeineDavon] = useState(false);          // Eingabefeld inline zeigen
  const [beleg, setBeleg] = useState<Beleg | null>(null);       // Ergebnis des Domain-Abgleichs
  // Der laufende Impressum-Check. Als Ref, nicht als State: er darf kein Rendern
  // ausloesen, solange er unterwegs ist — der Nutzer soll nichts davon merken.
  const impressumRef = useRef<{ id: string; lauf: Promise<ImpressumUrteil> } | null>(null);
  const [impressum, setImpressum] = useState<ImpressumUrteil | null>(null);
  const [antragText, setAntragText] = useState("");             // Freitext für die manuelle Prüfung
  const [antragGesendet, setAntragGesendet] = useState(false);
  const [vomToken, setVomToken] = useState(false);
  const [tokenFirma, setTokenFirma] = useState<{ id: string; name: string } | null>(null);
  const [tokenWert, setTokenWert] = useState<string | null>(null);
  /* TESTLAUF — den Ablauf durchspielen, ohne Konto und ohne Mail.
   *
   * Meine erste Fassung sperrte fremde Domains und verhinderte damit genau den Test, um
   * den es geht. Sven: „ich will da trotzdem gerne peter@gmail.com, peter@cancom.de und
   * peter@klostermann.de eintippen, um zu sehen wie sich die anmeldung verhält — darum
   * geht es doch gerade."
   *
   * Der Denkfehler war meiner: Registrierung und Belegprüfung hingen aneinander, obwohl
   * die Prüfung gar kein Konto braucht. Sie ist eine reine Funktion von (Firma, Adresse).
   * Im Testlauf entfällt nur das `register()` — alles andere läuft ECHT, samt Prüfung
   * gegen die Vergabedaten. Damit sind alle drei Fälle durchspielbar, ohne dass eine
   * einzige Mail eine echte Firma erreicht. */
  const testbetrieb = process.env.NODE_ENV !== "production";
  const [probe, setProbe] = useState(false);      // Firma kam aus der Outreach-Landing
  /* Angaben aus dem Eignungs-Check der Startseite. EINMAL beim Laden gelesen, nicht
   * erst beim Fertigstellen: der Abschlussbildschirm soll sie ZEIGEN. Eine stille
   * Vorbelegung waere schlechter als gar keine — wer sich vertippt hat, koennte es
   * nie bemerken, und die Zahl wirkt trotzdem auf jede Lead-Bewertung. */
  const [checkAngaben] = useState(() =>
    (typeof window === "undefined" ? null : checkLesen()));
  // ── ZURÜCK ────────────────────────────────────────────────────────────────────────
  // Sven beim Anlegen eines Profils: „es wäre schön, wenn man bei der anmeldung auch
  // zurück springen kann." Es gab Rückwege, aber nur auf zwei Bildschirmen — wer sich
  // vertippt hatte, kam von den übrigen nur über einen Neustart heraus.
  //
  // Ein Verlaufsstapel statt fester Rücksprünge: der Weg durchs Onboarding hat mehrere
  // Verzweigungen (Firma erkannt oder nicht, Vorschlag oder Kandidaten, warmer Weg über
  // Token), und eine Tabelle „von X kommt man nach Y" wäre bei der nächsten Verzweigung
  // schon wieder falsch. Der Stapel weiss immer, wo man wirklich herkam.
  const [verlauf, setVerlauf] = useState<Screen[]>([]);

  /** Einen Schritt weiter — und sich merken, von wo. */
  const geheZu = (ziel: Screen) => { setVerlauf((v) => [...v, screen]); setScreen(ziel); };
  /** Einen Schritt zurück. Eingaben bleiben stehen, es wird nichts verworfen. */
  const zurueck = () => {
    if (!verlauf.length) return;
    setScreen(verlauf[verlauf.length - 1]);
    setVerlauf(verlauf.slice(0, -1));
  };
  const pwStatus = pwPruefung(pw, email);
  const pwOk = pwStatus.ok;

  const acRef = useRef<HTMLDivElement>(null);

  /**
   * Kam der Besuch über eine Outreach-Landing (`/t/<token>`)? Dann ist die Firma bereits
   * bekannt — sie stand gerade groß auf dem Bildschirm, mitsamt ihren Verträgen.
   *
   * Sie hier neu eintippen zu lassen wäre der Moment, in dem ein kalter Kontakt abspringt:
   * wir fragen nach etwas, das wir selbst gerade vorgerechnet haben.
   *
   * Über `window.location` statt `useSearchParams`, weil letzteres in Next 15 eine
   * Suspense-Grenze um die ganze Seite verlangt — für einen optionalen Parameter, der nur
   * einen Vorschlag füllt, wäre das die falsche Reihenfolge von Aufwand und Wirkung.
   */
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    if (q.get("probe") === "1") setProbe(true);
    // `?firma=` als Vorbelegung: kam von einem Feld auf der Startseite, das dort am
    // 2026-08-21 wieder verschwunden ist. Der Eingang bleibt, weil er nichts kostet und
    // fuer Anschreiben nuetzlich ist — nur ein Vorschlag, bestaetigt wird ueber die
    // Firmensuche.
    const mit = (q.get("firma") || "").trim();
    if (mit) setEingabe(mit.slice(0, 120));
    const tok = q.get("t");
    if (!tok) return;
    setTokenWert(tok);
    fetch(`/api/outreach-firma?t=${encodeURIComponent(tok)}`)
      .then((r) => r.json())
      .then((d) => {
        // NUR vorschlagen, nie festschreiben: das Feld bleibt frei änderbar, und der
        // Treffer wird ganz normal über die Firmensuche bestätigt. Ein Token ist ein
        // Hinweis darauf, wen wir angeschrieben haben — kein Beleg, wer da tippt.
        if (!d?.name) return;
        setEingabe(d.name);
        setVomToken(true);
        // WARMER WEG: Firma steht fest, Vorbelegung kommt aus der eigenen Historie.
        if (d.id) setTokenFirma({ id: d.id, name: d.name });
        if (d.vorbelegung?.branche) setBranche(d.vorbelegung.branche);
        if (d.vorbelegung?.regionen?.length) {
          setRegionen(d.vorbelegung.regionen
            .map((n: string) => LAENDER.find((l) => l[0] === n)?.[1])
            .filter(Boolean) as string[]);
        }
      })
      .catch(() => {});
  }, []);

  // Schon eingeloggt (z. B. „Profil bearbeiten")? → Konto-/Registrierungs-Screen überspringen.
  useEffect(() => {
    currentUser().then((u) => { if (u) { setEmail(u.email ?? ""); geheZu("firma"); } }).catch(() => {});
  }, []);

  // Autocomplete auf der Firma-Seite (debounced).
  // ACHTUNG: Der Effekt lief früher auch beim VERLASSEN des Firma-Screens und rief dort
  // setMatches([]) auf — womit er die Kandidatenliste löschte, die zumMatch() gerade
  // gefüllt hatte. Der Kandidaten-Screen zeigte deshalb immer „Kein Treffer".
  // Geleert wird jetzt nur noch, solange wir wirklich auf dem Firma-Screen sind.
  useEffect(() => {
    if (screen !== "firma") return;
    if (eingabe.trim().length < 2) { setMatches([]); return; }
    // NICHT `t` nennen — das würde die Übersetzungsfunktion überdecken.
    const timer = setTimeout(async () => setMatches(await suche(eingabe)), 220);
    return () => clearTimeout(timer);
  }, [eingabe, screen]);

  const ladeMitglieder = useCallback(async (m: Match): Promise<number> => {
    try {
      const d = await fetch(`/api/entity-group?id=${encodeURIComponent(m.id)}`).then((r) => r.json());
      const ms: Member[] = d.members || [];
      setMembers(ms);
      // ── PLAUSIBILITÄTSBREMSE, TEIL 1: die Vorauswahl folgt der Beleglage ──────────
      // Sven: „was ist wenn ich bei der frage ‚gehören die einheiten zu euch' einfach was
      // dazu klicke, was eig gar nicht dazu gehört?" Bis zum 2026-08-21 waren ALLE
      // Einheiten vorangehakt, auch die nur über den Namen erkannten. Wer nichts tut,
      // bestätigt damit fremde Zuschläge — und das Bequeme war das Unbelegte.
      // Jetzt sind belegte Einheiten (Handelsregister, nationale Kennung) angehakt, die
      // nur namentlich erkannten nicht. Wer sie will, hakt sie bewusst an.
      // Nach Index keyen — gleichnamige Schwester-Entities (mehrere „CANCOM Public GmbH") kollabieren sonst.
      const belegte = ms.map((m, i) => (m.conf === "belegt" ? String(i) : null))
                        .filter((x): x is string => x !== null);
      // Sackgasse vermeiden: 7 der 31.418 Gruppen haben KEIN belegtes Mitglied (gemessen
      // 2026-08-21, u. a. „BS/ENERGY", „Dr. Löber IGV mbH"). Ohne Haken ist „Profil
      // bestätigen" gesperrt (s. disabled={!aktiv.size}) und das Onboarding endet blind.
      // Dort haken wir die grösste Einheit an: der Nutzer hat diese Firma im Schritt davor
      // selbst bestätigt, die Namensgleichheit ist also mehr als eine Vermutung.
      const groesste = ms.reduce((b, m, i) => (m.wins > (ms[b]?.wins ?? -1) ? i : b), 0);
      setAktiv(new Set(belegte.length ? belegte : ms.length ? [String(groesste)] : []));
      return ms.length;
    } catch { setMembers([]); setAktiv(new Set()); return 0; }
  }, []);

  // Der Abgleich läuft, sobald eine Firma angezeigt wird — nicht erst beim Abschluss,
  // damit der Nutzer den Status sieht, bevor er bestätigt.
  useEffect(() => {
    const m = matched ?? (offen ? matches.find((x) => x.id === offen) : null);
    if (!m || !email.includes("@")) { setBeleg(null); return; }
    let weg = false;
    pruefeBeleg(m.id, email).then((b) => { if (!weg) setBeleg(b); });
    // Der Impressum-Check laeuft PARALLEL und wird NICHT abgewartet. Er braucht gemessen
    // 3–6 s; das Fenster dafuer ist die Zeit, die der Nutzer ohnehin auf die
    // Bestaetigungsmail wartet. Eingesammelt wird er erst in `bestaetigen()`.
    impressumRef.current = { id: m.id, lauf: pruefeImpressumWeb(m.id, email) };
    return () => { weg = true; };
  }, [matched, offen, matches, email]);

  /* Den im Hintergrund laufenden Impressum-Check einsammeln.
   *
   * Beide Wege des Erkennungsschirms brauchen ihn — „Ja, das sind wir" UND der Antrag auf
   * Freischaltung. Eine fruehere Fassung sammelte ihn nur im Bestaetigungsweg ein, im
   * Antragsweg war das Urteil deshalb immer `null`: ausgerechnet dort, wo die Handpruefung
   * am dringendsten einen Beleg braucht.
   *
   * Die Frist ist kurz und absichtlich so: der Check laeuft seit der Erkennung und ist
   * gemessen nach 3–6 s fertig. Wer schneller klickt, soll nicht warten — ein spaeter
   * Beleg ist wertlos, ein wartender Nutzer ist ein Schaden. */
  async function holeImpressum(id: string): Promise<ImpressumUrteil | null> {
    const r = impressumRef.current;
    if (!r || r.id !== id) return null;
    const spaet: ImpressumUrteil = { urteil: "nicht_pruefbar", grund: "noch nicht fertig" };
    const u = await Promise.race([
      r.lauf, new Promise<ImpressumUrteil>((f) => setTimeout(() => f(spaet), 2500)),
    ]).catch(() => spaet);
    setImpressum(u);
    return u;
  }

  async function antragSenden(m: Match) {
    const impressum = await holeImpressum(m.id);
    const { saveClaim } = await import("@/lib/supabase/claims");
    // Das Impressum ist ein eigenstaendiger Beleg und wird deshalb MITGESCHRIEBEN, auch
    // wenn der Domain-Abgleich nichts hergab: die Handpruefung soll sehen, worauf sie
    // sich stuetzen kann. „belegt" hebt den Antrag; „widerlegt" ist der wertvollere Fall,
    // weil er dem Pruefenden die Arbeit abnimmt.
    const imp = impressum?.urteil === "belegt" || impressum?.urteil === "widerlegt"
      ? ` · Impressum: ${impressum.grund}` : "";
    await saveClaim({
      identityId: m.id, companyName: m.name,
      emailDomain: (email.split("@")[1] ?? null),
      status: impressum?.urteil === "belegt" ? "belegt" : "unbestaetigt",
      grund: (beleg?.grund ?? "") + imp, nachricht: antragText.trim() || undefined,
    }).catch(() => ({ error: "speichern fehlgeschlagen" }));
    setAntragGesendet(true);
  }

  async function bestaetigen(m: Match) {
    setMatched(m);
    const imp = await holeImpressum(m.id);
    /* Auch der BESTAETIGUNGS-Weg schreibt einen Claim.
     *
     * Bis hierher tat er das nicht: er sammelte das Impressum-Urteil ein und warf es beim
     * Seitenwechsel weg. Damit fehlte ausgerechnet fuer den Hauptweg der Beleg, WARUM
     * jemand Zugriff auf ein fremdes Firmenprofil bekommen hat — bei einer Beschwerde
     * („da war jemand in unseren Daten") haetten wir nichts vorzuweisen gehabt.
     *
     * Der Nachweis selbst liegt serverseitig in `domain_proof`; hier steht nur, welcher
     * Nutzer sich auf welche Firma berufen hat und worauf wir uns dabei gestuetzt haben. */
    const { saveClaim } = await import("@/lib/supabase/claims");
    const belegt = imp?.urteil === "belegt" || beleg?.conf === "belegt";
    void saveClaim({
      identityId: m.id, companyName: m.name,
      emailDomain: (email.split("@")[1] ?? null),
      status: belegt ? "belegt" : "unbestaetigt",
      grund: [beleg?.grund, imp && imp.urteil !== "nicht_pruefbar"
        ? `Impressum: ${imp.grund}` : null].filter(Boolean).join(" · "),
    }).catch(() => undefined);
    await ladeMitglieder(m);
    geheZu("profil");
  }

  // Konto anlegen (Registrierung), dann Firmen-Erkennung. Bei „E-Mail existiert" → Login anbieten.
/* ══ TESTSPERRE: keine Mail an fremde Firmen ═══════════════════════════════════════
 *
 * `signUp` schickt die Bestaetigung an GENAU die Adresse im Feld. Wer beim Ausprobieren
 * „peter@klostermann.de" eintippt, loest damit eine echte Mail an einen echten Menschen
 * in einer echten Firma aus — von einem Absender, den er nicht kennt.
 *
 * Gemessen am 2026-08-17 im Projekt: `peter@cancom.de` (27.07., sogar bestaetigt) und
 * `peter@klostermann.de` (heute). Beides Firmen, die wir spaeter sauber ansprechen wollen.
 * Sven, als es ihm auffiel: „wir sind gerade in einem testszenario, wieso gehen ueberhaupt
 * mails raus? wenn ich mich als peter@klostermann.de ausgebe, dann ist wohl offensichtlich
 * das das nicht meine mailadresse ist?!"
 *
 * Die Sperre greift NUR ausserhalb der Produktion — in Produktion registrieren sich echte
 * Firmen mit echten Adressen, dort waere sie falsch. Ueber `NEXT_PUBLIC_TEST_DOMAINS`
 * erweiterbar.
 *
 * Sie ist ein Schutz gegen VERSEHEN, nicht gegen Absicht: der Aufruf laeuft im Browser
 * und liesse sich umgehen. Das reicht — hier tippt niemand aus boeser Absicht, sondern
 * beim Ausprobieren.
 *
 * ⚠ WAS HIER STEHT, STEHT IM BROWSER. `NEXT_PUBLIC_*` wird ins Bundle gebacken und ist
 * lesbar. In der eingebauten Liste standen bis zum 2026-08-30 `skot.de` und `skot.io` —
 * die Domains des Betreibers. Sie verrieten nichts Gefaehrliches, verknuepften die
 * Anwendung aber mit einer Person, und dafuer gibt es keinen Grund: die Liste braucht nur
 * Adressen, an die ohnehin nie eine echte Mail geht. Die Vorgabe enthaelt deshalb nur noch
 * die reservierten Namen aus RFC 2606. Wer eigene ergaenzt, tut das ueber die Variable und
 * weiss dann, dass sie oeffentlich sind.
 */
const TEST_DOMAINS = (process.env.NEXT_PUBLIC_TEST_DOMAINS
  || "example.com,example.org,example.net,localhost,test,invalid")
  .split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);

function testMailErlaubt(mail: string): boolean {
  if (process.env.NODE_ENV === "production") return true;
  const dom = (mail.split("@")[1] || "").toLowerCase();
  return TEST_DOMAINS.some((d) => dom === d || dom.endsWith("." + d));
}

  /* Anbieter-Fehler in Klartext.
   *
   * Supabase antwortet auf Englisch und in seinem eigenen Vokabular. „email rate limit
   * exceeded" ist fuer uns eine Diagnose, fuer den Nutzer eine Sackgasse: er weiss weder,
   * was ein Rate Limit ist, noch dass es von selbst vergeht. Genau das ist Sven beim
   * Durchklicken passiert (2026-08-17).
   *
   * Was hier NICHT passiert: alles auf eine Sammelmeldung abbilden. Unbekannte Fehler
   * gehen im Wortlaut durch — eine erfundene Erklaerung waere schlimmer als eine fremde. */
  function klartext(m: string): string {
    if (/rate limit/i.test(m)) {
      return "Zu viele Registrierungen in kurzer Zeit. Der Mailversand ist gedeckelt; "
           + "in etwa einer Stunde geht es wieder.";
    }
    if (/invalid format|valid email/i.test(m)) return "Diese E-Mail-Adresse sieht nicht gültig aus.";
    if (/password/i.test(m)) return "Das Passwort erfüllt die Mindestanforderungen nicht.";
    if (/signup.*disabled/i.test(m)) return "Registrierung ist gerade abgeschaltet.";
    return m;
  }

  async function kontoAnlegen() {
    setAuthFehler(null);
    // Testlauf: kein Konto, keine Mail — der Rest des Ablaufs laeuft unveraendert weiter.
    // Die Domain-Sperre entfaellt hier bewusst: es wird ja nichts verschickt, und genau
    // die fremden Domains sind das Interessante am Test.
    if (probe && testbetrieb) {
      setBusy(true);
      await erkennen();
      setBusy(false);
      return;
    }
    if (!testMailErlaubt(email)) {
      setAuthFehler(
        `Testbetrieb: an ${email.split("@")[1]} wird nichts verschickt. Diese Domain gehört `
        + `einer echten Firma, und die Bestätigungsmail ginge wirklich dorthin. `
        + `Erlaubt sind: ${TEST_DOMAINS.join(", ")}.`);
      return;
    }
    setBusy(true);
    const { error } = await register(email, pw);
    setBusy(false);
    if (error && !/already registered|already exists/i.test(error.message)) { setAuthFehler(klartext(error.message)); return; }
    if (error) { setAuthFehler("Diese E-Mail hat schon ein Konto, bitte anmelden."); return; }
    await erkennen();   // signUp ok (mit oder ohne sofortige Session) → weiter im Flow
  }

  // E-Mail → Domain-Stamm ableiten und matchen (Ticket #7 Stufe 1)
  async function erkennen() {
    /*
      Liegt eine Vorbelegung aus dem Outreach-Token vor, ist SIE die bessere Ausgangsfrage
      als der Domain-Stamm: der Token benennt eine in unseren Daten aufgelöste Entität, der
      Stamm ist nur eine aus einer Adresse geschnittene Zeichenkette („mail@kloster-bau.de"
      → „kloster-bau"). Ohne diese Weiche hätte der Stamm die Vorbelegung an genau zwei
      Stellen wieder zunichte gemacht: unten per `setEingabe(frage)`, und davor schon,
      indem die Kandidaten-Suche nach dem falschen Namen fragt.

      Was NICHT passiert: überspringen. Bestätigt wird über dieselben Screens wie sonst.
      Ein Token sagt, wen wir angeschrieben haben — nicht, wer gerade tippt; ein
      weitergeleiteter Link ist der Normalfall, nicht die Ausnahme.
    */
    /*
      WARMER WEG (Sven, 2026-08-17): „ist bei warm die verifizierung notwendig? weil die
      anmeldung vorher erfolgt doch mit der firmenmail?"

      Richtig, und der Grund ist staerker als der Token: die Bestaetigungsfrage war NIE
      eine Verifizierung. Ein Klick auf „Ja, das sind wir" beweist nichts. Bewiesen wird
      ueber die Mailadresse, und das laeuft ohnehin — bei 53,2 % der Firmen liegt dafuer
      etwas vor (Kontaktadresse oder Domain aus den Vergabedaten).

      Also: still pruefen, nicht fragen. Drei Ausgaenge:
        belegt        -> durch, Profil traegt „belegt"
        unbestaetigt  -> AUCH durch, Profil traegt „unbestaetigt" (eine Frage haette die
                         Beweislage nicht geaendert, nur einen Schritt gekostet)
        fremd         -> hier NICHT durchwinken. Wer mit @bechtle.de das Klostermann-
                         Profil oeffnet, ist kein Grenzfall. Zurueck in den kalten Weg.
    */
    let fremdErkannt = false;
    if (tokenFirma) {
      const b = await pruefeBeleg(tokenFirma.id, email, tokenWert);
      setBeleg(b);
      if (b.conf !== "fremd") {
        const m = { id: tokenFirma.id, name: tokenFirma.name } as Match;
        setMatched(m);
        const anzahl = await ladeMitglieder(m);
        // „Gehoeren diese Einheiten zu euch?" ist nur dann eine Frage, wenn es MEHRERE
        // gibt. Bei Klostermann ist es genau eine — der Screen haette einen Klick
        // gekostet und nichts entschieden. Bei CANCOM mit vielen Schwestern ist die
        // Frage echt und bleibt stehen.
        geheZu(anzahl > 1 ? "profil" : "fertig");
        return;
      }
      // Fremde Domain: Vorbelegung faellt weg, es geht den normalen Weg weiter.
      //
      // ⚠ `fremdErkannt` als LOKALE Variable, nicht ueber den Zustand. `setVomToken(false)`
      // wirkt erst beim naechsten Rendern — die Zeile darunter las noch `true` und suchte
      // brav weiter nach der Token-Firma. Ergebnis im Testlauf am 2026-08-17: Adresse
      // `peter@cancom.de`, Urteil „gehoert zu Cancom SE", angezeigt trotzdem
      // H. Klostermann. Der Befund war richtig, die Folge daraus nicht.
      setTokenFirma(null);
      setVomToken(false);
      fremdErkannt = true;
      setEingabe("");          // sonst sucht der Fallback nach dem Token-Firmennamen
    }

    const ausToken = !fremdErkannt && vomToken && eingabe.trim().length > 1;
    setAusDomain(!ausToken);
    const frage = ausToken ? eingabe.trim() : domainStamm(email);
    // Bei fremder Domain ist der Domain-Stamm genau richtig: er fuehrt zu DER Firma,
    // zu der die Adresse gehoert — im Testfall von „cancom.de" also zu Cancom SE.
    if (!frage) { geheZu("firma"); return; }
    setBusy(true);
    const treffer = await suche(frage);
    setBusy(false);
    if (!treffer.length) { setEingabe(frage); geheZu("firma"); return; }
    const beste = treffer[0];
    if (beste.strong && treffer.length <= 3) { setMatched(beste); geheZu("vorschlag"); }
    else { setMatches(treffer); setOffen(treffer[0]?.id ?? null); setKeineDavon(false); geheZu("kandidaten"); }
  }

  async function zumMatch() {
    setAusDomain(false);
    setBusy(true);
    const treffer = await suche(eingabe);
    setBusy(false);
    if (!treffer.length) { geheZu("branche"); return; }
    const beste = treffer[0];
    if (beste.strong) { setMatched(beste); geheZu("vorschlag"); }
    else { setMatches(treffer); setOffen(treffer[0]?.id ?? null); setKeineDavon(false); geheZu("kandidaten"); }
  }

  function toggleMember(key: string) {
    setAktiv((s) => { const n = new Set(s); n.has(key) ? n.delete(key) : n.add(key); return n; });
  }
  function toggleRegion(r: string) {
    setRegionen((rs) => r === "Bundesweit"
      ? (rs.includes(r) ? [] : [r])
      : (rs.includes(r) ? rs.filter((x) => x !== r) : [...rs.filter((x) => x !== "Bundesweit"), r]));
  }

  function fertigstellen() {
    let profile;
    // Was der Check hergibt, bevor die Zweige sich trennen — er gilt in beiden.
    const ausCheck = checkAngaben ? alsProfilfelder(checkAngaben) : null;
    if (matched) {
      const cpvFields = matched.fields.map((f) => f.cpv4);
      profile = {
        ...buildProfile({
          firma: matched.name,
          // „belegt" nur, wenn der serverseitige Abgleich es hergibt — nie als Vorgabe.
          entityConfidence: beleg?.conf === "belegt" ? "belegt" : "unsicher",
          cpvFields, cpvLabels: matched.fields.map((f) => f.label || f.cpv4),
          cpvWins: Object.fromEntries(matched.fields.map((f) => [f.cpv4, f.wins])),
          cpvFields6: (matched.fields6 || []).map((f) => f.cpv6),   // CPV-6-Volltreffer (gewerkscharf)
          regions: matched.regions,
          regionTyp: matched.regionTyp ?? null,   // aus der Zuschlagshistorie abgeleitet
          regionLabels: matched.regions.map((r) => LAENDER.find((l) => l[0] === r)?.[1] || r),
          // Aus dem Eignungs-Check. Nichts davon ist aus Vergabedaten ableitbar — eine
          // Haftpflichtsumme steht in keiner Zuschlagsbekanntmachung.
          ...(ausCheck ?? {}),
        }),
        ...(checkAngaben ? { checkAngaben } : {}),
        // ── PLAUSIBILITÄTSBREMSE, TEIL 2: den BELEG mitspeichern, nicht nur den Anspruch ──
        // ⚠ Bis zum 2026-08-21 wanderten nur die NAMEN ins Profil. Damit war nach dem
        // Speichern nicht mehr unterscheidbar, welcher Teil des Bestands belegt ist und
        // welcher blosse Selbstauskunft — die Oberflaeche kann den Unterschied dann
        // nirgends mehr zeigen. Der Beleg gehoert an den Anspruch, nicht daneben.
        confirmedEntities: members.filter((_, i) => aktiv.has(String(i)))
          .map((m) => ({ name: m.name,
                         beleg: (m.conf === "belegt" ? "kennung" : "selbstauskunft") as
                                "kennung" | "selbstauskunft",
                         wins: m.wins })),
        identityId: matched.id,
      };
    } else {
      const nuts = regionen.filter((r) => r !== "Bundesweit").map(nameToNuts).filter(Boolean) as string[];
      profile = {
        ...buildProfile({
          firma: eingabe.trim() || null, entityConfidence: null,
          cpvFields: [], regions: nuts,
          regionLabels: nuts.map((r) => r === "BUND" ? "Bund" : (LAENDER.find((l) => l[0] === r)?.[1] || r)),
          ...(ausCheck ?? {}),
        }),
        branche: branche || undefined,
        ...(checkAngaben ? { checkAngaben } : {}),
      };
    }
    try { localStorage.setItem(PROFILE_KEY, JSON.stringify(profile)); } catch { /* Quota */ }
    // Verbraucht. Sonst belegt ein zweiter Durchlauf still mit den Zahlen des ersten vor.
    if (checkAngaben) {
      // Die Nachweise gehoeren ins FIRMENPROFIL — nur dort liest `recommendation.js` sie.
      // Ohne Sitzung (Testlauf) faellt das sauber auf `no-session`; die Rohwerte reisen
      // dann am Profil mit und koennen spaeter nachgezogen werden.
      uebernimmCheck(checkAngaben).catch(() => {});
      checkVerwerfen();
    }
    track(EV.ONBOARDING_DONE, { matched: !!matched, entities: matched ? aktiv.size : 0 });
    // Bei aktiver Session zusätzlich nach Supabase (sonst bleibt es lokal, bis bestätigt+angemeldet).
    saveProfile(profile).catch(() => {});
    // ⚠ Zeigte bis zum 2026-08-21 auf „/" — und seit die oeffentliche Startseite dort
    // wohnt (2026-08-20), landete „Leads ansehen" auf der Werbeseite statt in der Liste.
    // Wer angemeldet ist, wird von „/" zwar nach „/leads" geschickt; im Testlauf und in
    // jeder Sekunde, in der die Sitzung noch nicht steht, aber nicht. Also direkt dorthin,
    // was der Knopf verspricht.
    router.push("/leads");
  }

  const cur = stufeVon(screen);
  const winsAktiv = members.filter((_, i) => aktiv.has(String(i))).reduce((a, m) => a + m.wins, 0);
  const unsicher = members.some((m, i) => m.conf === "unsicher" && aktiv.has(String(i)));
  // ── PLAUSIBILITÄTSBREMSE, TEIL 3: das Preisschild ────────────────────────────────
  // Wir halten niemanden auf — wer seine Firmengruppe kennt, weiss es besser als unsere
  // Daten. Aber der Haken bekommt eine Zahl: wie viele Zuschläge hängen gerade an
  // Einheiten, für die es ausser dem Namen keinen Beleg gibt, und welcher Anteil des
  // Profils ist das? Eine Warnung ohne Zahl überliest man; „78 von 98" nicht.
  const winsUnbelegt = members
    .filter((m, i) => aktiv.has(String(i)) && m.conf !== "belegt")
    .reduce((a, m) => a + m.wins, 0);
  const anteilUnbelegt = winsAktiv ? Math.round((winsUnbelegt / winsAktiv) * 100) : 0;

  // EIN Rahmen — derselbe wie in der App. Die Schrittanzeige sitzt in der BEREICHSLEISTE,
  // derselben zweiten Zeile, in der Strategie ihre Abschnitte und Bausteine seine Themen
  // zeigt. Genau dafuer haben wir sie gebaut.
  //
  // Der Ausgang „Spaeter einrichten" ist entfallen: die Rail IST der Ausgang. Eine
  // Sackgasse kann so gar nicht mehr entstehen — das war der eigentliche Fehler, nicht der
  // fehlende Link dagegen.
  // ─── ZWEI WELTEN, EINE SCHWELLE ────────────────────────────────────────────────────
  // Sven: „was ist wenn man startseite → registrierung macht und dann anmeldung in der
  // app?" Genau so. Der Bruch lässt sich nicht vermeiden, nur platzieren — und er gehört
  // dorthin, wo jemand etwas BEKOMMT, nicht dorthin, wo er etwas gibt.
  //
  // Konto und Firma sind noch Besuch: sie laufen auf der Bühne der Startseite (grauer
  // Grund, weisses Blatt, dieselbe Kopfleiste). Ab Profil ist das Konto da, es gibt echte
  // Daten, und die Anwendung klappt auf — mit Rail, Suche und dem Free-Abzeichen, das dann
  // auch etwas bedeutet. Vorher standen beide Schritte in der App-Hülle, also neben einer
  // gesperrten Werkzeugleiste und einer Suche, die ins Leere sucht: die neue Umgebung kam
  // im selben Moment wie die Passwortabfrage, und beides zusammen ist eine Schranke.
  // ⚠ Nicht am Bildschirm festmachen, sondern an der STUFE: zum Schritt „Firma" gehören
  // ausser `firma` auch `vorschlag`, `kandidaten`, `branche` und `region` (s. `stufeVon`).
  // Beim ersten Versuch hing die Bühne an `screen`, und mitten im zweiten Schritt klappte
  // unvermittelt die App-Hülle auf — der Bruch wäre dorthin gerutscht, wo er am wenigsten
  // hingehört: mitten in eine Eingabe.
  const aufBuehne = cur <= 1;

  const schrittleiste = (
          <nav className="steps">
            {/* Der Rückweg steht VOR den Schritten, also dort, wo man ihn sucht, und er ist
                in beiden Welten derselbe, weil beide dieselbe Leiste rendern. Auf dem
                ersten Bildschirm gibt es ihn nicht — dort führt der Knopf „Anmeldung"
                oben rechts hinaus. */}
            {verlauf.length > 0 && (
              <button type="button" className="step-zurueck" onClick={zurueck}>
                <span aria-hidden="true">←</span> {t("Zurück")}
              </button>
            )}
            {SCHRITTE.map(([k, l], i) => (
              <span key={k} style={{ display: "contents" }}>
                {/*
                  WARUM BIN ICH SCHON BEI SCHRITT 3? Genau die Frage hatte Sven beim
                  Durchklicken (2026-08-17): der warme Weg ueberspringt „Firma", die Leiste
                  sagte aber nur „1 2 3 4" und liess offen, was mit Schritt 2 passiert ist.
                  Ein uebersprungener Schritt, der aussieht wie ein ausstehender, ist eine
                  offene Frage im Kopf des Nutzers — und zwar an der Stelle, an der er
                  gerade Vertrauen fassen soll.
                  Er steht deshalb als ERLEDIGT da, mit dem Grund darunter.
                */}
                <span className={`step ${k === "firma" && tokenFirma ? "done"
                                         : i < cur ? "done" : i === cur ? "on" : ""}`}>
                  <i>{(k === "firma" && tokenFirma) || i < cur ? "✓" : i + 1}</i>{t(l)}
                  {k === "firma" && tokenFirma && (
                    <em className="step-grund">{t("über euren Link erkannt")}</em>
                  )}
                </span>
                {i < SCHRITTE.length - 1 ? <span className="step-sep" /> : null}
              </span>
            ))}
          </nav>
  );

  const inhalt = (
    <>
        {/* 0 · Konto */}
        {screen === "mail" && (
          <div className="card">
            {/* Was aus dem Eignungs-Check der Startseite mitkommt. Steht VOR der Überschrift,
                weil es die Frage beantwortet, die hier zuerst auftaucht: wofür lege ich das
                Konto an? Erscheint nur, wenn der Check in dieser Sitzung gelaufen ist. */}
            <CheckMitbringsel />
            <h1>{t("Alle öffentlichen Ausschreibungen.")}<br />{t("Die eine, die zu euch passt.")}</h1>
            <p className="lede">{t("goVisor liest jede öffentliche Vergabe in {laender} und filtert die heraus, auf die ihr euch bewerben solltet. Kostenlos starten, ohne Zahlungsdaten.", { laender: staatenAufzaehlung(t) })}</p>
            <div className="field">
              <label className="lbl" htmlFor="mail">{t("Geschäftliche E-Mail")}</label>
              <input className="inp" id="mail" type="email" value={email} autoComplete="email"
                placeholder={t("name@firma.de")} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <label className="lbl" htmlFor="pw">{t("Passwort")}</label>
              <input className="inp" id="pw" type="password" value={pw} placeholder={t("mindestens 12 Zeichen")} autoComplete="new-password"
                aria-describedby="pw-hinweis"
                onChange={(e) => setPw(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && email.includes("@") && pwOk) kontoAnlegen(); }} />
              <div className="pw-bar" aria-hidden><i data-stufe={pwStatus.stufe} /></div>
              <div className="pw-hint" id="pw-hinweis">
                {pw.length === 0
                  ? t("Länge zählt mehr als Sonderzeichen, eine Passphrase aus vier Wörtern ist sicherer als „P@ssw0rt!“.")
                  : pwStatus.maengel.length
                    ? <>{t("Es fehlt noch:")} {pwStatus.maengel.map((mg) => t(mg)).join(" · ")}</>
                    : pwStatus.stufe === 3 ? t("Stark.") : t("Ausreichend, länger wäre besser.")}
              </div>
            </div>
            {authFehler && <div className="note note-w">{t(authFehler)} {/existiert|angemeldet/.test(authFehler) ? <Link href="/login" style={{ textDecoration: "underline" }}>{t("Zum Login")}</Link> : null}</div>}
            <div className="btnrow">
              {/* Nur ausserhalb der Produktion. Sichtbar und beschriftet, nicht versteckt:
                   ein Schalter, der Konten unterdrueckt, darf niemanden ueberraschen. */}
              {testbetrieb && (
                <label className="probe-schalter">
                  <input type="checkbox" checked={probe} onChange={(e) => setProbe(e.target.checked)} />
                  <span>{t("Testlauf: Ablauf durchspielen, ohne Konto und ohne E-Mail")}</span>
                </label>
              )}
              <button className="btn btn-p" disabled={!email.includes("@") || !pwOk || busy} onClick={kontoAnlegen}>
                {busy ? t("Lege Konto an …") : t("Konto anlegen")}
              </button>
            </div>
            <div className="note note-i">{t("Free-Zugang nach der Anmeldung: Lead-Liste und alle Eckdaten dauerhaft unbegrenzt, drei ausführliche Bewertungen je 30 Tage.")}</div>
          </div>
        )}

        {/* 1 · Firma (getippt) */}
        {screen === "firma" && (
          <div className="card">
            <h1>{t("Wie heißt eure Firma?")}</h1>
            <p className="lede">{ausDomain
              ? (domainStamm(email)
                ? <>{t("Wir haben versucht, eure Firma an der Adresse")} <b>{email}</b> {t("zu erkennen, unter „{stamm}“ finden wir aber kein Unternehmen in den Vergabedaten.", { stamm: domainStamm(email) ?? "" })}</>
                : <>{t("Eure Adresse ist eine Freemail-Adresse, daraus lässt sich keine Firma ableiten.")}</>)
              : t("Damit wir euer Profil bauen können, brauchen wir den Firmennamen.")}</p>
            <div className="field">
              <label className="lbl" htmlFor="q">{t("Firmenname")}</label>
              <div className="inpwrap">
                <input className="inp" id="q" autoComplete="off" autoFocus value={eingabe}
                  placeholder={t("z. B. CANCOM, Bechtle …")}
                  onChange={(e) => { setEingabe(e.target.value); setAcOpen(true); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && eingabe.trim()) { setAcOpen(false); zumMatch(); } }} />
                {acOpen && matches.length > 0 && (
                  <div className="ac" ref={acRef}>
                    {matches.map((m) => (
                      <button key={m.id} className="acopt" onClick={() => { setEingabe(m.name); setAcOpen(false); }}>
                        <span className="ac-n">{m.name}</span><span className="ac-w">{t("{n} Siege", { n: m.wins })}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              {/*
                Hier stand „Zum Ausprobieren: cancom, bechtle, müller" — eine Notiz an uns
                selbst, die jeder Kunde zu sehen bekam. Ein Hinweis unter einem Pflichtfeld
                soll beim Ausfüllen helfen, nicht Testdaten nennen.
              */}
              <span className="hint">{vomToken
                ? t("Aus eurer Übersicht übernommen, ihr könnt den Namen ändern.")
                : t("Am besten der Name, unter dem ihr Aufträge bekommt.")}</span>
            </div>
            {/*
              Hieß „Suchen". Gesucht wird aber schon beim Tippen — die Vorschlagsliste steht
              darüber. Der Knopf tut das, was jeder Knopf in einem vierstufigen Ablauf tut:
              er führt weiter. „Suchen" benannte die Mechanik statt den Schritt und stand
              damit quer zur Fortschrittsanzeige daneben.
            */}
            <div className="btnrow">
              <button className="btn btn-p" disabled={!eingabe.trim() || busy} onClick={() => { setAcOpen(false); zumMatch(); }}>{t("Weiter")}</button>
            </div>
            {/*
              Der Ausweg ist ein ANDERER Weg, kein Abbruch — er überspringt den Schritt.
              Als grauer Text unmittelbar neben dem Hauptknopf las er sich wie eine Fußnote
              zu ihm. Er steht jetzt unter einer Trennlinie und sagt vorher, wofür er da ist.
            */}
            <div className="ausweg">
              <span className="ausweg-f">{t("Ihr findet euch hier nicht?")}</span>
              {/*
                Hieß früher „Wir haben noch nie öffentlich geboten" — eine Behauptung, die
                wir gar nicht prüfen können und die den häufigsten Fall falsch benennt.
                Gemessen 2026-08-16 an `notice_parties`: wir kennen 1.233.126 GEWINNER
                namentlich und keinen einzigen unterlegenen Bieter. Angebote werden nur
                gezählt (259.299 in 51.466 Vergaben), nicht benannt. Wer zehnmal geboten
                und zehnmal verloren hat, ist in unseren Daten also genauso unsichtbar wie
                jemand, der nie angetreten ist.
                Der Knopf sagt jetzt, was wir wirklich wissen: dass wir sie nicht finden.
              */}
              <button className="btn btn-t" onClick={() => geheZu("branche")}>{t("Wir sind noch nicht in eurer Datenbank")}</button>
            </div>
          </div>
        )}

        {/* 2 · Starker Vorschlag */}
        {screen === "vorschlag" && matched && (
          <div className="card">
            <h1>{ausDomain ? t("Moment, arbeitest du bei {firma}?", { firma: matched.name }) : t("Das wissen wir über euch.")}</h1>
            <p className="lede">{ausDomain
              ? <>{t("Eure Adresse endet auf")} <b>{domainStamm(email)}</b> {t("und unter diesem Namen finden wir ein Unternehmen in den öffentlichen Vergabedaten. Falls das ihr seid, wissen wir schon einiges:")}</>
              : t("Aus den öffentlichen Vergabedaten der letzten Jahre.")}</p>
            <div className="suggest">
              <div className="sg-head">
                <div className="sg-name">{matched.name}</div>
                <div className="sg-meta">
                  <span className={`conf conf-${beleg?.conf ?? "unsicher"}`}>
                    {beleg ? (beleg.conf === "belegt" ? t("belegt")
                              : beleg.conf === "fremd" ? t("andere Firma")
                              : t("unbestätigt")) : t("wird geprüft …")}
                  </span>
                  <span>{t(beleg?.grund ?? "gleichen eure Adresse mit den Vergabedaten ab")}</span>
                </div>
              </div>
              <FirmaFakten m={matched} />
            </div>
            {/* Belegt ist eine gute Nachricht — die soll man auch als solche lesen,
                nicht nur als grünes Wörtchen im Kopf. */}
            {beleg?.conf === "belegt" ? (
              <div className="note note-ok">{t("Wir konnten euch zuordnen: {grund}.", { grund: t(beleg.grund) })} {t("Ihr könnt dieses Profil direkt übernehmen.")}</div>
            ) : null}
            {beleg?.conf === "unbestaetigt" ? (
              antragGesendet ? (
                <div className="note note-p">{t("Prüfantrag ist raus. Ihr könnt sofort weiterarbeiten. Wir melden uns, sobald jemand draufgeschaut hat.")}</div>
              ) : (
                <div className="note note-w antrag">
                  <b>{t("Wir können nicht automatisch prüfen, ob ihr zu dieser Firma gehört.")}</b>
                  <span>{t(beleg.grund)}. {t("Ihr könnt trotzdem sofort loslegen, die Zuordnung bleibt so lange")}
                    <b> {t("unbestätigt")}</b>{t(" und ist in eurem Profil so gekennzeichnet.")}</span>
                  {/* Statt einer Sackgasse ein Weg: Kurznachricht, die jemand von Hand prüft.
                      Gemessen betrifft das 5,8 % der Zielgruppe — knapp die Hälfte davon
                      t-online-Adressen, also etablierte Betriebe ohne eigene Mail-Domain. */}
                  <textarea className="inp antrag-t" rows={2} value={antragText}
                    onChange={(e) => setAntragText(e.target.value)}
                    placeholder={t("Kurz zur Prüfung: eure Rolle im Betrieb, gern Handelsregister-Nummer oder Website")} />
                  <button className="btn btn-s" onClick={() => antragSenden(matched)}>{t("Prüfung anfragen")}</button>
                </div>
              )
            ) : null}
            <div className="note note-p">{t("Passend zu diesem Profil bauen wir gleich eure Lead-Liste. Bestätigt die Firma, dann leiten wir das Profil aus euren Vergaben ab.")}</div>
            <div className="btnrow split">
              <button className="btn btn-p" onClick={() => bestaetigen(matched)}>{t("Ja, das sind wir")}</button>
              <button className="btn btn-s" onClick={() => { const l = [matched, ...matches].slice(0, 6); setMatches(l); setOffen(l[0]?.id ?? null); setKeineDavon(false); geheZu("kandidaten"); }}>{t("Nein, andere Firma")}</button>
            </div>
          </div>
        )}

        {/* 3 · Kandidaten (schwacher Match) */}
        {screen === "kandidaten" && (
          <div className="card wide">
            {/* Der Bildschirm entsteht, wenn `zumMatch` keinen starken Treffer hat — das
                kann auch EIN schwacher Treffer sein. „Welche davon seid ihr?" fragt dann
                nach einer Auswahl, die es nicht gibt. Sven am 2026-08-21: „wenn nur eine
                firma vorgeschlagen wird, warum dann die frage ‚welche davon seid ihr?'" */}
            {matches.length === 1 ? (
              <>
                <h1>{t("Seid ihr das?")}</h1>
                <p className="lede">{t("Eine Firma passt zu dem Namen, sicher sind wir uns aber nicht. Prüft, was in den Vergabedaten über sie steht.")}</p>
              </>
            ) : matches.length ? (
              <>
                <h1>{t("Welche davon seid ihr?")}</h1>
                <p className="lede">{t("Der Name allein war nicht eindeutig. Klickt auf eure Firma. Dann zeigen wir direkt hier, was in den Vergabedaten über euch steht.")}</p>
              </>
            ) : (
              <>
                <h1>{t("Kein Treffer für diesen Namen")}</h1>
                <p className="lede">{t("Das heißt nicht, dass ihr nicht dabei seid. Vielleicht schreibt euch die Vergabestelle anders.")}</p>
              </>
            )}
            <div className="cands">
              {matches.length ? matches.map((m) => (
                <div key={m.id} className={`cand-box ${offen === m.id ? "auf" : ""}`}>
                  {/* Aufklappen statt weiterspringen: der Nutzer sieht erst die Belege,
                      dann entscheidet er. Vorher war das ein eigener Screen mit drei Zahlen. */}
                  <button className="cand" aria-expanded={offen === m.id}
                    onClick={() => setOffen((o) => (o === m.id ? null : m.id))}>
                    <div className="cand-m"><span className="cand-n">{m.name}</span>
                      <span className="cand-x">{t("{n} Auftraggeber · aktiv seit {seit}", { n: m.buyers ?? 0, seit: m.seit ?? "—" })}</span></div>
                    <span className="cand-w">{t("{n} Zuschläge", { n: m.wins })}</span>
                    <span className="cand-car">{offen === m.id ? "▴" : "▾"}</span>
                  </button>
                  {offen === m.id ? (
                    <div className="cand-auf">
                      <FirmaFakten m={m} />
                      <button className="btn btn-p" onClick={() => bestaetigen(m)}>{t("Ja, das sind wir")}</button>
                    </div>
                  ) : null}
                </div>
              )) : <div className="note note-i">{t("Kein Treffer. Das ist normal. Nur Unternehmen, die schon eine öffentliche Vergabe gewonnen haben, stehen in unseren Daten.")}</div>}
            </div>

            {/* „Keine davon" öffnet die Eingabe HIER, statt auf einen weiteren fast leeren
                Screen zu springen. */}
            {keineDavon ? (
              <div className="keine-auf">
                <div className="field">
                  <label className="lbl" htmlFor="fname">{t("Wie heißt euer Unternehmen?")}</label>
                  <input className="inp" id="fname" value={eingabe} autoComplete="organization"
                    placeholder={t("Firmenname eingeben")} onChange={(e) => setEingabe(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && eingabe.trim().length > 1) zumMatch(); }} />
                </div>
                <div className="btnrow">
                  <button className="btn btn-p" disabled={eingabe.trim().length < 2 || busy} onClick={zumMatch}>
                    {busy ? t("Suche …") : t("Nochmal suchen")}
                  </button>
                  <button className="btn btn-t" onClick={() => geheZu("branche")}>
                    {t("Wir sind nicht dabei, ohne Vergabehistorie starten")}
                  </button>
                </div>
              </div>
            ) : (
              <div className="btnrow split">
                <button className="btn btn-s" onClick={() => setKeineDavon(true)}>{t("Keine davon")}</button>
              </div>
            )}
          </div>
        )}

        {/* 4 · Gruppe = Identität */}
        {screen === "profil" && matched && (
          <div className="card wide">
            <h1>{t("Gehören diese Einheiten zu euch?")}</h1>
            <p className="lede">{t("Öffentliche Auftraggeber schreiben denselben Konzern unterschiedlich. Wir rechnen Siege aller aktiven Einheiten zusammen, sonst übersehen wir eure eigenen Aufträge.")}</p>
            {members.length ? (
              <div className="ents">
                {members.map((m, i) => (
                  <div key={i} className={`ent ${aktiv.has(String(i)) ? "on" : ""}`}>
                    <button className="ent-box" onClick={() => toggleMember(String(i))}>✓</button>
                    <div className="ent-m">
                      <span className="ent-n">{m.name}</span>
                      <span className={m.conf === "belegt" ? "ent-x" : "ent-x ent-x-schwach"}>
                        {t(m.method)}
                      </span>
                    </div>
                    <span className="ent-w">{m.wins}</span>
                  </div>
                ))}
              </div>
            ) : <div className="spin">{t("Lade Einheiten …")}</div>}
            {aktiv.size === 0 && <div className="note note-w">{t("Mindestens eine Einheit muss aktiv bleiben.")}</div>}
            {unsicher && (
              <div className="note note-w">
                {t("Ihr habt {n} Zuschläge angehakt, für die es ausser dem Namen keinen Beleg gibt: {p} % eures Profils.",
                   { n: winsUnbelegt, p: anteilUnbelegt })}{" "}
                {t("Wir halten euch nicht auf: ihr kennt eure Firmengruppe besser als unsere Daten. Wir merken uns diese Einheiten aber als Selbstauskunft. Was ihr hier anhakt, gilt uns als euer Bestand: diese Zuschläge zählen als eure Historie, und die zugehörigen Ausschreibungen erscheinen euch als eigene, die ihr verteidigen müsst.")}
              </div>
            )}
            <div className="note note-p">{t("Mit der Bestätigung merken wir uns diese Einheiten als eure Identität. Nur so erkennen wir später, dass ihr eine Ausschreibung gewonnen habt.")} <b>{t("{n} Siege", { n: winsAktiv })}</b> {t("fließen in euer Profil.")}</div>
            <div className="btnrow split">
              <button className="btn btn-p" disabled={!aktiv.size} onClick={() => geheZu("fertig")}>{t("Profil bestätigen")}</button>
              <button className="btn btn-t" onClick={() => geheZu("kandidaten")}>{t("Doch eine andere Firma")}</button>
            </div>
          </div>
        )}

        {/* 5 · Branche (manueller Pfad) */}
        {screen === "branche" && (
          <div className="card wide">
            <h1>{t("In welchem Bereich seid ihr unterwegs?")}</h1>
            <p className="lede">{t("Eure Firma taucht in unseren Daten noch nicht als Auftragnehmer auf. Das ist kein Nachteil. Wir starten mit eurem Feld und schärfen das Profil, je mehr ihr goVisor nutzt.")}</p>
            <div className="grid2">
              {BRANCHEN.map((b) => (
                <button key={b.k} className={`pick ${branche === b.k ? "on" : ""}`} onClick={() => setBranche(b.k)}>
                  <div className="pick-m"><span className="pick-n">{t(b.n)}</span><span className="pick-x">{t(b.x)}</span></div>
                </button>
              ))}
            </div>
            <div className="btnrow split">
              <button className="btn btn-p" disabled={!branche} onClick={() => geheZu("region")}>{t("Weiter")}</button>
              <button className="btn btn-t" onClick={zurueck}>{t("Zurück zur Firmensuche")}</button>
            </div>
          </div>
        )}

        {/* 6 · Region */}
        {screen === "region" && (
          <div className="card wide">
            <h1>{t("Wo wollt ihr Aufträge gewinnen?")}</h1>
            <p className="lede">{t("Mehrfachauswahl. Wir filtern nach dem")} <b>{t("Leistungsort")}</b>{t(", nicht nach dem Sitz der Vergabestelle, sonst zeigten wir euch Ausschreibungen in der falschen Gegend.")}</p>
            <div className="chips">
              {REGIONEN.map((r) => (
                <button key={r} className={`chip ${regionen.includes(r) ? "on" : ""}`} onClick={() => toggleRegion(r)}>{t(r)}</button>
              ))}
            </div>
            <div className="note note-i">{t("Bei etwa jeder zehnten Ausschreibung ist der Leistungsort nicht kreisgenau bekannt. Diese zeigen wir trotzdem, aber ohne Regionsfilter, lieber einmal zu viel als einen passenden Auftrag verschweigen.")}</div>
            <div className="btnrow split">
              <button className="btn btn-p" disabled={!regionen.length} onClick={() => geheZu("fertig")}>{t("Fertig")}</button>
              <button className="btn btn-t" onClick={zurueck}>{t("Zurück")}</button>
            </div>
          </div>
        )}

        {/* 7 · Fertig */}
        {screen === "fertig" && (
          <div className="card">
            <div className="done-ring">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
            </div>
            <h1>{t("Alles bereit.")}</h1>
            {/* Das Prüfergebnis SICHTBAR machen. Im warmen Weg lief die Belegprüfung
                still im Hintergrund — für einen Test ist ein unsichtbares Ergebnis
                wertlos, und für einen echten Nutzer ist „wir haben euch über eure
                Firmen-Domain bestätigt" eine gute Nachricht, keine interne Notiz. */}
            {beleg && (
              <div className={`beleg-kasten beleg-${beleg.conf}`}>
                <b>{beleg.conf === "belegt" ? t("Bestätigt")
                    : beleg.conf === "fremd" ? t("Achtung") : t("Nicht bestätigt")}</b>
                <span>{beleg.grund}</span>
              </div>
            )}
            <p className="lede">{matched
              ? t("Wir haben euer Profil aus euren bisherigen Vergaben gebaut.")
              : t("Wir starten mit eurem Bereich und eurer Region, das Profil wächst mit der Nutzung.")}</p>
            <div className="sum">
              {matched ? <>
                <div className="sum-r"><span className="sum-k">{t("Firma")}</span><span className="sum-v">{matched.name}</span></div>
                <div className="sum-r"><span className="sum-k">{t("Einheiten")}</span><span className="sum-v">{t("{n} aktiv", { n: aktiv.size })}</span></div>
                <div className="sum-r"><span className="sum-k">{t("Siege im Profil")}</span><span className="sum-v">{winsAktiv}</span></div>
                <div className="sum-r"><span className="sum-k">{t("Schwerpunkte")}</span><span className="sum-v">{matched.fields.slice(0, 4).map((f) => f.label || f.cpv4).join(" · ")}</span></div>
                {/* ⚠ HAENGT AM BELEG, NICHT AM TREFFER. Bis zum 2026-08-31 stand hier fest
                    „bestätigt ✓", sobald ueberhaupt eine Firma gewaehlt war — waehrend zwei
                    Zeilen darueber der Kasten „Nicht bestätigt" meldete. Zwei Bedeutungen in
                    einem Wort: `matched` heisst „wir haben die Firma GEFUNDEN", der Beleg
                    heisst „wir wissen, dass ihr dazugehoert". Ausgerechnet bei einem Produkt,
                    das mit „was sich nicht belegen laesst, verwerfen wir" wirbt.
                    Dieselbe Quelle wie der Kasten oben, damit sie sich nicht widersprechen
                    koennen. */}
                <div className="sum-r"><span className="sum-k">{t("Identität")}</span><span className="sum-v">{
                  beleg?.conf === "belegt" ? t("bestätigt ✓")
                    : beleg?.conf === "fremd" ? t("widersprüchlich")
                    : t("nicht bestätigt")}</span></div>
              </> : <>
                <div className="sum-r"><span className="sum-k">{t("Bereich")}</span><span className="sum-v">{(() => { const b = BRANCHEN.find((x) => x.k === branche); return b ? t(b.n) : "—"; })()}</span></div>
                <div className="sum-r"><span className="sum-k">{t("Regionen")}</span><span className="sum-v">{regionen.map((r) => t(r)).join(" · ") || "—"}</span></div>
                <div className="sum-r"><span className="sum-k">{t("Identität")}</span><span className="sum-v">{t("noch offen")}</span></div>
              </>}
              {/* ⚠ SICHTBAR, nicht still. Diese Angaben wirken auf jede spaetere
                  Lead-Bewertung; wer sich im Check vertippt hat, muss es hier bemerken
                  koennen. Eine unsichtbare Vorbelegung waere schlechter als gar keine. */}
              {checkAngaben && (
                <div className="sum-r">
                  <span className="sum-k">{t("Aus eurem Check")}</span>
                  <span className="sum-v">{[
                    checkAngaben.volMax ? t("Aufträge bis {n}", { n: eur(checkAngaben.volMax) })
                                        : t("Aufträge ohne Obergrenze"),
                    checkAngaben.haftpflicht ? t("Haftpflicht {n}", { n: eur(checkAngaben.haftpflicht) }) : null,
                    checkAngaben.referenzen != null ? t("{n} Referenzen", { n: checkAngaben.referenzen }) : null,
                    checkAngaben.pq ? "PQ" : null,
                    checkAngaben.iso9001 ? "ISO 9001" : null,
                  ].filter(Boolean).join(" · ")}</span>
                </div>
              )}
              <div className="sum-r"><span className="sum-k">{t("Zugang")}</span><span className="sum-v">{t("Free. Liste und Eckdaten unbegrenzt, 3 Bewertungen je 30 Tage")}</span></div>
            </div>
            {!matched && <div className="note note-i">{t("Sobald ihr eine Vergabe gewinnt, erkennen wir das und fragen, ob wir euer Profil ergänzen dürfen.")}</div>}
            <div className="btnrow">
              <button className="btn btn-p" onClick={fertigstellen}>{t("Leads ansehen")}</button>
            </div>
          </div>
        )}
    </>
  );

  if (aufBuehne) {
    return (
      <main className="lp lp-anmeldung">
        <header className="lp-kopf">
          <Link href="/" aria-label={t("Zur Startseite")}>
            <img className="lp-logo" src="/govisor-wordmark.png" alt="goVisor"
                 width={1004} height={252} />
          </Link>
          <nav className="lp-nav">
            <Link className="lp-knopf lp-knopf-linie" href="/login">{t("Anmeldung")}</Link>
          </nav>
        </header>
        <div className="lp-anmeldung-schritte">{schrittleiste}</div>
        <div className="main seitenmain zugang">{inhalt}</div>
      </main>
    );
  }

  return (
    <div className="app">
      <AppTop />
      <div className="bereichsleiste">{schrittleiste}</div>
      <div className="body">
        <AppRail gesperrt />
        <div className="main seitenmain zugang">{inhalt}</div>
      </div>
    </div>
  );
}
