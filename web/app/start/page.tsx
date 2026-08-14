"use client";
/**
 * Startpunkt hinter dem Vorhang.
 *
 * Der Vorhang-Pfad (`ZUGANG_PFAD`, s. `middleware.ts`) führt auf `/login`; von dort landet man
 * hier. Diese Seite ist die Weiche: anmelden, registrieren, direkt in die App — oder mit einer
 * bestimmten Kundensicht hinein.
 *
 * Warum eine eigene Seite und nicht ein Menü in der App: solange nur getestet und vorgeführt
 * wird, ist die erste Frage nicht „was will ich tun", sondern „als wer schaue ich". Diese Frage
 * beantwortet man einmal am Anfang, nicht mitten im Klickpfad.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { currentUser, logout } from "@/lib/supabase/auth";
import {
  TESTPROFILE, PROFIL_COOKIE, darfSchreiben, type Testprofil,
} from "@/lib/testprofile";

function setzeProfilCookie(id: string | null) {
  // Kein httpOnly: die Oberfläche muss das gewählte Profil selbst lesen können. Es ist eine
  // Anzeige-Einstellung, kein Geheimnis — die Berechtigung hängt an der Supabase-Session.
  const basis = `path=/; SameSite=Lax; max-age=${60 * 60 * 12}`;
  document.cookie = id ? `${PROFIL_COOKIE}=${id}; ${basis}` : `${PROFIL_COOKIE}=; path=/; max-age=0`;
}

export default function StartSeite() {
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);
  const [laedt, setLaedt] = useState(true);

  useEffect(() => {
    currentUser()
      .then((u) => setEmail(u?.email ?? null))
      .finally(() => setLaedt(false));
  }, []);

  function starte(profil: Testprofil | null) {
    setzeProfilCookie(profil?.id ?? null);
    router.push("/");
  }

  if (laedt) return <main className="startseite"><p>…</p></main>;

  return (
    <main className="startseite">
      <h1>goVisor</h1>
      <p className="start-status">
        {email ? <>Angemeldet als <strong>{email}</strong></> : "Nicht angemeldet"}
      </p>

      {!email && (
        <section className="start-block">
          <h2>Zugang</h2>
          <div className="start-knopfreihe">
            <button onClick={() => router.push("/login")}>Anmelden</button>
            <button onClick={() => router.push("/login?modus=registrieren")}>Registrieren</button>
          </div>
        </section>
      )}

      {email && (
        <>
          <section className="start-block">
            <h2>Direkt in die App</h2>
            <p className="start-hinweis">Mit dem eigenen Konto und dem eigenen Profil.</p>
            <button onClick={() => starte(null)}>App öffnen</button>
          </section>

          <section className="start-block">
            <h2>Mit einer Kundensicht</h2>
            {/* Die beiden Arten stehen bewusst getrennt und beschriftet. „Vorführung" und
                „Test" sehen in der App fast gleich aus — der Unterschied (Schreibschutz) muss
                deshalb HIER klar sein, wo man wählt, nicht erst wenn etwas schiefgeht. */}
            <p className="start-hinweis">
              <strong>Test</strong> hat volle Rechte — zum Durchklicken und Zustände erzeugen.{" "}
              <strong>Vorführung</strong> kann nur lesen; damit lässt sich vor Publikum nichts
              versehentlich verändern.
            </p>
            <ul className="start-profile">
              {TESTPROFILE.map((p) => (
                <li key={p.id} className={`start-profil start-profil--${p.art}`}>
                  <button onClick={() => starte(p)}>
                    <span className="start-profil-name">{p.name}</span>
                    <span className="start-profil-art">
                      {darfSchreiben(p) ? "volle Rechte" : "nur lesen"}
                    </span>
                    <span className="start-profil-text">{p.beschreibung}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="start-block">
            <button
              className="start-abmelden"
              onClick={async () => { setzeProfilCookie(null); await logout(); router.refresh(); }}
            >
              Abmelden
            </button>
          </section>
        </>
      )}
    </main>
  );
}
