"use client";
/**
 * Der Rahmen VOR der App — Anmelden, Registrieren, Profilwechsel.
 *
 * **Warum es ihn gibt.** Bis 2026-08-16 gab es vier verschiedene Rahmen, bis man in der App
 * war: `/login` (eigener Kopf, geliehenes Stylesheet), `/onboarding` (eigener Kopf, eigenes
 * Stylesheet), `/start` (**gar kein Kopf**) und die App selbst. Das Ergebnis fühlte sich
 * lose an — zu Recht, denn es war nicht uneinheitlich gestaltet, sondern mehrfach gebaut.
 *
 * Jetzt gibt es genau zwei Rahmen im Produkt: **diesen hier** vor der Anmeldung und
 * `AppTop`/`AppRail` darin. Was ein Rahmen ist, erkennt man daran, dass er sich nicht je
 * Seite unterscheidet — sonst ist er Dekoration.
 *
 * **Die Schrittanzeige ist der einzige erlaubte Unterschied.** Beim Registrieren ist sie
 * richtig (man will wissen, wie viel noch kommt), beim Anmelden falsch (es gibt keine
 * Schritte). Deshalb ist sie ein Steckplatz und keine feste Zeile.
 */
import Link from "next/link";
import "../app/einstieg.css";

export function EinstiegShell({ titel, schritte, aktion, children }: {
  /** Kurzwort neben dem Logo: „Anmelden", „Onboarding", „Profil wechseln". */
  titel: string;
  /** Schrittanzeige — nur wo es Schritte GIBT. */
  schritte?: React.ReactNode;
  /** Optionaler Ausgang rechts. Eine Seite ohne Rückweg liest sich als Sackgasse; genau
   *  das war das Onboarding, bis wir es bemerkt haben. */
  aktion?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="einstieg">
      <header className="top">
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <Link href="/" className="brand" style={{ textDecoration: "none", color: "inherit" }}>
            go<span>V</span>isor
          </Link>
          <span className="ver">{titel}</span>
        </div>
        {schritte ?? null}
        {aktion ?? null}
      </header>
      <main className="stage">{children}</main>
    </div>
  );
}

export default EinstiegShell;
