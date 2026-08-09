"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { buildProfile } from "@/lib/profileEngine";
import { LAENDER } from "@/components/explorer/FilterPanel";
import { register, saveProfile, currentUser } from "@/lib/supabase/auth";
import { track, EV } from "@/lib/analytics";
import Link from "next/link";
import "./onboarding.css";

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
const norm = (s: string) => s.toLowerCase().replace(/[^a-zäöüß0-9]/g, "");

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

export default function OnboardingPage() {
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

  const acRef = useRef<HTMLDivElement>(null);

  // Schon eingeloggt (z. B. „Profil bearbeiten")? → Konto-/Registrierungs-Screen überspringen.
  useEffect(() => {
    currentUser().then((u) => { if (u) { setEmail(u.email ?? ""); setScreen("firma"); } }).catch(() => {});
  }, []);

  // Autocomplete auf der Firma-Seite (debounced)
  useEffect(() => {
    if (screen !== "firma" || eingabe.trim().length < 2) { setMatches([]); return; }
    const t = setTimeout(async () => setMatches(await suche(eingabe)), 220);
    return () => clearTimeout(t);
  }, [eingabe, screen]);

  const ladeMitglieder = useCallback(async (m: Match) => {
    try {
      const d = await fetch(`/api/entity-group?id=${encodeURIComponent(m.id)}`).then((r) => r.json());
      const ms: Member[] = d.members || [];
      setMembers(ms);
      // Nach Index keyen — gleichnamige Schwester-Entities (mehrere „CANCOM Public GmbH") kollabieren sonst.
      setAktiv(new Set(ms.map((_, i) => String(i))));
    } catch { setMembers([]); setAktiv(new Set()); }
  }, []);

  async function bestaetigen(m: Match) {
    setMatched(m);
    await ladeMitglieder(m);
    setScreen("profil");
  }

  // Konto anlegen (Registrierung), dann Firmen-Erkennung. Bei „E-Mail existiert" → Login anbieten.
  async function kontoAnlegen() {
    setAuthFehler(null); setBusy(true);
    const { error } = await register(email, pw);
    setBusy(false);
    if (error && !/already registered|already exists/i.test(error.message)) { setAuthFehler(error.message); return; }
    if (error) { setAuthFehler("Diese E-Mail hat schon ein Konto — bitte anmelden."); return; }
    await erkennen();   // signUp ok (mit oder ohne sofortige Session) → weiter im Flow
  }

  // E-Mail → Domain-Stamm ableiten und matchen (Ticket #7 Stufe 1)
  async function erkennen() {
    setAusDomain(true);
    const stamm = domainStamm(email);
    if (!stamm) { setScreen("firma"); return; }
    setBusy(true);
    const treffer = await suche(stamm);
    setBusy(false);
    if (!treffer.length) { setEingabe(stamm); setScreen("firma"); return; }
    const beste = treffer[0];
    if (beste.strong && treffer.length <= 3) { setMatched(beste); setScreen("vorschlag"); }
    else { setMatches(treffer); setScreen("kandidaten"); }
  }

  async function zumMatch() {
    setAusDomain(false);
    setBusy(true);
    const treffer = await suche(eingabe);
    setBusy(false);
    if (!treffer.length) { setScreen("branche"); return; }
    const beste = treffer[0];
    if (beste.strong) { setMatched(beste); setScreen("vorschlag"); }
    else { setMatches(treffer); setScreen("kandidaten"); }
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
    if (matched) {
      const cpvFields = matched.fields.map((f) => f.cpv4);
      profile = {
        ...buildProfile({
          firma: matched.name, entityConfidence: "confirmed",
          cpvFields, cpvLabels: matched.fields.map((f) => f.label || f.cpv4),
          cpvWins: Object.fromEntries(matched.fields.map((f) => [f.cpv4, f.wins])),
          cpvFields6: (matched.fields6 || []).map((f) => f.cpv6),   // CPV-6-Volltreffer (gewerkscharf)
          regions: matched.regions,
          regionTyp: matched.regionTyp ?? null,   // aus der Zuschlagshistorie abgeleitet
          regionLabels: matched.regions.map((r) => LAENDER.find((l) => l[0] === r)?.[1] || r),
        }),
        confirmedEntities: members.filter((_, i) => aktiv.has(String(i))).map((m) => m.name),
        identityId: matched.id,
      };
    } else {
      const nuts = regionen.filter((r) => r !== "Bundesweit").map(nameToNuts).filter(Boolean) as string[];
      profile = {
        ...buildProfile({
          firma: eingabe.trim() || null, entityConfidence: null,
          cpvFields: [], regions: nuts,
          regionLabels: nuts.map((r) => r === "BUND" ? "Bund" : (LAENDER.find((l) => l[0] === r)?.[1] || r)),
        }),
        branche: branche || undefined,
      };
    }
    try { localStorage.setItem(PROFILE_KEY, JSON.stringify(profile)); } catch { /* Quota */ }
    track(EV.ONBOARDING_DONE, { matched: !!matched, entities: matched ? aktiv.size : 0 });
    // Bei aktiver Session zusätzlich nach Supabase (sonst bleibt es lokal, bis bestätigt+angemeldet).
    saveProfile(profile).catch(() => {});
    router.push("/");
  }

  const cur = stufeVon(screen);
  const winsAktiv = members.filter((_, i) => aktiv.has(String(i))).reduce((a, m) => a + m.wins, 0);
  const unsicher = members.some((m, i) => m.conf === "unsicher" && aktiv.has(String(i)));

  return (
    <div className="ob-page">
      <header className="top">
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span className="brand">go<span>V</span>isor</span><span className="ver">Onboarding</span>
        </div>
        <nav className="steps">
          {SCHRITTE.map(([k, l], i) => (
            <span key={k} style={{ display: "contents" }}>
              <span className={`step ${i < cur ? "done" : i === cur ? "on" : ""}`}>
                <i>{i < cur ? "✓" : i + 1}</i>{l}
              </span>
              {i < SCHRITTE.length - 1 ? <span className="step-sep" /> : null}
            </span>
          ))}
        </nav>
      </header>

      <main className="stage">
        {/* 0 · Konto */}
        {screen === "mail" && (
          <div className="card">
            <h1>Alle öffentlichen Ausschreibungen.<br />Die eine, die zu euch passt.</h1>
            <p className="lede">goVisor liest jede öffentliche Vergabe in Deutschland und filtert die heraus,
              auf die ihr euch bewerben solltet. Kostenlos starten, ohne Zahlungsdaten.</p>
            <div className="field">
              <label className="lbl" htmlFor="mail">Geschäftliche E-Mail</label>
              <input className="inp" id="mail" type="email" value={email} autoComplete="email"
                placeholder="name@firma.de" onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <label className="lbl" htmlFor="pw">Passwort</label>
              <input className="inp" id="pw" type="password" value={pw} placeholder="mindestens 8 Zeichen" autoComplete="new-password"
                onChange={(e) => setPw(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && email.includes("@") && pw.length >= 8) kontoAnlegen(); }} />
            </div>
            {authFehler && <div className="note note-w">{authFehler} {/existiert|angemeldet/.test(authFehler) ? <Link href="/login" style={{ textDecoration: "underline" }}>Zum Login</Link> : null}</div>}
            <div className="btnrow">
              <button className="btn btn-p" disabled={!email.includes("@") || pw.length < 8 || busy} onClick={kontoAnlegen}>
                {busy ? "Lege Konto an …" : "Konto anlegen"}
              </button>
              <Link className="btn btn-t" href="/login">Ich habe schon ein Konto</Link>
            </div>
            <div className="note note-i">Free-Zugang: Lead-Liste und alle Eckdaten dauerhaft unbegrenzt,
              drei ausführliche Bewertungen je 30 Tage.</div>
          </div>
        )}

        {/* 1 · Firma (getippt) */}
        {screen === "firma" && (
          <div className="card">
            <h1>Wie heißt eure Firma?</h1>
            <p className="lede">{ausDomain
              ? (domainStamm(email)
                ? <>Wir haben versucht, eure Firma an der Adresse <b>{email}</b> zu erkennen — unter „{domainStamm(email)}" finden wir aber kein Unternehmen in den Vergabedaten.</>
                : <>Eure Adresse ist eine Freemail-Adresse, daraus lässt sich keine Firma ableiten.</>)
              : "Damit wir euer Profil bauen können, brauchen wir den Firmennamen."}</p>
            <div className="field">
              <label className="lbl" htmlFor="q">Firmenname</label>
              <div className="inpwrap">
                <input className="inp" id="q" autoComplete="off" autoFocus value={eingabe}
                  placeholder="z. B. CANCOM, Bechtle …"
                  onChange={(e) => { setEingabe(e.target.value); setAcOpen(true); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && eingabe.trim()) { setAcOpen(false); zumMatch(); } }} />
                {acOpen && matches.length > 0 && (
                  <div className="ac" ref={acRef}>
                    {matches.map((m) => (
                      <button key={m.id} className="acopt" onClick={() => { setEingabe(m.name); setAcOpen(false); }}>
                        <span className="ac-n">{m.name}</span><span className="ac-w">{m.wins} Siege</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
              <span className="hint">Zum Ausprobieren: „cancom", „bechtle" oder „müller".</span>
            </div>
            <div className="btnrow">
              <button className="btn btn-p" disabled={!eingabe.trim() || busy} onClick={() => { setAcOpen(false); zumMatch(); }}>Suchen</button>
              <button className="btn btn-t" onClick={() => setScreen("branche")}>Wir haben noch nie öffentlich geboten</button>
            </div>
          </div>
        )}

        {/* 2 · Starker Vorschlag */}
        {screen === "vorschlag" && matched && (
          <div className="card">
            <h1>{ausDomain ? `Moment — arbeitest du bei ${matched.name}?` : "Das wissen wir über euch."}</h1>
            <p className="lede">{ausDomain
              ? <>Eure Adresse endet auf <b>{domainStamm(email)}</b> — und unter diesem Namen finden wir ein Unternehmen in den öffentlichen Vergabedaten. Falls das ihr seid, wissen wir schon einiges:</>
              : "Aus den öffentlichen Vergabedaten der letzten Jahre."}</p>
            <div className="suggest">
              <div className="sg-head">
                <div className="sg-name">{matched.name}</div>
                <div className="sg-meta"><span className="conf conf-belegt">belegt</span><span>über die Vergabedaten erkannt</span></div>
              </div>
              <div className="sg-stats">
                <div className="sg-stat"><span className="sg-k">Vergaben gewonnen</span><span className="sg-v">{matched.wins}</span></div>
                <div className="sg-stat"><span className="sg-k">Auftraggeber</span><span className="sg-v">{matched.buyers ?? "—"}</span></div>
                <div className="sg-stat"><span className="sg-k">Aktiv seit</span><span className="sg-v">{matched.seit ?? "—"}</span></div>
              </div>
            </div>
            <div className="note note-p">Passend zu diesem Profil bauen wir gleich eure Lead-Liste.
              Bestätigt die Firma, dann leiten wir das Profil aus euren Vergaben ab.</div>
            <div className="btnrow split">
              <button className="btn btn-p" onClick={() => bestaetigen(matched)}>Ja, das sind wir</button>
              <button className="btn btn-s" onClick={() => { setMatches([matched, ...matches].slice(0, 6)); setScreen("kandidaten"); }}>Nein, andere Firma</button>
            </div>
          </div>
        )}

        {/* 3 · Kandidaten (schwacher Match) */}
        {screen === "kandidaten" && (
          <div className="card wide">
            <h1>Meinst du eine dieser Firmen?</h1>
            <p className="lede">Der Name allein war nicht eindeutig. Deshalb schlagen wir nichts vor, sondern
              lassen euch wählen — eine falsche Zuordnung wäre schlimmer als eine Rückfrage.</p>
            <div className="cands">
              {matches.length ? matches.map((m) => (
                <button key={m.id} className="cand" onClick={() => bestaetigen(m)}>
                  <div className="cand-m"><span className="cand-n">{m.name}</span>
                    <span className="cand-x">{m.buyers ?? 0} Auftraggeber · aktiv seit {m.seit ?? "—"}</span></div>
                  <span className="cand-w">{m.wins} Siege</span>
                </button>
              )) : <div className="note note-i">Kein Treffer. Das ist normal — nur Unternehmen, die schon eine öffentliche Vergabe gewonnen haben, stehen in unseren Daten.</div>}
            </div>
            <div className="btnrow split">
              <button className="btn btn-s" onClick={() => setScreen("branche")}>Keine davon</button>
              <button className="btn btn-t" onClick={() => setScreen("firma")}>Namen ändern</button>
            </div>
          </div>
        )}

        {/* 4 · Gruppe = Identität */}
        {screen === "profil" && matched && (
          <div className="card wide">
            <h1>Gehören diese Einheiten zu euch?</h1>
            <p className="lede">Öffentliche Auftraggeber schreiben denselben Konzern unterschiedlich.
              Wir rechnen Siege aller aktiven Einheiten zusammen — sonst übersehen wir eure eigenen Aufträge.</p>
            {members.length ? (
              <div className="ents">
                {members.map((m, i) => (
                  <div key={i} className={`ent ${aktiv.has(String(i)) ? "on" : ""}`}>
                    <button className="ent-box" onClick={() => toggleMember(String(i))}>✓</button>
                    <div className="ent-m"><span className="ent-n">{m.name}</span><span className="ent-x">{m.method}</span></div>
                    <span className="ent-w">{m.wins}</span>
                  </div>
                ))}
              </div>
            ) : <div className="spin">Lade Einheiten …</div>}
            {aktiv.size === 0 && <div className="note note-w">Mindestens eine Einheit muss aktiv bleiben.</div>}
            {unsicher && <div className="note note-w">Eine aktive Einheit wurde <b>nur über den Namen</b> erkannt.
              Wir zeigen ihre Zahlen, kennzeichnen sie aber als unbestätigt — und rechnen sie nicht in die Erfolgsprämie ein, solange die Zuordnung nicht belegt ist.</div>}
            <div className="note note-p">Mit der Bestätigung merken wir uns diese Einheiten als eure Identität.
              Nur so erkennen wir später, dass ihr eine Ausschreibung gewonnen habt. <b>{winsAktiv} Siege</b> fließen in euer Profil.</div>
            <div className="btnrow split">
              <button className="btn btn-p" disabled={!aktiv.size} onClick={() => setScreen("fertig")}>Profil bestätigen</button>
              <button className="btn btn-t" onClick={() => setScreen("kandidaten")}>Doch eine andere Firma</button>
            </div>
          </div>
        )}

        {/* 5 · Branche (manueller Pfad) */}
        {screen === "branche" && (
          <div className="card wide">
            <h1>In welchem Bereich seid ihr unterwegs?</h1>
            <p className="lede">Eure Firma taucht in unseren Daten noch nicht als Auftragnehmer auf.
              Das ist kein Nachteil — wir starten mit eurem Feld und schärfen das Profil, je mehr ihr goVisor nutzt.</p>
            <div className="grid2">
              {BRANCHEN.map((b) => (
                <button key={b.k} className={`pick ${branche === b.k ? "on" : ""}`} onClick={() => setBranche(b.k)}>
                  <div className="pick-m"><span className="pick-n">{b.n}</span><span className="pick-x">{b.x}</span></div>
                </button>
              ))}
            </div>
            <div className="btnrow split">
              <button className="btn btn-p" disabled={!branche} onClick={() => setScreen("region")}>Weiter</button>
              <button className="btn btn-t" onClick={() => setScreen("firma")}>Zurück zur Firmensuche</button>
            </div>
          </div>
        )}

        {/* 6 · Region */}
        {screen === "region" && (
          <div className="card wide">
            <h1>Wo wollt ihr Aufträge gewinnen?</h1>
            <p className="lede">Mehrfachauswahl. Wir filtern nach dem <b>Leistungsort</b>, nicht nach dem Sitz
              der Vergabestelle — sonst zeigten wir euch Ausschreibungen in der falschen Gegend.</p>
            <div className="chips">
              {REGIONEN.map((r) => (
                <button key={r} className={`chip ${regionen.includes(r) ? "on" : ""}`} onClick={() => toggleRegion(r)}>{r}</button>
              ))}
            </div>
            <div className="note note-i">Bei etwa jeder zehnten Ausschreibung ist der Leistungsort nicht kreisgenau
              bekannt. Diese zeigen wir trotzdem, aber ohne Regionsfilter — lieber einmal zu viel als einen passenden Auftrag verschweigen.</div>
            <div className="btnrow split">
              <button className="btn btn-p" disabled={!regionen.length} onClick={() => setScreen("fertig")}>Fertig</button>
              <button className="btn btn-t" onClick={() => setScreen("branche")}>Zurück</button>
            </div>
          </div>
        )}

        {/* 7 · Fertig */}
        {screen === "fertig" && (
          <div className="card">
            <div className="done-ring">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
            </div>
            <h1>Alles bereit.</h1>
            <p className="lede">{matched
              ? "Wir haben euer Profil aus euren bisherigen Vergaben gebaut."
              : "Wir starten mit eurem Bereich und eurer Region — das Profil wächst mit der Nutzung."}</p>
            <div className="sum">
              {matched ? <>
                <div className="sum-r"><span className="sum-k">Firma</span><span className="sum-v">{matched.name}</span></div>
                <div className="sum-r"><span className="sum-k">Einheiten</span><span className="sum-v">{aktiv.size} aktiv</span></div>
                <div className="sum-r"><span className="sum-k">Siege im Profil</span><span className="sum-v">{winsAktiv}</span></div>
                <div className="sum-r"><span className="sum-k">Schwerpunkte</span><span className="sum-v">{matched.fields.slice(0, 4).map((f) => f.label || f.cpv4).join(" · ")}</span></div>
                <div className="sum-r"><span className="sum-k">Identität</span><span className="sum-v">bestätigt ✓</span></div>
              </> : <>
                <div className="sum-r"><span className="sum-k">Bereich</span><span className="sum-v">{BRANCHEN.find((b) => b.k === branche)?.n || "—"}</span></div>
                <div className="sum-r"><span className="sum-k">Regionen</span><span className="sum-v">{regionen.join(" · ") || "—"}</span></div>
                <div className="sum-r"><span className="sum-k">Identität</span><span className="sum-v">noch offen</span></div>
              </>}
              <div className="sum-r"><span className="sum-k">Zugang</span><span className="sum-v">Free — Liste und Eckdaten unbegrenzt, 3 Bewertungen je 30 Tage</span></div>
            </div>
            {!matched && <div className="note note-i">Sobald ihr eine Vergabe gewinnt, erkennen wir das und fragen,
              ob wir euer Profil ergänzen dürfen.</div>}
            <div className="btnrow">
              <button className="btn btn-p" onClick={fertigstellen}>Leads ansehen</button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
