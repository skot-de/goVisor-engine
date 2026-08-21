"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { logout } from "@/lib/supabase/auth";
import { SPRACHEN, sprachName, useSprache } from "@/lib/i18n";
import { useProfil } from "@/lib/useProfil";
import { SeitenSuche } from "./SeitenSuche";

/* Die Hauptnavigation — EINE Quelle für alle Seiten.
 *
 * Vorher stand die Leiste nur in der ExplorerShell; „Unternehmen" und „Bausteine" führten
 * damit auf Seiten OHNE Navigation, also in eine Sackgasse mit Zurück-Link. Eine Leiste,
 * die zwei ihrer sechs Ziele nicht überlebt, ist keine Navigation.
 *
 * Zwei Betriebsarten:
 *  · In der Shell schalten die ersten vier Punkte die Ansicht in-app um (kein Remount,
 *    Zustand bleibt) → `onSwitch` wird gesetzt.
 *  · Auf eigenständigen Seiten gibt es diesen Zustand nicht → dieselben Punkte sind Links.
 */

export type RailId = "akquise" | "merkliste" | "netzwerk" | "strategie" | "unternehmen" | "bausteine";

const ICON: Record<RailId, React.ReactNode> = {
  // FERNGLAS. Die Vorgängerfassung hatte gleich breite Rohre über zwei gleich großen
  // Kreisen — bei 22 px las sie sich als „88", nicht als Fernglas. Nebenan liegen Stern,
  // Netz und Kurve; ein Symbol, das dort wie eine Ziffernfolge wirkt, ist kein Symbol.
  //
  // Was ein Fernglas bei dieser Größe erkennbar macht, sind zwei Dinge, und beide fehlten:
  // die VERJÜNGUNG (breites Objektiv unten, schmales Okular oben) und ein Steg, der bei
  // 1,6 px Strichstärke noch sichtbar ist — deshalb steht er hier ausdrücklich dicker.
  //
  // Geprüft wurde an sechs Entwürfen bei ECHTER Größe in der Leiste, nicht vergrößert:
  // zwei gleich breite Rohre („00") und Rohre mit Okular-Absatz („88") fielen dabei durch.
  // Vergrößert sahen alle sechs brauchbar aus — die Größe, die zählt, ist die kleine.
  akquise: (<>
    <circle cx="6.6" cy="16.4" r="3.4" /><circle cx="17.4" cy="16.4" r="3.4" />
    <path d="M4.6 14.2 6.9 6.1a1.4 1.4 0 0 1 1.3-1h1.1a1.4 1.4 0 0 1 1.4 1.4v7.9" />
    <path d="M19.4 14.2 17.1 6.1a1.4 1.4 0 0 0-1.3-1h-1.1a1.4 1.4 0 0 0-1.4 1.4v7.9" />
    <path d="M10.7 12.4h2.6" strokeWidth="2.4" />
  </>),
  merkliste: <path d="m12 4 2.4 4.9 5.4.8-3.9 3.8.9 5.4-4.8-2.5-4.8 2.5.9-5.4-3.9-3.8 5.4-.8L12 4Z" />,
  netzwerk: (<>
    <circle cx="6" cy="7" r="2.6" /><circle cx="18" cy="7" r="2.6" /><circle cx="12" cy="18" r="2.6" />
    <path d="M7.6 9.1 10.6 15.7M16.4 9.1 13.4 15.7M8.6 7h6.8" />
  </>),
  strategie: (<>
    <path d="M4 4v16h16" /><path d="m7.5 15 3.5-3.6 3 3L20 7" /><path d="M15.8 7H20v4.2" />
  </>),
  unternehmen: (<>
    <path d="M3 21h18M5 21V5a1 1 0 0 1 1-1h7a1 1 0 0 1 1 1v16M14 21V9h4a1 1 0 0 1 1 1v11" />
    <path d="M8 7h2M8 11h2M8 15h2" />
  </>),
  bausteine: (<>
    <rect x="4.5" y="3" width="15" height="18" rx="1.6" /><path d="M8 8h8M8 12h8M8 16h4.5" />
  </>),
};

// Gruppiert nach Aufgabe, nicht nach Technik — drei Paare: täglicher Trichter ·
// Markt verstehen · was wir mitbringen. `sep` markiert den Schnitt NACH dem Eintrag.
// Beschriftung und Zweck kommen aus dem Sprachkatalog (`lib/i18n/messages/*.json`),
// nicht aus dieser Datei — sonst muesste fuer jede weitere Sprache der Code angefasst
// werden. Hier bleibt nur, was sprachunabhaengig ist: Reihenfolge, Ziel, Trennstrich.
const NAV: { id: RailId; href: string; sep?: boolean }[] = [
  { id: "akquise", href: "/leads" },
  { id: "merkliste", href: "/watchlist", sep: true },
  { id: "netzwerk", href: "/network" },
  { id: "strategie", href: "/strategy", sep: true },
  { id: "unternehmen", href: "/unternehmen" },
  { id: "bausteine", href: "/bausteine" },
];

