from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

LEVERS = ("price", "ads", "promotion", "restock")

# Public calendar, intentionally modest. Reality can still be marked as a confounder.
SEASONAL = [1.0] * 52
for week, value in {
    3: 1.04, 4: 1.08, 11: 1.06, 12: 1.10, 13: 1.18, 14: 1.30,
    15: 1.42, 16: 1.15, 17: .95, 18: 1.08, 19: 1.10, 20: 1.10,
    21: 1.08, 24: 1.15, 25: 1.10, 26: .93, 27: .92, 28: .92,
    29: .94, 31: 1.18, 34: 1.08, 40: .94, 41: .93, 42: .93,
    43: .93, 44: .93, 45: .93, 46: .93, 47: .94,
}.items():
    SEASONAL[week] = value


@dataclass
class Group:
    key: str
    name: str
    base_units: float
    price: float
    cogs: float
    ad_share: float
    ad_spend: float
    supplier: str
    safety_weeks: float = 1.5
    control: bool = False

    @property
    def margin(self) -> float:
        return self.price - self.cogs


@dataclass
class Partner:
    key: str
    name: str
    type: str
    promised_days: float


@dataclass
class Business:
    name: str
    groups: list[Group]
    partners: list[Partner]
    cash0: float
    fixed_weekly: float
    cod_share: float
    courier_key: str
    start_date: str = "2025-07-07"
    reorder_every: int = 2
    seasonal: list[float] = field(default_factory=lambda: list(SEASONAL))

    def group(self, key: str) -> Group:
        return next(g for g in self.groups if g.key == key)

    def partner(self, key: str) -> Partner:
        return next(p for p in self.partners if p.key == key)

    def season(self, week: int) -> float:
        return self.seasonal[week % len(self.seasonal)]

    def week_date(self, week: int) -> date:
        return date.fromisoformat(self.start_date) + timedelta(days=week * 7)

    @property
    def monthly_revenue(self) -> float:
        return sum(g.base_units * g.price for g in self.groups) * 52 / 12

    @property
    def gross_margin(self) -> float:
        revenue = sum(g.base_units * g.price for g in self.groups)
        return sum(g.base_units * g.margin for g in self.groups) / revenue

    @property
    def monthly_ad_spend(self) -> float:
        return sum(g.ad_spend for g in self.groups) * 52 / 12

    @property
    def monthly_fixed(self) -> float:
        return self.fixed_weekly * 52 / 12

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Business":
        return cls(
            name=raw["name"], groups=[Group(**x) for x in raw["groups"]],
            partners=[Partner(**x) for x in raw["partners"]], cash0=raw["cash0"],
            fixed_weekly=raw["fixed_weekly"], cod_share=raw["cod_share"],
            courier_key=raw["courier_key"], start_date=raw.get("start_date", "2025-07-07"),
            reorder_every=raw.get("reorder_every", 2), seasonal=raw.get("seasonal", list(SEASONAL)),
        )

    def rescale(self, revenue: float | None = None, margin: float | None = None,
                cash: float | None = None, fixed: float | None = None, ads: float | None = None) -> None:
        if revenue and revenue > 0:
            factor = revenue / self.monthly_revenue
            for group in self.groups:
                group.base_units *= factor
        if margin and .05 < margin < .95:
            target_cogs = sum(g.base_units * g.price for g in self.groups) * (1 - margin)
            old_cogs = sum(g.base_units * g.cogs for g in self.groups)
            for group in self.groups:
                group.cogs *= target_cogs / old_cogs
        if cash is not None and cash >= 0:
            self.cash0 = cash
        if fixed is not None and fixed >= 0:
            self.fixed_weekly = fixed * 12 / 52
        if ads is not None and ads >= 0 and self.monthly_ad_spend:
            factor = ads / self.monthly_ad_spend
            for group in self.groups:
                group.ad_spend *= factor


def demo_business() -> Business:
    return Business(
        name="Lumen & Wick Candle Co.",
        groups=[
            Group("premium", "Premium Collection", 80, 1500, 600, .30, 25000, "rajan-jars"),
            Group("core", "Core Range", 410, 550, 240, .35, 44000, "aarav-waxworks"),
            Group("gifting", "Gift Sets & Accessories", 130, 400, 160, .10, 4000, "packwell", control=True),
        ],
        partners=[
            Partner("rajan-jars", "Rajan Jars", "supplier", 10),
            Partner("aarav-waxworks", "Aarav Waxworks", "supplier", 7),
            Partner("packwell", "PackWell Packaging", "supplier", 5),
            Partner("inklane", "InkLane Printers", "other", 4),
            Partner("speedy-courier", "Speedy Courier", "courier", 7),
        ],
        cash0=400000, fixed_weekly=95000, cod_share=.45, courier_key="speedy-courier",
    )
