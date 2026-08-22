# Den Dokumentkorpus sichern

**Warum.** `data/docs` sind 173 GB in 6.860 Dateien, überwiegend ZIPs mit Vergabeunterlagen.
Daraus entstehen 6.563 Volltexte und 6.262 LLM-Auswertungen — die Grundlage für den
Anforderungs-Check, die Checklisten und die Mustererkennung, die Sven daraus ableiten will.

⚠️ **Es gibt sie genau einmal**, auf einer externen SSD. Der Rest der Plattform ist aus ihnen
regenerierbar (Silber, Gold, Exporte), sie selbst aus nichts: Portale geben nicht alles ein
zweites Mal heraus, `SPERRE_TAGE` bremst jeden erneuten Versuch, und ältere Vergaben
verschwinden aus den Portalen. Fällt die SSD aus, sind sie weg — und mit ihnen die
6.262 Auswertungen, die bei 8 USD Tagesdeckel Monate gekostet haben.

Das ist das wertvollste Stück der Plattform. Wertvoller als der Code, denn den kann man
neu schreiben.

## Was zu tun ist (einmalig)

1. **Azure-Konto anlegen**, dann ein **Storage Account** (StorageV2, LRS reicht, Region
   West Europe). LRS statt GRS, weil es eine Sicherung ist und keine hochverfügbare Quelle.
2. **Container anlegen**, z. B. `govisor`. **Nicht öffentlich** (Zugriffsebene „privat").
3. **SAS-Token erzeugen** auf Container-Ebene, Rechte `Write`, `Create`, `Read`, `List`,
   Ablauf mindestens ein Jahr. Die vollständige URL sieht so aus:

   ```
   https://<konto>.blob.core.windows.net/govisor?sv=2024-…&sig=…
   ```

4. **In `web/.env.local` eintragen** (der Tageslauf liest diese Datei, er hat kein Shell-Profil):

   ```
   DATA_AZURE_URL=https://<konto>.blob.core.windows.net/govisor?sv=…
   ```

5. **Trockenlauf**, er zeigt Menge und Stufe, ohne etwas zu schreiben:

   ```
   python3 scripts/upload_web_data.py --quelle docs --probe
   ```

6. **Sichern.** Der erste Lauf überträgt 173 GB und dauert über eine Hausleitung mehrere
   Tage. Er ist **unterbrechbar**: das Skript fragt je Datei die Größe im Speicher ab und
   überspringt, was schon gleich groß dort liegt. Einfach erneut starten.

   ```
   python3 scripts/upload_web_data.py --quelle docs
   ```

## Was das Skript tut

* Quelle `docs` statt `web`, eigenes Präfix `docs/` im Container — sonst mischen sich
  173 GB Archiv und 984 MB Betriebsdaten, und eine Lebenszyklus-Regel träfe die falschen.
* Stufe **Cool** beim Schreiben, nicht nachträglich: nachträglich wäre es eine zweite
  Operation je Blob und bei 6.860 Dateien ein eigener Lauf.
* **Nicht Archive.** Archive kostet weniger, muss aber vor jedem Zugriff stundenlang
  aufgetaut werden. Wer Muster aus den Unterlagen ableiten will, greift zu — dann ist
  Archive der falsche Platz.

## Kosten

173 GB in Cool sind rund **1,50 bis 2 € im Monat** (West Europe, LRS, Stand der Preise
prüfen). Das Hochladen selbst kostet nichts, Azure berechnet eingehenden Verkehr nicht.
Teuer wird nur das Zurückholen — was der Sinn einer Sicherung ist, die man nicht braucht.

## Danach

Der Tageslauf holt laufend neue Unterlagen. Ein wöchentlicher Nachlauf reicht, weil das
Skript nur Neues überträgt:

```
python3 scripts/upload_web_data.py --quelle docs
```
