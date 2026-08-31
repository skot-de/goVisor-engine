import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";
import { istAdmin } from "@/lib/admin";

/**
 * Pre-Launch-Blackout — FAIL-CLOSED.
 *
 * Jedes Production-Deployment liefert NUR eine leere schwarze Seite (auch /api), SOLANGE nicht
 * explizit `LAUNCH_LIVE=1` gesetzt ist. Lokale Entwicklung (`next dev`, NODE_ENV≠production) läuft
 * immer voll — dort ist der Blackout nie aktiv.
 *
 * Wichtig (Härtung): der Schutz hängt NICHT mehr an einer plattform-gesetzten Var (`VERCEL`),
 * deren Fehlen früher die volle App öffentlich machte (fail-open auf fremdem Host/Klon/Preview).
 * Default ist jetzt schwarz; Freischalten = aktives Setzen von `LAUNCH_LIVE=1` in der Deploy-Umgebung
 * (kein Code-Change nötig).
 *
 * VORSCHAU-BYPASS (privat deployen, ohne öffentlich zu sein): ist der Blackout aktiv, kommt man mit
 * dem geheimen Schlüssel `?preview=<PREVIEW_KEY>` (oder gesetztem Cookie) trotzdem in die volle App;
 * die Öffentlichkeit sieht weiter Schwarz. FAIL-CLOSED: ist `PREVIEW_KEY` leer/ungesetzt, gibt es
 * KEINEN Bypass. So bleibt LAUNCH_LIVE ungesetzt (public = schwarz), und nur Sven kommt rein.
 */
const BLACKOUT = process.env.NODE_ENV === "production" && process.env.LAUNCH_LIVE !== "1";
const PREVIEW_KEY = process.env.PREVIEW_KEY ?? "";
const PREVIEW_COOKIE = "gv_preview";

/* ── INTERNE SEITEN ────────────────────────────────────────────────────────────────────
 *
 * Bis 2026-08-16 pruefte KEINE der `/intern`-Seiten und auch die API nichts. Geschuetzt
 * hat sie allein die Coming-Soon-Sperre oben — und die ist ein LAUNCH-Gate, keine
 * Zugriffskontrolle: am Tag der Freischaltung waeren `/intern/lauf` und `/api/intern/lauf`
 * oeffentlich gewesen, samt Logzeilen, Pfaden und Fehlermeldungen aus dem Dateisystem.
 *
 * WARUM HIER UND NICHT IN DEN SEITEN: einen Link zu verstecken ist keine Absicherung. Die
 * URL ist raterbar, die API direkt aufrufbar. Die Sperre gehoert an die eine Stelle, die
 * JEDE Anfrage sieht.
 *
 * WARUM 404 UND NICHT 403: ein 403 bestaetigt, dass es die Seite gibt. Fuer eine interne
 * Oberflaeche ist schon diese Auskunft zu viel.
 *
 * WARUM UMGEBUNGSVARIABLE UND NICHT DATENBANK-ROLLE: fuer eine Person ist ein Rollenmodell
 * mehr Angriffsflaeche als Nutzen. Ein Datenbankfeld kann man versehentlich setzen; eine
 * Vercel-Umgebungsvariable nicht.
 */