// In-App umschaltbar sind nur die Ansichten der Shell; die anderen zwei sind eigene Routen.
const IN_APP: RailId[] = ["akquise", "merkliste", "netzwerk", "strategie"];

type Plan = "free" | "paid" | "cancelled";

/** Sind die internen Seiten fuer diesen Nutzer erreichbar?
 *
 * Gefragt wird der SERVER, nicht eine Variable im Bundle: die Admin-Adresse gehoert nicht
 * ins ausgelieferte JavaScript. Die Middleware antwortet Nicht-Admins mit 404 — dieses 404
 * ist die Antwort „nein", ohne dass die Oberflaeche je erfaehrt, wer Admin waere.
 */
function useIntern(): boolean {
  const [ja, setJa] = useState(false);
  useEffect(() => {
    let weg = false;
    fetch("/api/wer", { cache: "no-store" })
      .then((r) => r.json())
      .then((d) => { if (!weg) setJa(!!d.admin); })
      .catch(() => { if (!weg) setJa(false); });
    return () => { weg = true; };
  }, []);
  return ja;
}

export function AppRail({
  current, merkN = 0, onSwitch, plan: planProp, userEmail: mailProp, onLogout, gesperrt,
}: {
  /** Fehlt, wenn die Seite kein Rail-Ziel ist (z. B. Einstellungen) — dann leuchtet nichts. */
  current?: RailId;
  merkN?: number;
  /** Nur die Shell kann in-app umschalten. Fehlt der Handler, werden alle Punkte zu Links. */
  onSwitch?: (id: RailId) => void;
  /** Sichtbar, aber nicht anklickbar — fuer Anmelden, Registrieren und Onboarding.
   *
   *  WARUM SICHTBAR STATT WEG: der Rahmen soll derselbe sein, sonst springt beim Wechsel
   *  wieder alles. Und man SIEHT, was einen erwartet, statt vor einer leeren Seite zu
   *  stehen. Nicht klickbar, weil die Bereiche ohne Konto nichts zeigen — ein Link, der
   *  auf eine leere Seite fuehrt, ist schlechter als ein stiller Punkt. */
  gesperrt?: boolean;
  plan?: Plan;
  userEmail?: string | null;
  onLogout?: () => void;
}) {
  const { t } = useSprache();
  const intern = useIntern();
  const [planOpen, setPlanOpen] = useState(false);
  // Die Shell reicht ihren bereits geladenen Kontostand durch; eigenständige Seiten
  // haben keinen — die holen ihn hier selbst, damit das Konto überall erreichbar bleibt.
  const [ownPlan, setOwnPlan] = useState<Plan>("free");
  const [ownMail, setOwnMail] = useState<string | null>(null);
  const [identBestaetigt, setIdentBestaetigt] = useState<boolean | null>(null);
  const eigenstaendig = planProp === undefined;

  useEffect(() => {
    if (!eigenstaendig) return;
    import("@/lib/supabase/account")
      .then(({ loadAccount }) => loadAccount())
      .then((a) => { if (a) { setOwnPlan(a.plan as Plan); setOwnMail(a.email ?? null);
        setIdentBestaetigt(a.entity_confidence === "confirmed"); } })
      .catch(() => { /* nicht angemeldet — Free-Ansicht ist die richtige Antwort */ });
  }, [eigenstaendig]);

  const plan = planProp ?? ownPlan;
  const userEmail = eigenstaendig ? ownMail : mailProp ?? null;

  async function abmelden() {
    if (onLogout) return onLogout();
    await logout().catch(() => {});
    window.location.href = "/leads";
  }

  return (
    <nav className="rail" aria-label="Navigation">
      {NAV.map((n) => {
        const label = t(`nav.${n.id}`);
        const zweck = t(`nav.${n.id}Zweck`);
        const inner = (<>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
            {ICON[n.id]}
          </svg>
          <span className="vb-lbl">{label}<em>{zweck}</em></span>
          {n.id === "merkliste" && merkN ? <span className="railcount">{merkN}</span> : null}
        </>);
        const aktiv = current === n.id ? "true" : undefined;
        // GESPERRT: als `span` rendern, nicht als deaktivierter Knopf. Ein `disabled`
        // Button bleibt ein Bedienelement, das nicht reagiert — der Tastatur-Fokus laeuft
        // hindurch und Vorlesesoftware kuendigt ihn an. Ein `span` mit `aria-disabled`
        // sagt beides ehrlich: da ist etwas, es geht gerade nicht.
        if (gesperrt) {
          const el = (
            <span key={n.id} className="viewbtn railgesperrt" aria-disabled="true"
              title={t("Erst nach der Anmeldung")}>{inner}</span>
          );
          return n.sep ? [el, <span key={n.id + "-sep"} className="railsep" />] : el;
        }
        const btn = onSwitch && IN_APP.includes(n.id) ? (
          <button key={n.id} className="viewbtn" aria-label={label} aria-current={aktiv}
            onClick={() => onSwitch(n.id)}>{inner}</button>
        ) : (
          <Link key={n.id} className="viewbtn raillink" href={n.href} aria-label={label} aria-current={aktiv}>
            {inner}
          </Link>
        );
        return n.sep ? [btn, <span key={n.id + "-sep"} className="railsep" />] : btn;
      })}

      <div className="railfoot">
        {/* Konto-Einstieg: Plan-Status + Einstellungen/Abrechnung/Upgrade an EINER auffindbaren Stelle. */}
        <div className="planwrap">
          <button className={`planbadge ${plan === "paid" ? "is-pro" : ""}`} title="Konto & Zugang"
            onClick={() => setPlanOpen((o) => !o)} aria-expanded={planOpen}>
            <span className="plan-ring" />
            <span className="plan-lbl">{plan === "paid" ? "Pro" : plan === "cancelled" ? "endet" : "Free"}</span>
          </button>
          {planOpen ? (
            <div className="planmenu" role="menu">
              <div className="pm-head">
                <b>{userEmail || "Nicht angemeldet"}</b>
                <span>{plan === "paid" ? "Pro — voller Zugang" : "Free — Lead-Liste unbegrenzt, 3 Bewertungen"}</span>
              </div>
              {/* Die Sperre hing frueher an der Abrechnung. Die Erfolgspraemie ist am
                  2026-08-21 gestrichen worden; was bleibt, ist die Kennzeichnung: bis die
                  Zugehoerigkeit belegt ist, steht die Historie auf Selbstauskunft. */}
              {identBestaetigt === false ? (
                <div className="pm-warn">
                  Firma noch <b>unbestätigt</b>
                  <em>Eure Historie und die Erkennung eigener Aufträge beruhen so lange auf eurer Selbstauskunft.</em>
                </div>
              ) : null}
              {plan !== "paid" ? (
                <Link className="pm-up" href="/settings?sek=zahlung" onClick={() => setPlanOpen(false)}>
                  Auf Pro upgraden
                  <em>Bewertung, Vergabestellen-Dossier &amp; Markt ohne Limit</em>
                </Link>
              ) : null}
              {/* Sprache steht im Konto-Menue, nicht in einer eigenen Ecke: es ist eine
                  Nutzereinstellung wie der Plan, und hier sucht man sie. */}
              <Link className="pm-item" href="/settings" onClick={() => setPlanOpen(false)}>Einstellungen</Link>
              <Link className="pm-item" href="/settings?sek=zahlung" onClick={() => setPlanOpen(false)}>Zahlung &amp; Rechnungen</Link>
              <Link className="pm-item" href="/unternehmen" onClick={() => setPlanOpen(false)}>Unser Unternehmen</Link>
              {/* Interna stehen im KONTO-Menue, nicht in der Rail: die hat sechs Punkte,
                  und jeder weitere kostet Klarheit fuer alle Nutzer. Hier ist auch die
                  ehrlichere Einordnung — es gehoert nicht zum Produkt, sondern zum Betrieb. */}
              {intern ? (
                <Link className="pm-item" href="/intern" onClick={() => setPlanOpen(false)}>
                  Intern · Betrieb
                </Link>
              ) : null}
              {/* Der Profil-Wechsler unter /start gab es laengst — er war nur von keiner
                  Seite aus erreichbar. Eine Funktion, die man ueber die Adresszeile
                  aufrufen muss, ist fuer alle ausser dem Autor nicht vorhanden. */}
              {intern ? (
                <Link className="pm-item" href="/start" onClick={() => setPlanOpen(false)}>
                  Profil wechseln
                </Link>
              ) : null}
              {userEmail
                ? <button className="pm-item pm-out" onClick={() => { setPlanOpen(false); abmelden(); }}>Abmelden</button>
                : <Link className="pm-item" href="/login" onClick={() => setPlanOpen(false)}>Anmelden</Link>}
            </div>
          ) : null}
        </div>
      </div>
    </nav>
  );
}

