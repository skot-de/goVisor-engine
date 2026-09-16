# Kennzahlen-Katalog

> ⚠ **ERZEUGT, NICHT GETIPPT.** `python3 scripts/kpi_katalog.py`. Wer hier von Hand
> schreibt, verliert es beim naechsten Lauf. Stand 2026-09-16.

## Die Regel

Eine Kennzahl ist ein **abgeleiteter Wert, der eine Entscheidung stuetzt**. Keine
Kennung, kein Name, kein Link, kein Herkunftskennzeichen, kein rohes Stammdatum.
Die Ausschlussliste steht als Regex im Skript und ist damit pruefbar.

⚠ Das ist **Auslegung, nicht Wahrheit**. Eine andere Regel ergibt eine andere Zahl;
dann gehoert die neue Regel ins Skript und nicht in eine Fussnote.

## Die Zahl

**149 verschiedene Kennzahlen.** Davon 111 in den
Produktflaechen und 45 aus den handgepflegten Listen fuer Vergabestelle
und Region; 7 kommen in beidem vor.

## Je Produktflaeche

| Flaeche | Kennzahlen | Tabelle |
|---|---:|---|
| Lead (Auslauf-Radar) | 29 | `leads.parquet` |
| Lead-Detail | 39 | `lead_detail.parquet` |
| Marktchancen | 18 | `market_opportunity.parquet` |
| Anbieterprofil | 6 | `contractor_stats.parquet` |
| Vergabestelle | 8 | `buyer_stats.parquet` |
| Vorgangsakte | 14 | `vorgaenge.parquet` |
| Vergabekette | 9 | `vorgang_kette.parquet` |
| Dokumentenanalyse | 19 | `doc_analysis.parquet` |
| Anlaufvergleich | — | `anlauf_vergleich.parquet` (noch nicht gebaut) |

## Je handgepflegter Liste

| Liste | Kennzahlen |
|---|---:|
| [kpi-buyer-profile.md](kpi-buyer-profile.md) | 29 |
| [kpi-region-und-kontext.md](kpi-region-und-kontext.md) | 22 |

## Alle Kennzahlen, alphabetisch

- `active_years` · `also_below_threshold` · `ampel` · `ampel_grund`
- `auftraege_je_1000_ew` · `avg_bidders` · `avg_decision_days` · `awards_per_year_recent`
- `band_effektiv` · `bau_beschaeftigte` · `bau_umsatz_eur` · `baubetriebe`
- `bevoelkerung` · `bidder_bucket` · `bieter_plausibel` · `branche`
- `buyer_entity` · `cal_offset_days` · `cal_spread_days` · `chronic_needs`
- `competition_flag` · `concentration` · `contract_end` · `contract_end_cal`
- `contract_end_eff` · `contract_kind` · `dauerangebot` · `deadline_date`
- `decision_days_coverage` · `displ_band` · `displaceability` · `distinct_contractors`
- `duration_days_eff` · `erfolglos_pct` · `erste_veroeffentlichung` · `faellig_basis`
- `first_year` · `genehmigungen_gesamt` · `glieder_pro_jahr` · `has_renewal`
- `hat_unterlagen` · `hhi` · `incumbent_entity` · `incumbent_since_year`
- `intensitaet_pct` · `investition_je_kopf_eur` · `investitionen_eur` · `is_enriched`
- `ist_hauptlos` · `jahr` · `konfidenz_zum_vorgaenger` · `kreis_finanzen_jahr`
- `kreis_investitionen_eur` · `last_award_year` · `letzte_veroeffentlichung` · `lose_im_cluster`
- `market_rank` · `market_share_by_wins` · `max_fail_years` · `max_renewals`
- `median_award_eur` · `median_value` · `methode` · `min_konfidenz`
- `months_to_expiry` · `n_anforderungen` · `n_angedockt` · `n_aufwand`
- `n_ausschreibung` · `n_awards` · `n_bekanntmachungen` · `n_categories`
- `n_checklist` · `n_contractors` · `n_distinct_winners` · `n_doctypes`
- `n_dokumente` · `n_dubletten` · `n_eignung` · `n_erfolglos`
- `n_fristen` · `n_glieder` · `n_ko_kriterien` · `n_korrektur`
- `n_missing_expected` · `n_offen` · `n_parsed_files` · `n_positions`
- `n_truncated` · `n_vergabestellen` · `n_vergeben` · `n_verschmolzen`
- `n_vorinfo` · `n_zuschlag` · `num_tenders` · `population`
- `position` · `reachable` · `rej_beleg` · `rej_schema`
- `rej_typ` · `rejected_items` · `retention_rate` · `schulden_je_kopf_eur`
- `score_basis` · `score_driver` · `sector` · `segment_label`
- `single_bidder` · `single_bidder_pct` · `single_bidder_rate` · `source`
- `struktur` · `sv_beschaeftigte` · `tenure_years` · `termin_plausibel`
- `token_cost` · `top3_share` · `top_contractors` · `top_cpvs`
- `top_division_label` · `top_dominators` · `top_winners` · `total_awards`
- `total_value_known` · `total_volume_known` · `total_wins` · `trend_yoy`
- `value_band` · `value_clean` · `value_coverage` · `value_effektiv`
- `value_eur` · `value_real_2020` · `value_used` · `vergabe_datum`
- `vollstaendig` · `volume_coverage` · `volume_known_eur` · `volumen_2023_eur`
- `volumen_coverage` · `vorgaenger` · `website` · `wert_umgerechnet`
- `window_end` · `window_start` · `window_years` · `winner`
- `zusammenfassung`