/* ── ANMELDE-TOR ───────────────────────────────────────────────────────────────────────
 *
 * WARUM. Die ganze Anwendung beruht darauf, GEZIELTE Ausschreibungen zu zeigen. Ohne Profil
 * ist die Liste eine ungefilterte Aufzaehlung von 15.762 Vergaben — genau das, was jedes
 * kostenlose Portal auch kann. Der Wert entsteht erst mit dem Profil, also gibt es die App
 * erst nach der Anmeldung. „Free" heisst kostenlos NACH der Registrierung, nicht ohne.
 *
 * WAS BEWUSST OFFEN BLEIBT:
 *   /login /onboarding /start   der Weg hinein — sonst sperrt man die Tuer von innen ab
 *   /t/…                        der Vertriebs-Einstieg, ausdruecklich ohne Konto gedacht
 *   /api/wer                    die Selbstauskunft; sie MUSS „nein" sagen koennen
 *   /api/entity-search          die Firmensuche des Onboardings — sie laeuft VOR der
 *                               Anmeldung. Ich hatte sie beim Bau des Tors vergessen; der
 *                               Firma-Schritt lieferte dadurch „Anmeldung erforderlich"
 *                               und die Kandidatenliste blieb leer, ohne Fehlermeldung.
 *   /api/entity-group           die Mitglieder einer Firmengruppe, gleicher Grund.
 *   /api/outreach-firma         der Firmenname zum Outreach-Token, fuer die Vorbelegung
 *   /api/entity-verify          die Firmensuche des Onboardings. Sie laeuft, BEVOR eine
 *                               Sitzung existiert: bei ausstehender E-Mail-Bestaetigung
 *                               gibt es nach `signUp` noch keine. Ohne diese Ausnahme
 *                               waere Schritt 2 der Registrierung tot.
 *   /api/calendar/<token>       der iCal-Feed. Ihn holt Outlook bzw. Google, nicht der
 *                               Browser des Nutzers — diese Clients schicken KEIN
 *                               Sitzungscookie und koennen sich auch nicht anmelden.
 *                               Hinter dem Tor war der Feed unabonnierbar, obwohl die
 *                               Oberflaeche ihn anbietet („aktualisiert sich automatisch").
 *                               Die Berechtigung ist hier der TOKEN: die Route loest ihn
 *                               serverseitig gegen `user_calendar_feed` auf und antwortet
 *                               sonst mit 404. Weil sie damit oeffentlich erreichbar ist,
 *                               hat sie eine Ratenbremse bekommen.
 *   /robots.txt /sitemap.xml    die zwei Dateien, die ein Crawler als ERSTES holt — und er
 *                               holt sie ohne Konto. Hinter dem Tor beantwortete beide eine
 *                               Umleitung auf `/login`; eine robots.txt, die auf eine
 *                               Anmeldemaske zeigt, ist keine. Gemessen am 2026-08-30, kurz
 *                               nachdem ich sie angelegt hatte: `GET /robots.txt` →
 *                               `/login?weiter=%2Frobots.txt`. Sie geben nichts preis, was
 *                               nicht ohnehin fuer die Oeffentlichkeit gedacht ist — die
 *                               Sitemap nennt Startseite, Einstieg und Anmeldung.
 *   /api/alerts/run             der Frist-Hinweislauf. Ihn ruft der Vercel-Scheduler
 *                               (`web/vercel.json`, taeglich 06:00), und ein Scheduler hat
 *                               keine Sitzung. Hinter dem Tor bekam er jeden Morgen 401 —
 *                               gemessen am 2026-08-31, auch MIT Bearer-Kopfzeile. Ein Cron,
 *                               der ins Leere laeuft, meldet sich nicht: die Hinweise waeren
 *                               einfach nie gekommen, und das ausgerechnet bei dem
 *                               Versprechen, um dessentwillen es das Produkt gibt.
 *                               Die Berechtigung ist hier das CRON_SECRET: `requireCronSecret`
 *                               ist fail-closed (ohne Geheimnis 503, mit falschem 403).
 */
const OFFEN = ["/login", "/auth", "/api/health", "/onboarding", "/start", "/t", "/api/wer", "/api/entity-verify", "/api/impressum", "/api/entity-search",
                     "/api/entity-group", "/api/outreach-firma", "/api/calendar",
                     "/robots.txt", "/sitemap.xml", "/api/alerts/run"];

function istOffen(pfad: string): boolean {
  // Die Wurzel zeigt seit dem 2026-08-20 die oeffentliche Startseite (app/page.tsx) und
  // leitet nur ANGEMELDETE in die App. Vorher fuehrte sie immer nach `/leads` und damit
  // jeden Fremden auf die Anmeldemaske.
  if (pfad === "/") return true;
  return OFFEN.some((o) => pfad === o || pfad.startsWith(o + "/"));
}

