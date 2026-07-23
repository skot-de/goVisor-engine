"""CPV-Divisionen → Bezeichnung, Sektor, Branche.

Die CPV-Division (erste 2 Stellen) ist der Fakt aus den Daten. ``sector`` und
``branche`` sind die redaktionelle Gruppierung — deine Setzung, versioniert,
in Gold. Silber bleibt unberührt: dort stehen die Rohcodes.

``branche`` ist bewusst grob und änderbar. 'IT' hier umfasst Dienste, Software,
Hardware, Telekommunikation und IT-nahe Wartung — das ist eine Geschäfts-
entscheidung, keine Tatsache, und darf sich ändern, ohne Silber neu zu bauen.
"""

from __future__ import annotations

DIM_CPV_VERSION = 1

# division → (Bezeichnung, Sektor, Branche)
DIVISIONS = {
    "03": ("Landwirtschaft, Fischerei, Forst", "Primär", "Landwirtschaft"),
    "09": ("Energie, Kraftstoffe, Strom", "Versorgung", "Energie"),
    "14": ("Bergbau, Metalle", "Industrie", "Rohstoffe"),
    "15": ("Lebensmittel, Getränke, Tabak", "Konsum", "Lebensmittel"),
    "16": ("Landmaschinen", "Industrie", "Maschinen"),
    "18": ("Bekleidung, Schuhe, Gepäck", "Konsum", "Textil"),
    "19": ("Leder, Textil, Kunststoff, Gummi", "Industrie", "Textil"),
    "22": ("Druckerzeugnisse", "Konsum", "Druck/Medien"),
    "24": ("Chemische Erzeugnisse", "Industrie", "Chemie"),
    "30": ("Büro-/Computermaschinen (Hardware)", "IT", "IT"),
    "31": ("Elektrische Maschinen, Beleuchtung", "Industrie", "Elektro"),
    "32": ("Rundfunk, Telekommunikationsgeräte", "IT", "IT"),
    "33": ("Medizintechnik, Pharma", "Gesundheit", "Medizin"),
    "34": ("Transportmittel", "Transport", "Fahrzeuge"),
    "35": ("Sicherheit, Feuerwehr, Verteidigung", "Sicherheit", "Sicherheit"),
    "37": ("Musikinstrumente, Sport, Spielwaren", "Konsum", "Freizeit"),
    "38": ("Labor-, Präzisionsgeräte", "Industrie", "Messtechnik"),
    "39": ("Möbel, Haushaltsgeräte, Reinigung", "Konsum", "Möbel/Ausstattung"),
    "41": ("Wasser", "Versorgung", "Wasser"),
    "42": ("Industriemaschinen", "Industrie", "Maschinen"),
    "43": ("Bergbau-/Baumaschinen", "Industrie", "Maschinen"),
    "44": ("Baustoffe, Bauhilfsprodukte", "Bau", "Bau"),
    "45": ("Bauarbeiten", "Bau", "Bau"),
    "48": ("Softwarepakete, Informationssysteme", "IT", "IT"),
    "50": ("Reparatur und Wartung", "Dienstleistung", "Wartung"),
    "51": ("Installationsleistungen (außer Software)", "Dienstleistung", "Installation"),
    "55": ("Hotel, Gaststätten, Handel", "Dienstleistung", "Gastgewerbe"),
    "60": ("Transportdienste", "Transport", "Transport"),
    "63": ("Transport-Hilfsdienste, Reisebüros", "Transport", "Transport"),
    "64": ("Post- und Telekommunikationsdienste", "IT", "IT"),
    "65": ("Öffentliche Versorgung", "Versorgung", "Versorgung"),
    "66": ("Finanz- und Versicherungsdienste", "Dienstleistung", "Finanzen"),
    "70": ("Immobiliendienste", "Dienstleistung", "Immobilien"),
    "71": ("Architektur, Ingenieurwesen, Prüfung", "Bau", "Ingenieur/Architektur"),
    "72": ("IT-Dienste: Beratung, Softwareentw., Support", "IT", "IT"),
    "73": ("Forschung und Entwicklung", "Dienstleistung", "Forschung"),
    "75": ("Verwaltung, Verteidigung, Sozialversicherung", "Verwaltung", "Verwaltung"),
    "76": ("Öl- und Gasindustrie-Dienste", "Versorgung", "Energie"),
    "77": ("Landwirtschafts-/Forstdienste", "Primär", "Landwirtschaft"),
    "79": ("Unternehmensdienste: Recht, Marketing, Beratung", "Dienstleistung", "Beratung"),
    "80": ("Bildung und Ausbildung", "Bildung", "Bildung"),
    "85": ("Gesundheit und Sozialwesen", "Gesundheit", "Gesundheit"),
    "90": ("Abwasser, Abfall, Reinigung, Umwelt", "Umwelt", "Umwelt/Reinigung"),
    "92": ("Freizeit, Kultur, Sport", "Konsum", "Kultur"),
    "98": ("Sonstige soziale/persönliche Dienste", "Dienstleistung", "Sonstige"),
}


def division_of(cpv_code: str | None) -> str | None:
    if cpv_code and len(cpv_code) >= 2 and cpv_code[:2].isdigit():
        return cpv_code[:2]
    return None
