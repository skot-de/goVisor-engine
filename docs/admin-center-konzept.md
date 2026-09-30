# Internes Admin-Center — Konzept

Stand 2026-09-30. Vorgehen (Sven): erst Konzept & Inhalte, dann bauen. Zweck: **Insights
UND Troubleshooting** in einem internen Werkzeug.

## Grundstein (schon da)

`/intern` + `/api/intern/{claims,firmen,landing,lauf,outreach}`, abgesichert über `istAdmin`
(Env-Allowlist `ADMIN_EMAILS`, `web/lib/admin.ts`), 404-Gating in der Middleware, in
Produktion hart gesperrt (`INTERN_ENABLED`). Darauf baut das Admin-Center auf.

## Leitplanken

- **Läuft auf dem Worker-Dienst (Deploy-Weg C).** Fast alle Inhalte brauchen Datei-/Python-/
  DB-Zugriff (`intern/lauf` liest das Dateisystem, Firmensuche/Outreach starten Python). Das
  Admin-Center ist deshalb kein Teil der öffentlichen Edge-App, sondern lebt auf demselben
  Dauer-Host wie die schweren Routen. Es hängt damit am Deploy-Startschuss.
- **Sicherheit**: hinter `istAdmin`, eigenes Gate/Netz, nie Teil der öffentlichen App,
  Audit-Log für Aktionen.
- **Passwörter**: der Admin löst nur eine **Reset-Mail** aus (Supabase), setzt nie selbst ein
  Passwort.

## Bereiche (1-6)

| # | Bereich | Insights (sehen) | Aktionen (troubleshooting) | Quelle |
|---|---|---|---|---|
| 1 | **Betrieb** | Nachtlauf-Status, 8 Sonden/Wächterdienst, Dokument-Rückstau, Datenfrische je Land | Lauf/Sonde anstoßen, Rückstau erklären | `api/intern/lauf`, `waechterlauf.sh`, `letzter_lauf.txt` |
| 2 | **Datenqualität** | Review-Queue, Entity-Merge-Kandidaten, Dubletten, Quality-Flags, Abdeckung je Land/Portal | Merge bestätigen/ablehnen, Flag klären | Gold-Tabellen, `curated/` |
| 3 | **Konten & Profile** | Orgs, User, Profile, Seats, Pläne, Quote/Nutzung | **Firmensuche**, **Passwort-Reset (Mail)**, Plan/Seats setzen, Identitäts-Claim prüfen | Supabase, `api/intern/claims` |
| 4 | **Vertrieb & Outreach** | Zielliste, Schmerz-Signale, Outreach-Log, Trefferquote | Firmensuche, Landing/Token erzeugen, Ansprache loggen | `api/intern/{firmen,landing,outreach}` |
| 5 | **Kuratierung** | `curated/`-CSVs (Aliasse, Regionskorrekturen, gesperrte Hosts, Portale ohne Abrufer), Doktypen | Eintrag hinzufügen/ändern | `curated/`, `govisor/doctypes.py` |
| 6 | **LLM & Kosten** | OpenRouter-Guthaben & Ausgaben, Modellwahl, Geldwache-Reserve, Analyse-Rückstau | Modell umstellen, Reserve setzen | LLM-Konfig, `docs/modellwahl-und-anbieterboden.md` |

### Zusätze (Sven), eingeordnet
- **Firmensuche** — existiert (`intern/firmen`: Sitz/Name + Schmerzsignale), sichtbar in
  Bereich 3 und 4.
- **Passwort-Reset** — Bereich 3, als ausgelöste Reset-Mail (nie Passwort setzen).
- Ausrichtung **Insights + Troubleshooting** ist über alle Bereiche der Leitgedanke: jede
  Zeile hat eine „sehen"- und, wo sinnvoll, eine „handeln"-Spalte.

## Geparkt: Bereich 7 — Agenten-Werkstatt (ausgeklammert am 2026-09-30)

Bewusst **vorerst nicht** im Umfang. Festgehalten für später, damit die Idee und ihre
Sicherheitsleitplanke nicht verloren gehen:

> Das Portal öffnet eine **Agenten-Sitzung gegen das Repo**, die einen Fix erarbeitet und als
> **Pull Request mit Tests** vorlegt; ein Mensch merged. **Nie Auto-Deploy**, streng gegated
> (nur Admin, eigenes Netz), Audit-Log. Setzt den Worker-Dienst (Weg C) voraus und wäre als
> **letztes** zu bauen, wenn 1-6 stehen.

## Bau-Reihenfolge

1. Umfang 1-6 bestätigt (dieses Dokument).
2. Pro Bereich die konkrete Inhalts-/Aktionsliste ausdefinieren (nächster Schritt).
3. Bau auf dem Worker-Dienst — nach dem Deploy-Startschuss (Weg C).
