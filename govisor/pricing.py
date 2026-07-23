"""Erfolgsgebühren-Preismodell über die Gebühren-Basis ``value_band_effektiv``.

Die Gebühr fällt an, WENN der Nutzer einen gefundenen Auftrag gewinnt. Sie hängt am
Auftragswert-Band — mit zwei bewussten Design-Zwängen aus der Datenmessung:

  * **Ränder fix, Kern prozentual.** Kleinstaufträge (<50k) tragen keine Erfolgs-
    gebühr (im Abo enthalten); Mega-Aufträge (>5M) zahlen eine FIXgebühr statt %,
    weil ihr Wert oft ein Rahmenvertrags-Höchstwert ist (kein echter Umsatz).
  * **Unsicherheits-Rabatt.** Ist das Band nur imputiert/default (Wert nicht
    veröffentlicht), wird konservativer abgerechnet — die Gebühr bleibt so auch
    bei den ~58 % nicht-echten Werten verteidigbar.

Alles hier ist **Konfiguration** — Beträge/Prozente frei kalibrierbar. Lauf
``python -m govisor.pricing`` rechnet die Staffel an den echten Leads durch.
"""
from __future__ import annotations

# Band → Pauschale (reines Flat-per-Band). 7 Stufen, Grenzen an den echten Wert-
# Perzentilen; Stufen 1-5 verdoppeln sich sauber (600→1.200→…→9.600, konstante 2×-
# Klippen), oben Fix. Keys = exakt die Labels aus gold._band_sql. mode 'flat' = Fixbetrag
# (mode 'pct' bleibt in fee() unterstützt, wird hier aber nicht genutzt).
SCHEDULE: dict[str, dict] = {
    "<100k":     {"mode": "flat", "amount": 600},      # Lose/Unterschwelle
    "100-250k":  {"mode": "flat", "amount": 1_200},
    "250-500k":  {"mode": "flat", "amount": 2_400},    # Median-Deal-Band
    "500k-1,3M": {"mode": "flat", "amount": 4_800},
    "1,3-5M":    {"mode": "flat", "amount": 9_600},    # ~$10k/Zuschlag-Präzedenzfall
    "5-25M":     {"mode": "flat", "amount": 15_000},   # echte Großdeals
    ">25M":      {"mode": "flat", "amount": 25_000},   # Rahmen/Ceiling → nur Schwelle nötig
}

# Rabatt, wenn das Band nur aus CPV-Median (imputiert) oder Default stammt.
UNCERTAINTY_DISCOUNT = 0.8
UNCERTAIN_SOURCES = frozenset({"imputiert", "default"})


def fee(band_effektiv: str, band_source: str, value_effektiv: float | None,
        schedule: dict | None = None, discount: float = UNCERTAINTY_DISCOUNT) -> float:
    """Erfolgsgebühr für einen gewonnenen Auftrag. Immer ein Wert (Band nie unbekannt)."""
    rule = (schedule or SCHEDULE).get(band_effektiv)
    if rule is None:
        return 0.0
    if rule["mode"] == "flat":
        base = float(rule["amount"])
    else:
        v = value_effektiv or 0.0
        base = min(max(v * rule["pct"], rule["floor"]), rule["cap"])
    if band_source in UNCERTAIN_SOURCES:
        base *= discount
    return round(base, 2)


def _run(country: str = "DE", data_dir: str = "data") -> None:
    """Staffel an den echten Leads durchrechnen — Verteilung + Summen."""
    import duckdb
    from pathlib import Path

    g = Path(data_dir) / "gold" / country
    con = duckdb.connect()
    con.create_function(  # special: NULL value_effektiv soll fee() erreichen (Floor greift)
        "fee", lambda b, s, v: fee(b, s, v),
        ["VARCHAR", "VARCHAR", "DOUBLE"], "DOUBLE", null_handling="special")
    rows = con.execute(f"""
        SELECT band_effektiv, band_source, count(*) n,
               round(sum(fee(band_effektiv, band_source, value_effektiv))) fee_sum,
               round(avg(fee(band_effektiv, band_source, value_effektiv))) fee_avg
        FROM read_parquet('{(g / 'value_band_effektiv.parquet').as_posix()}')
        GROUP BY 1, 2 ORDER BY 1, 2
    """).fetchall()
    tot_n = sum(r[2] for r in rows)
    tot_fee = sum(r[3] for r in rows)
    print(f"{'Band':9} {'Quelle':11} {'Leads':>7} {'Ø-Gebühr':>10} {'Summe (wenn alle gewonnen)':>28}")
    print("-" * 70)
    for band, src, n, fsum, favg in rows:
        print(f"{band:9} {src:11} {n:>7,} {favg:>9,.0f}€ {fsum:>26,.0f}€")
    print("-" * 70)
    print(f"{'GESAMT':21} {tot_n:>7,} {tot_fee/tot_n:>9,.0f}€ {tot_fee:>26,.0f}€")
    print("\nHinweis: Summe = theoretische Obergrenze (alle Leads gewonnen). "
          "Echter Umsatz = Summe x Gewinn-Konversion deiner Nutzer.")


if __name__ == "__main__":
    _run()
