"""Pipeline configuration.

Country is a parameter everywhere, never a constant. The initial scope is DE,
but nothing below the config layer knows that: ``--country DE FR`` is the whole
change needed to widen it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import countries

DEFAULT_COUNTRIES = ("DE",)


@dataclass
class Config:
    countries: tuple[str, ...] = DEFAULT_COUNTRIES
    data_dir: Path = Path("data")

    def __post_init__(self) -> None:
        self.countries = tuple(countries.normalize(c) for c in self.countries)
        self.data_dir = Path(self.data_dir)

    @property
    def cache_dir(self) -> Path:
        """Downloaded packages. Disposable — re-fetchable from TED."""
        return self.data_dir / "cache"

    @property
    def raw_dir(self) -> Path:
        """Country-filtered original XML. Never modified after ingest."""
        return self.data_dir / "raw"

    @property
    def index_dir(self) -> Path:
        """Parsed summaries, regenerable from raw_dir without re-downloading."""
        return self.data_dir / "index"

    @property
    def silver_dir(self) -> Path:
        """Lossless Parquet, regenerable from raw_dir. What DuckDB queries."""
        return self.data_dir / "silver"

    def raw_path(self, country: str, key: str) -> Path:
        return self.raw_dir / country / f"{key}.tar.gz"

    def index_path(self, country: str, key: str) -> Path:
        return self.index_dir / country / f"{key}.jsonl.gz"

    @property
    def curated_dir(self) -> Path:
        """Von Hand gepflegte Quellen — überleben jeden Rebuild (nicht abgeleitet)."""
        return self.data_dir / "curated"

    def group_csv(self, country: str) -> Path:
        return self.curated_dir / f"{country}_company_groups.csv"

    @property
    def gold_dir(self) -> Path:
        """Serving-Ebene: Verfahren und Entitäten, aus Silber abgeleitet."""
        return self.data_dir / "gold"

    @property
    def review_dir(self) -> Path:
        """Zweifelsfälle zur Nachbearbeitung — mit Original-XML als Beleg."""
        return self.data_dir / "review"

    def review_path(self, key: str) -> Path:
        return self.review_dir / f"{key}.jsonl.gz"

    def review_raw_path(self, key: str) -> Path:
        return self.review_dir / f"{key}.tar.gz"

    def silver_table_path(self, table: str, country: str, key: str) -> Path:
        year = key.split("-")[0]
        return self.silver_dir / country / table / f"year={year}" / f"{key}.parquet"

    def silver_table_glob(self, table: str, country: str) -> str:
        return str(self.silver_dir / country / table / "*" / "*.parquet")