function istIntern(pfad: string): boolean {
  return pfad === "/intern" || pfad.startsWith("/intern/") || pfad.startsWith("/api/intern");
}


/**
 * VORHANG-PFAD — der zweite, sanftere Weg hinein.
 *
 * Bis hierher war der Preview-Schlüssel die Authentifizierung: ein Geheimnis, alles oder
 * nichts, kein Login. Das hat zwei Nachteile. Erstens steht der Schlüssel in der URL und
 * landet damit in Browser-Historie, Proxy-Logs und Referrern. Zweitens gibt es keine
 * Rollen — wer ihn hat, ist drin, egal als wer.
 *
 * `ZUGANG_PFAD` ist deshalb ausdrücklich KEIN Passwort. Der Pfad zieht nur den Vorhang auf
 * und zeigt ein Login-Fenster; wer dahinter etwas sehen will, muss sich anmelden. Der Schutz
 * liegt in der Anmeldung, die Unerratbarkeit ist nur Ruhe vor Scannern.
 *
 * Bewusst ein PFAD und keine Subdomain: eine Subdomain taucht in den Certificate-
 * Transparency-Logs auf, ist also faktisch öffentlich — sie wäre schwerer zu bauen und
 * leichter zu finden.
 *
 * FAIL-CLOSED bleibt: ist `ZUGANG_PFAD` leer, gibt es diesen Weg nicht.
 */
const ZUGANG_PFAD = process.env.ZUGANG_PFAD ?? "";
const VORHANG_COOKIE = "gv_vorhang";

/** Antwort fuer gesperrte Interna. Bewusst 404 statt 403 und ohne Hinweistext: ein 403
 *  bestaetigt, dass es die Seite gibt, und genau das soll niemand erfahren. */
/** Ohne Sitzung zum Anmelden. APIs bekommen 401 statt einer Umleitung — eine HTML-Seite als
 *  Antwort auf einen Datenabruf ist fuer den Aufrufer unbrauchbar und erzeugt Folgefehler,
 *  die nach etwas ganz anderem aussehen. */
function zumLogin(request: NextRequest, pfad: string) {
  if (pfad.startsWith("/api/")) {
    return NextResponse.json({ error: "Anmeldung erforderlich" }, { status: 401 });
  }
  const ziel = new URL("/login", request.url);
  // Wohin der Nutzer WOLLTE — damit er nach dem Anmelden dort landet und nicht irgendwo.
  if (pfad && pfad !== "/") ziel.searchParams.set("weiter", pfad);
  return NextResponse.redirect(ziel);
}

function nichtGefunden() {
  return new NextResponse("Not found", {
    status: 404,
    headers: { "content-type": "text/plain; charset=utf-8",
               "cache-control": "no-store", "x-robots-tag": "noindex, nofollow" },
  });
}

function blackPage() {
  return new NextResponse(BLACK_PAGE, {
    status: 200,
    headers: {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "x-robots-tag": "noindex, nofollow",
    },
  });
}

