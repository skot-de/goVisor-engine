"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { login, magicLink, passwortVergessen } from "@/lib/supabase/auth";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../explorer.css";
import "../zugang.css";

/* Supabase antwortet auf Englisch, und zwar mit Saetzen, die der Nutzer nicht einordnen
 * kann („Email link is invalid or has expired" — und nun?). Uebersetzt wird nur, was
 * tatsaechlich vorkommt; alles Unbekannte geht unveraendert durch, damit ein neuer Fehler
 * sichtbar bleibt statt hinter einem freundlichen Platzhalter zu verschwinden. */
const AUF_DEUTSCH: [RegExp, string][] = [
  [/invalid login credentials/i, "E-Mail oder Passwort stimmt nicht."],
  [/(link|token).*(invalid|expired)/i,
   "Der Link ist abgelaufen oder wurde schon benutzt. Fordert unten einen neuen an, er gilt eine Stunde."],
  [/only request this after (\d+) seconds/i,
   "Zu viele Versuche. Wartet einen Moment und probiert es noch einmal."],
  [/email not confirmed/i, "Die Adresse ist noch nicht bestätigt. Schaut in eure Mails."],
  [/user not found/i, "Zu dieser Adresse gibt es kein Konto."],
];
function deutsch(m: string | null): string | null {
  if (!m) return m;
  for (const [muster, text] of AUF_DEUTSCH) if (muster.test(m)) return text;
  return m;
}

/* ⚠ WARUM DIESE SEITE ZWEIGETEILT IST.
 * `useSearchParams()` zwingt Next zum Rendern auf dem Client. Ohne eine `<Suspense>`-Grenze
 * darum bricht `next build` ab — und zwar NUR dort: `next dev` bleibt grün, die laufende
 * Seite auch. Genau deshalb ist es vom 18.08. bis zum 01.09.2026 unbemerkt geblieben; ein
 * frisches Deployment wäre in dieser Zeit gescheitert.
 *
 * Die Grenze umschliesst absichtlich nur das Formular, nicht die Hülle: Kopfzeile und Rail
 * werden vorab gerendert und stehen sofort. Ein `fallback={null}` hätte die Seite beim
 * Aufbau leer blitzen lassen — die Rail ist hier der einzige Ausgang zurück in die Leads. */
export default function LoginPage() {
  return (
    <div className="app">
      <AppTop />
      <div className="body">
        <AppRail gesperrt />
        <Suspense fallback={<div className="main seitenmain zugang" />}>
          <LoginFormular />
        </Suspense>
      </div>
    </div>
  );
}

