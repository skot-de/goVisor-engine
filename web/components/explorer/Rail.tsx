"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { logout } from "@/lib/supabase/auth";

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
  akquise: (<>
    <circle cx="7" cy="15.6" r="3.6" /><circle cx="17" cy="15.6" r="3.6" />
    <path d="M4.5 13.2V6.2A2.2 2.2 0 0 1 6.7 4h.9a2.2 2.2 0 0 1 2.2 2.2v7" />
    <path d="M19.5 13.2V6.2A2.2 2.2 0 0 0 17.3 4h-.9a2.2 2.2 0 0 0-2.2 2.2v7" />
    <path d="M9.8 9.4h4.4" />
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
const NAV: { id: RailId; label: string; zweck: string; href: string; sep?: boolean }[] = [
  { id: "akquise", label: "Akquise", zweck: "worauf ihr euch jetzt bewerben könnt", href: "/leads" },
  { id: "merkliste", label: "Merkliste", zweck: "was ihr verfolgt — Termine und Stand", href: "/watchlist", sep: true },
  { id: "netzwerk", label: "Netzwerk", zweck: "wo ihr Verbindungen in den Markt habt", href: "/network" },
  { id: "strategie", label: "Strategie", zweck: "wohin sich euer Markt bewegt", href: "/strategy", sep: true },
  { id: "unternehmen", label: "Unternehmen", zweck: "euer Profil, eure Bilanz, eure Chancen", href: "/unternehmen" },
  { id: "bausteine", label: "Bausteine", zweck: "eure Textbausteine fürs Angebot", href: "/bausteine" },
];

// In-App umschaltbar sind nur die Ansichten der Shell; die anderen zwei sind eigene Routen.
const IN_APP: RailId[] = ["akquise", "merkliste", "netzwerk", "strategie"];

type Plan = "free" | "paid" | "cancelled";

export function AppRail({
  current, merkN = 0, onSwitch, plan: planProp, userEmail: mailProp, onLogout,
}: {
  /** Fehlt, wenn die Seite kein Rail-Ziel ist (z. B. Einstellungen) — dann leuchtet nichts. */
  current?: RailId;
  merkN?: number;
  /** Nur die Shell kann in-app umschalten. Fehlt der Handler, werden alle Punkte zu Links. */
  onSwitch?: (id: RailId) => void;
  plan?: Plan;
  userEmail?: string | null;
  onLogout?: () => void;
}) {
  const [planOpen, setPlanOpen] = useState(false);
  // Die Shell reicht ihren bereits geladenen Kontostand durch; eigenständige Seiten
  // haben keinen — die holen ihn hier selbst, damit das Konto überall erreichbar bleibt.
  const [ownPlan, setOwnPlan] = useState<Plan>("free");
  const [ownMail, setOwnMail] = useState<string | null>(null);
  const eigenstaendig = planProp === undefined;

  useEffect(() => {
    if (!eigenstaendig) return;
    import("@/lib/supabase/account")
      .then(({ loadAccount }) => loadAccount())
      .then((a) => { if (a) { setOwnPlan(a.plan as Plan); setOwnMail(a.email ?? null); } })
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
        const inner = (<>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round">
            {ICON[n.id]}
          </svg>
          <span className="vb-lbl">{n.label}<em>{n.zweck}</em></span>
          {n.id === "merkliste" && merkN ? <span className="railcount">{merkN}</span> : null}
        </>);
        const aktiv = current === n.id ? "true" : undefined;
        const btn = onSwitch && IN_APP.includes(n.id) ? (
          <button key={n.id} className="viewbtn" aria-label={n.label} aria-current={aktiv}
            onClick={() => onSwitch(n.id)}>{inner}</button>
        ) : (
          <Link key={n.id} className="viewbtn raillink" href={n.href} aria-label={n.label} aria-current={aktiv}>
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
              {plan !== "paid" ? (
                <Link className="pm-up" href="/settings?sek=zahlung" onClick={() => setPlanOpen(false)}>
                  Auf Pro upgraden
                  <em>Bewertung, Vergabestellen-Dossier &amp; Markt ohne Limit</em>
                </Link>
              ) : null}
              <Link className="pm-item" href="/settings" onClick={() => setPlanOpen(false)}>Einstellungen</Link>
              <Link className="pm-item" href="/settings?sek=zahlung" onClick={() => setPlanOpen(false)}>Zahlung &amp; Rechnungen</Link>
              <Link className="pm-item" href="/unternehmen" onClick={() => setPlanOpen(false)}>Unser Unternehmen</Link>
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
export function AppTop({ titel }: { titel: string }) {
  return (
    <header className="topbar topbar-schlank">
      <div className="brandcell">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/govisor-wordmark.png" alt="goVisor" className="brandlogo" />
      </div>
      <span className="top-titel">{titel}</span>
    </header>
  );
}