/* Schlanke Kopfleiste für die eigenständigen Seiten: dieselbe Marke, derselbe Rahmen wie
 * im Explorer. Ohne sie sieht die Seite trotz Rail aus wie ein fremdes Werkzeug. */

/**
 * Der Kopf der eigenstaendigen Seiten — EINE Leiste, ueberall gleich hoch.
 *
 * **Ohne Titel** (2026-08-15): zwei von sechs beschriftete Bereiche sind uneinheitlicher als
 * keiner. Welcher Bereich aktiv ist, sagt das hervorgehobene Symbol links.
 *
 * **Und ohne zweite Leiste** — das ist die Ruecknahme eines eigenen Fehlers vom selben Tag.
 * Um den 45-px-Sprung zwischen den Bereichen zu beseitigen, hatte ich hier eine dauerhafte
 * `.bereichsleiste` eingezogen. Das Problem war echt, der Preis lag an der falschen Stelle:
 * nachgemessen war sie auf `/leads` (dem Hauptbildschirm im Normalzustand) und auf
 * `/intern/lauf` LEER — 45 px leeres Chrom auf fast jedem Schirm.
 *
 * Der Denkfehler dahinter: **ein Sprung, den der Nutzer selbst ausloest, ist lesbar; einer
 * beim Bereichswechsel ist es nicht.** Die Token-Zeile darf also kommen und gehen, wenn
 * gesucht wird — sie erklaert sich durch die Handlung. Was NICHT springen darf, ist der
 * Rahmen beim blossen Umschalten.
 *
 * Deshalb: die Werkzeuge des Bereichs stehen IN dieser Leiste (`werkzeuge`), nicht darunter.
 */
