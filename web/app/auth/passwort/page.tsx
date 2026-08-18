"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { AppRail, AppTop } from "@/components/explorer/Rail";
import "../../explorer.css";
import "../../zugang.css";

/**
 * Neues Passwort setzen, nachdem der Wiederherstellungs-Link eingelöst wurde.
 *
 * Die Seite ist NUR mit gültiger Sitzung sinnvoll: `updateUser` ändert das Passwort des
 * angemeldeten Kontos. Genau deshalb steht sie hinter `/auth/callback` und nicht daneben.
 * Wer sie ohne Sitzung öffnet, bekommt den Weg zurück gezeigt statt eines Formulars, das
 * beim Absenden scheitern müsste.
 *
 * Die Mindestlänge stammt aus der Supabase-Vorgabe (6). Wir prüfen sie hier mit, damit der
 * Fehler beim Tippen erscheint und nicht erst nach dem Absenden vom Server kommt.
 */
const MINDESTLAENGE = 8;

export default function PasswortPage() {
  const router = useRouter();
  const [sitzung, setSitzung] = useState<boolean | null>(null);
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState<string | null>(null);
  const [fertig, setFertig] = useState(false);

  useEffect(() => {
    createClient().auth.getUser().then(({ data }) => setSitzung(!!data.user));
  }, []);

  async function speichern() {
    setBusy(true); setFehler(null);
    const { error } = await createClient().auth.updateUser({ password: pw });
    setBusy(false);
    if (error) { setFehler(error.message); return; }
    setFertig(true);
    setTimeout(() => router.push("/leads"), 1200);
  }

  const zuKurz = pw.length > 0 && pw.length < MINDESTLAENGE;
  const ungleich = pw2.length > 0 && pw !== pw2;

  return (
    <div className="app">
      <AppTop />
      <div className="body">
        <AppRail gesperrt />
        <div className="main seitenmain zugang">
          <div className="card">
            <h1>Neues Passwort</h1>
            {sitzung === false ? (
              <>
                <p className="lede">
                  Dieser Link ist abgelaufen oder wurde schon benutzt. Fordert auf der
                  Anmeldeseite einen neuen an, er gilt eine Stunde.
                </p>
                <div className="btnrow">
                  <button className="btn btn-p" onClick={() => router.push("/login")}>Zur Anmeldung</button>
                </div>
              </>
            ) : fertig ? (
              <p className="lede">Passwort gespeichert. Ihr seid angemeldet, es geht gleich weiter.</p>
            ) : (
              <>
                <p className="lede">Vergebt ein neues Passwort für euer Konto, mindestens {MINDESTLAENGE} Zeichen.</p>
                <div className="field">
                  <label className="lbl" htmlFor="pw">Neues Passwort</label>
                  <input className="inp" id="pw" type="password" value={pw} autoComplete="new-password"
                    onChange={(e) => setPw(e.target.value)} />
                </div>
                <div className="field">
                  <label className="lbl" htmlFor="pw2">Noch einmal</label>
                  <input className="inp" id="pw2" type="password" value={pw2} autoComplete="new-password"
                    onChange={(e) => setPw2(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && pw && pw === pw2 && !zuKurz) speichern(); }} />
                </div>
                {zuKurz && <div className="note note-w">Mindestens {MINDESTLAENGE} Zeichen.</div>}
                {ungleich && <div className="note note-w">Die beiden Eingaben sind nicht gleich.</div>}
                {fehler && <div className="note note-w">{fehler}</div>}
                <div className="btnrow">
                  <button className="btn btn-p" disabled={!pw || pw !== pw2 || zuKurz || busy} onClick={speichern}>
                    {busy ? "Speichere …" : "Passwort speichern"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
