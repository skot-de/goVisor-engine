"""Preismodell: 7-Band-Pauschalen-Staffel + Unsicherheits-Rabatt."""
from govisor import pricing


def test_flat_per_band_ignores_exact_value():
    # Pauschale haengt NUR am Band, nicht am exakten Wert (das ist der Kern-Punkt).
    assert pricing.fee("250-500k", "echt", 260_000) == 2_400
    assert pricing.fee("250-500k", "echt", 490_000) == 2_400
    assert pricing.fee("500k-1,3M", "echt", 600_000) == 4_800
    assert pricing.fee("500k-1,3M", "echt", 1_200_000) == 4_800


def test_all_seven_bands():
    exp = {"<100k": 600, "100-250k": 1_200, "250-500k": 2_400, "500k-1,3M": 4_800,
           "1,3-5M": 9_600, "5-25M": 15_000, ">25M": 25_000}
    for band, amount in exp.items():
        assert pricing.fee(band, "echt", None) == amount


def test_uncertainty_discount_on_imputed_and_default():
    assert pricing.fee("1,3-5M", "imputiert", None) == round(9_600 * 0.8)   # 7680
    assert pricing.fee("250-500k", "default", None) == round(2_400 * 0.8)   # 1920
    # echt/geschaetzt bekommen KEINEN Rabatt
    assert pricing.fee("250-500k", "echt", 300_000) == 2_400
    assert pricing.fee("250-500k", "geschaetzt", 300_000) == 2_400


def test_unknown_band_is_zero():
    assert pricing.fee("unbekannt", "echt", None) == 0
    assert pricing.fee("nonsense", "echt", 100) == 0