export function AppTop({ suche, werkzeuge, ohneSuche }: {
  /** Eigene Suche der Seite. Fehlt sie, steht die seitenuebergreifende `SeitenSuche`. */
  suche?: React.ReactNode;
  /** Werkzeuge, die NUR zu dieser Seite gehoeren (Filter, Spalten, Export, Reiter). */
  werkzeuge?: React.ReactNode;
  ohneSuche?: boolean;
}) {
  const { t, lang, setLang } = useSprache();
  const profil = useProfil();
  const [sprOffen, setSprOffen] = useState(false);

  // Klick daneben schliesst das Sprachmenue. Das lag frueher in `closeAllPops` der Shell —
  // ein Menue, dessen Schliess-Logik in einer FREMDEN Komponente wohnt, funktioniert genau
  // so lange, wie es dort gerendert wird. Jetzt bringt es sie selbst mit.
  useEffect(() => {
    if (!sprOffen) return;
    function daneben(e: MouseEvent) {
      if (!(e.target as HTMLElement).closest(".sprachcell")) setSprOffen(false);
    }
    document.addEventListener("mousedown", daneben);
    return () => document.removeEventListener("mousedown", daneben);
  }, [sprOffen]);

  return (
    <header className="topbar topbar-schlank">
      <div className="brandcell">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/govisor-wordmark.png" alt="goVisor" className="brandlogo" />
      </div>

      {/* GRUNDAUFBAU UEBERALL GLEICH: Logo · Profil · Suche · (Werkzeuge) · Sprache.
          Profil und Sprache stehen FEST, weil sie zu jeder Seite gehoeren — wer auf
          „Unternehmen" ist, sucht sein Profil eher dort als in der Lead-Liste. Bis
          2026-08-16 gab es beide nur im Explorer, weil ihr Zustand zufaellig in dessen
          Komponente lag; das war keine Entscheidung, sondern eine Nebenwirkung. */}
      <Link className={`colbtn profilbtn ${profil ? "colbtn-on" : ""}`} href="/onboarding"
        title={profil
          ? t("{firma}, ansehen/bearbeiten", { firma: profil.firma || t("Profil") })
          : t("Profil einrichten, schaltet echte Relevanz frei")}>
        <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor"
          strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 12a4 4 0 100-8 4 4 0 000 8ZM4 21a8 8 0 0116 0" />
        </svg>
        <span className="pb-name">
          {profil ? (profil.firma || t("Profil")) : t("Profil einrichten")}
        </span>
      </Link>

      {ohneSuche ? null : (suche ?? <SeitenSuche />)}
      {werkzeuge ? <div className="top-werkzeuge">{werkzeuge}</div> : null}

      {/* Sprache ganz rechts, auf JEDER Seite. Sie betrifft die Anzeige, nicht das Konto —
          deshalb hier und nicht im Konto-Menue der Rail. */}
      <div className="colcfg sprachcell">
        <button className="colbtn" type="button" aria-haspopup="menu" aria-expanded={sprOffen}
          onClick={() => setSprOffen((o) => !o)} title={t("sprache.app")}>
          <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" strokeWidth={2}>
            <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18" />
          </svg>
          {lang.toUpperCase()}
        </button>
        <div className="colmenu" data-open={sprOffen ? "" : undefined} role="menu">
          {SPRACHEN.map((sp) => (
            <div key={sp} className="ci" role="menuitemradio" aria-checked={sp === lang}
              data-on={sp === lang ? "" : undefined}
              onClick={() => { setLang(sp); setSprOffen(false); }}>
              <span className="box" />
              <span>{sprachName(sp, t)}</span>
            </div>
          ))}
        </div>
      </div>
    </header>
  );
}
