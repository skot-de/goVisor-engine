"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { login } from "@/lib/supabase/auth";
import { EinstiegShell } from "@/components/EinstiegShell";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);

  async function anmelden() {
    setBusy(true); setFehler(null);
    const { error } = await login(email, pw);
    setBusy(false);
    if (error) { setFehler(error.message === "Invalid login credentials" ? "E-Mail oder Passwort stimmt nicht." : error.message); return; }
    router.push("/leads");   // Explorer, nicht Onboarding — s. Kommentar oben
  }

  // KEINE Schrittanzeige hier: beim Anmelden gibt es keine Schritte. Das ist der einzige
  // erlaubte Unterschied zum Registrieren — alles andere kommt aus dem gemeinsamen Rahmen.
  return (
    <EinstiegShell titel="Anmelden">
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
    </EinstiegShell>
  );
}
