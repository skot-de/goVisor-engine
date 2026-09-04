"""Gemeinsame Voreinstellungen für alle Tests.

⚠ **KEIN BYTECODE WÄHREND DER TESTS.** Das ist keine Geschmacksfrage, sondern verhindert
eine Falle, die am 2026-09-04 zugeschlagen hat und die genau die Arbeitsweise trifft, mit
der hier jeder Fund belegt wird: Fehler zurückbauen, Test laufen lassen, Fehler entfernen,
Test noch einmal laufen lassen.

27 Testdateien laden Skripte über `importlib.util.spec_from_file_location`. Dabei schreibt
Python ein `.pyc` und merkt sich darin die Zeit der Quelldatei — **in ganzen Sekunden**.
Wird die Quelle innerhalb derselben Sekunde geändert und bleibt dabei gleich gross (`<` zu
`>` etwa), ist die Änderung für Python unsichtbar, und der Test führt den ALTEN Code aus.
Gemessen, nicht vermutet:

    Änderung in derselben Sekunde, gleiche Groesse  → alter Wert
    Änderung eine Sekunde spaeter                   → neuer Wert

Das ist die teuerste Sorte Fehler, die es hier gibt: eine Gegenprobe, die den falschen Code
prüft. Sie kann in beide Richtungen lügen — ein blinder Test sieht scharf aus, weil noch der
kaputte Bytecode läuft, oder ein guter Test wirkt blind, weil noch der heile läuft.
Aufgefallen ist es nur daran, dass die Tests nach dem Zurückbauen rot blieben.

Ohne geschriebenen Bytecode entsteht das Problem gar nicht: es gibt nichts, was veralten
kann. Der Preis ist etwas Ladezeit je Lauf.
"""
import sys

sys.dont_write_bytecode = True
