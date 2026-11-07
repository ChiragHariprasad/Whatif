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
    29: .94, 31: 1.18, 34: 1.08, 40: .94, 41: .93,
    42: 1.35, 43: 1.55, 44: 1.70, 45: 1.25, 46: .88, 47: .85,
}.items():
    SEASONAL[week] = value

# These worlds do not share the consumer-gifting demand curve. Keep the
# definitions explicit so a future world cannot accidentally inherit it.
B2B_SEASONAL = [1.0] * 52
for week, value in {20: .94, 21: .94, 50: .86, 51: .82}.items():
    B2B_SEASONAL[week] = value

CAFE_SEASONAL = [1.0] * 52
for week, value in {23: .94, 24: .91, 25: .89, 26: .90, 27: .93, 42: 1.07, 43: 1.09, 44: 1.06}.items():
    CAFE_SEASONAL[week] = value


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
    # Generalises COD timing to invoices and platform payouts. cod_share is
    # retained for backwards-compatible persisted worlds.
    delayed_receipts_share: float | None = None
    currency_symbol: str = "₹"
    locale: str = "en-IN"
    start_date: str = "2025-07-07"
    reorder_every: int = 2
    seasonal: list[float] = field(default_factory=lambda: list(SEASONAL))

    @property
    def receipt_delay_share(self) -> float:
        return max(0.0, min(1.0, self.cod_share if self.delayed_receipts_share is None else self.delayed_receipts_share))

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
            fixed_weekly=raw["fixed_weekly"], cod_share=raw.get("cod_share", 0.0),
            courier_key=raw["courier_key"], delayed_receipts_share=raw.get("delayed_receipts_share"),
            currency_symbol=raw.get("currency_symbol", "₹"), locale=raw.get("locale", "en-IN"),
            start_date=raw.get("start_date", "2025-07-07"),
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
    return ember_wick_business()


def ember_wick_business() -> Business:
    return Business(
        name="Ember & Wick Candle Co.",
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
        cash0=120000, fixed_weekly=95000, cod_share=.45, courier_key="speedy-courier",
    )


def northlight_studio_business() -> Business:
    return Business(
        name="Northlight Studio",
        groups=[
            Group("retainers", "Retainer Clients", 6, 450000, 180000, .20, 40000, "apex-digital"),
            Group("projects", "Fixed-Price Projects", 4, 450000, 220000, .80, 80000, "devcraft-contractors"),
        ],
        partners=[
            Partner("apex-digital", "Apex Digital (Client)", "courier", 30),
            Partner("scaleco", "ScaleCo (Client)", "courier", 30),
            Partner("devcraft-contractors", "DevCraft Contractors", "supplier", 7),
        ],
        cash0=350000, fixed_weekly=280000, cod_share=0.0, courier_key="apex-digital",
        delayed_receipts_share=1.0, seasonal=list(B2B_SEASONAL),
    )


def brew_lane_cafe_business() -> Business:
    return Business(
        name="Brew Lane Café",
        groups=[
            Group("dine_in", "Dine-in Service", 1200, 380, 190, .40, 20000, "freshfarms-produce"),
            Group("delivery", "Delivery Orders", 850, 420, 220, .60, 30000, "app-payouts"),
        ],
        partners=[
            Partner("freshfarms-produce", "FreshFarms Produce", "supplier", 1),
            Partner("dairydirect", "DairyDirect", "supplier", 2),
            Partner("app-payouts", "Delivery App Payouts", "courier", 7),
        ],
        cash0=180000, fixed_weekly=210000, cod_share=0.0, courier_key="app-payouts",
        delayed_receipts_share=.45, seasonal=list(CAFE_SEASONAL),
    )


def get_business_world(key: str) -> Business:
    k = key.lower()
    if "agency" in k or "northlight" in k: return northlight_studio_business()
    if "cafe" in k or "brew" in k: return brew_lane_cafe_business()
    return ember_wick_business()
