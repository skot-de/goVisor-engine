"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/supabase/auth";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../explorer.css";
import "../zugang.css";

export default function LoginPage() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  async function anmelden() {
    setBusy(true); setFehler(null);
    const { error } = await login(email, pw);
    setBusy(false);
    if (error) { setFehler(error.message === "Invalid login credentials" ? "E-Mail oder Passwort stimmt nicht." : error.message); return; }
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

  // KEINE Schrittanzeige hier: beim Anmelden gibt es keine Schritte. Das ist der einzige
  // erlaubte Unterschied zum Registrieren — alles andere kommt aus dem gemeinsamen Rahmen.
  // EIN Rahmen — derselbe wie in der App. Die Anwendung ist anonym nutzbar (Free-Tier);
  // ein eigener Rahmen VOR ihr unterstellte eine Schranke, die es gar nicht gibt. Und die
  // Rail ist der Ausgang: von hier kommt man jederzeit zurueck in die Leads.
  return (
    <div className="app">
      <AppTop />
      <div className="body">
        <AppRail gesperrt />
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
        </div>
        </div>
      </div>
    </div>
  );
}