function LoginFormular() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  // Der Fehler aus `/auth/callback` kommt als Query an: ein abgelaufener Link ist der
  // Normalfall (Supabase-Vorgabe: eine Stunde), und er gehoert dorthin gezeigt, wo man den
  // naechsten anfordert. Sonst steht der Nutzer wieder vor demselben leeren Formular.
  const [fehler, setFehler] = useState<string | null>(deutsch(params.get("fehler")));
  const [gesendet, setGesendet] = useState<string | null>(null);

  async function anmelden() {
    setBusy(true); setFehler(null);
    const { error } = await login(email, pw);
    setBusy(false);
    if (error) { setFehler(deutsch(error.message)); return; }
    // WOHIN NACH DEM ANMELDEN — drei Faelle, in dieser Reihenfolge:
    //
    // 1. `weiter`: der Nutzer wollte irgendwohin und wurde vom Tor abgefangen. Ihn
    //    stattdessen auf die Startseite zu setzen, waere ein zweiter Umweg.
    // 2. KEIN PROFIL → Onboarding. Die ganze Anwendung beruht darauf, GEZIELTE
    //    Ausschreibungen zu zeigen; ohne Profil ist die Liste eine ungefilterte
    //    Aufzaehlung, wie sie jedes kostenlose Portal auch hat. (Ich hatte hier zuerst
    //    „immer in den Explorer" gebaut und mit Bewegungsfreiheit begruendet — das war
    //    ein Argument ueber den Ablauf, nicht ueber den Zweck des Produkts.)
    // 3. sonst in die Leads.
    const ziel = params.get("weiter");
    let hatProfil = false;
    try { hatProfil = !!localStorage.getItem("govisor.profile.v1"); } catch { /* egal */ }
    router.push(ziel && ziel.startsWith("/") ? ziel : (hatProfil ? "/leads" : "/onboarding"));
  }

  /* OHNE PASSWORT HINEIN — und warum das keine Bequemlichkeit ist.
   *
   * Bis 2026-08-18 kannte die Anmeldung ausschliesslich E-Mail plus Passwort. Wer keines
   * hatte, kam nicht mehr in sein Konto: es gab weder Wiederherstellung noch Magic Link,
   * und die Mails, die Supabase auf Zuruf verschickt, landeten auf einer Adresse ohne
   * Rueckkehr-Route. Sven ist an genau dieser Stelle haengengeblieben, an seinem eigenen Konto.
   *
   * Beide Wege schicken bewusst DIESELBE Rueckmeldung, egal ob die Adresse existiert. Wer
   * hier „kein Konto mit dieser Adresse" laese, koennte unsere Kundenliste abfragen.
   */
  async function ohnePasswort(art: "link" | "neu") {
    setBusy(true); setFehler(null); setGesendet(null);
    const { error } = art === "link" ? await magicLink(email) : await passwortVergessen(email);
    setBusy(false);
    if (error) { setFehler(deutsch(error.message)); return; }
    setGesendet(art === "link"
      ? "Wir haben euch einen Anmeldelink geschickt. Er gilt eine Stunde."
      : "Wenn es zu dieser Adresse ein Konto gibt, ist die Mail unterwegs. Der Link gilt eine Stunde.");
  }

  // KEINE Schrittanzeige hier: beim Anmelden gibt es keine Schritte. Das ist der einzige
  // erlaubte Unterschied zum Registrieren — alles andere kommt aus dem gemeinsamen Rahmen.
  // EIN Rahmen — derselbe wie in der App. Die Anwendung ist anonym nutzbar (Free-Tier);
  // ein eigener Rahmen VOR ihr unterstellte eine Schranke, die es gar nicht gibt. Und die
  // Rail ist der Ausgang: von hier kommt man jederzeit zurueck in die Leads.
  return (
        <div className="main seitenmain zugang">
        <div className="card">
          <h1>Willkommen zurück.</h1>
          <p className="lede">Meldet euch an, um eure Merkliste, euer Profil und eure Bewertungen wiederzusehen.</p>
          <div className="field">
            <label className="lbl" htmlFor="mail">E-Mail</label>
            <input className="inp" id="mail" type="email" value={email} autoComplete="email"
              placeholder="name@firma.de" onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") document.getElementById("pw")?.focus(); }} />
          </div>
          <div className="field">
            <label className="lbl" htmlFor="pw">Passwort</label>
            <input className="inp" id="pw" type="password" value={pw} autoComplete="current-password"
              placeholder="Passwort" onChange={(e) => setPw(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && email && pw) anmelden(); }} />
          </div>
          {fehler && <div className="note note-w">{fehler}</div>}
          <div className="btnrow">
            <button className="btn btn-p" disabled={!email || !pw || busy} onClick={anmelden}>
              {busy ? "Melde an …" : "Anmelden"}
            </button>
            <Link className="btn btn-t" href="/onboarding">Noch kein Konto? Kostenlos starten</Link>
          </div>
          {gesendet && <div className="note">{gesendet}</div>}
          {/* Beide brauchen nur die Adresse, nicht das Passwortfeld — deshalb haengen sie
              an `email` und nicht an der Freigabe des Anmelde-Knopfes. */}
          <div className="btnrow zugang-alt">
            <button className="btn btn-t" disabled={!email || busy} onClick={() => ohnePasswort("link")}>
              Anmeldelink per Mail
            </button>
            <button className="btn btn-t" disabled={!email || busy} onClick={() => ohnePasswort("neu")}>
              Passwort vergessen
            </button>
          </div>
        </div>
        </div>
  );
}