export async function middleware(request: NextRequest) {
  const pfad = new URL(request.url).pathname;
  if (BLACKOUT) {
    // Bypass nur, wenn ein PREVIEW_KEY gesetzt ist UND per Query/Cookie exakt getroffen wird.
    const q = new URL(request.url).searchParams.get("preview");
    const cookie = request.cookies.get(PREVIEW_COOKIE)?.value;
    const unlocked = PREVIEW_KEY.length > 0 && (q === PREVIEW_KEY || cookie === PREVIEW_KEY);

    // Zweiter Weg: der Vorhang-Pfad. Er fuehrt auf /login und setzt ein Cookie, damit die
    // Folgeseiten (Anmeldung, Registrierung, App) nicht wieder schwarz werden. Was danach
    // sichtbar ist, entscheidet die Supabase-Session — nicht dieser Pfad.
    const vorhangCookie = request.cookies.get(VORHANG_COOKIE)?.value;
    const vorhangAuf = ZUGANG_PFAD.length > 0 && vorhangCookie === ZUGANG_PFAD;
    if (ZUGANG_PFAD.length > 0 && pfad === `/${ZUGANG_PFAD}`) {
      const res = NextResponse.redirect(new URL("/login", request.url));
      res.cookies.set(VORHANG_COOKIE, ZUGANG_PFAD, {
        httpOnly: true, sameSite: "lax", secure: true, path: "/", maxAge: 60 * 60 * 24 * 30,
      });
      return res;
    }
    // Die Rueckkehr aus einer Anmelde-Mail muss auch durch den Vorhang. Sie zeigt nichts:
    // sie loest einen Einmal-Token ein und leitet weiter. Ohne diese Ausnahme waere jede
    // Passwort-Wiederherstellung live tot, weil die schwarze Seite vor der Route kaeme.
    // Die Gesundheitsprobe muss auch durch den Vorhang: eine Ueberwachung, die nur die
    // schwarze Seite sieht, meldet „alles gut", waehrend die Daten fehlen. Sie verraet
    // nichts ausser Zustand und Alter (s. app/api/health/route.ts).
    // Der Kalender-Feed muss ebenfalls durch den Vorhang, aus demselben Grund wie die
    // Gesundheitsprobe: ein Kalenderprogramm, das die schwarze Seite bekommt, meldet
    // keinen Fehler — es zeigt einen LEEREN Kalender. Abonniert und still, und der Nutzer
    // merkt es erst, wenn er eine Frist verpasst hat. Er verraet nichts: ohne gueltigen
    // Token gibt die Route 404.
    // Auch `robots.txt` und `sitemap.xml` muessen durch den Vorhang. Ein Crawler, der als
    // Antwort auf `robots.txt` eine schwarze HTML-Seite bekommt, liest daraus keine Regeln
    // — er sieht eine kaputte Datei und faellt auf „alles erlaubt" zurueck. Verraten wird
    // dabei nichts: waehrend der Sperre traegt ohnehin jede Seite `noindex`.
    // Der Hinweislauf muss ebenfalls durch, aus demselben Grund wie die Gesundheitsprobe:
    // ein Scheduler, der eine schwarze HTML-Seite bekommt, meldet keinen Fehler. Er laeuft
    // jeden Morgen, bekommt 200, und niemand erfaehrt, dass nichts passiert ist. Verraten
    // wird nichts — ohne CRON_SECRET antwortet die Route mit 503, mit falschem mit 403.
    if (!unlocked && !vorhangAuf && !pfad.startsWith("/auth/") && pfad !== "/api/health"
        && !pfad.startsWith("/api/calendar/")
        && pfad !== "/robots.txt" && pfad !== "/sitemap.xml"
        && pfad !== "/api/alerts/run")
      return blackPage();
    // Schlüssel gültig → volle App; bei frischem ?preview den Cookie setzen (Folgeseiten ohne Query).
    const { response: res, email } = await updateSession(request);
    if (istIntern(pfad) && !istAdmin(email)) return nichtGefunden();
    if (!email && !istOffen(pfad)) return zumLogin(request, pfad);
    if (q === PREVIEW_KEY) {
      res.cookies.set(PREVIEW_COOKIE, PREVIEW_KEY, {
        httpOnly: true, sameSite: "lax", secure: true, path: "/", maxAge: 60 * 60 * 24 * 30,
      });
    }
    return res;
  }
  // Lokal: Auth-Session frisch halten wie gehabt, volle App. Die Interna sind aber AUCH
  // lokal gesperrt — sonst waere die Sperre nie ausprobiert und faende ihren ersten
  // Ernstfall in der Produktion.
  const { response, email } = await updateSession(request);
  if (istIntern(pfad) && !istAdmin(email)) return nichtGefunden();
  if (!email && !istOffen(pfad)) return zumLogin(request, pfad);
  return response;
}

export const config = {
  // Alles außer statischen Assets — greift den Blackout bzw. hält die Auth-Session frisch. /api erfasst.
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};

// Reine schwarze Seite — kein Text, kein Logo.
const BLACK_PAGE = `<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow"><title></title><style>html,body{margin:0;height:100%;background:#000}</style></head><body></body></html>`;
