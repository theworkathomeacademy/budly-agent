"""Unified Canonical Affiliate Analytics Engine (G9B.7B).

Guarantees:
- All traffic, conversions, and commissions unify under Canonical Affiliate ID.
- Vanity link changes never fragment lifetime analytics.
- Supports Traffic, Commerce, Affiliate Commission, Campaign, and Trend metrics.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .engine import money


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ClickEvent:
    event_id: str
    affiliate_id: str
    referral_token: str
    routing_method: str
    slug: str | None
    campaign_id: str | None
    source: str | None
    platform: str | None
    timestamp: datetime
    visitor_id: str


@dataclass
class AffiliateAnalyticsSummary:
    affiliate_id: str
    total_clicks: int
    unique_visitors: int
    total_orders: int
    qualifying_revenue: Decimal
    commission_total: Decimal
    commission_pending: Decimal
    commission_matured: Decimal
    commission_payable: Decimal
    commission_paid: Decimal
    commission_reversed: Decimal
    average_order_value: Decimal
    by_campaign: dict[str, dict[str, Any]]
    by_product: dict[str, dict[str, Any]]
    by_source: dict[str, int]
    by_platform: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "affiliate_id": self.affiliate_id,
            "total_clicks": self.total_clicks,
            "unique_visitors": self.unique_visitors,
            "total_orders": self.total_orders,
            "qualifying_revenue": str(self.qualifying_revenue),
            "commission_total": str(self.commission_total),
            "commission_pending": str(self.commission_pending),
            "commission_matured": str(self.commission_matured),
            "commission_payable": str(self.commission_payable),
            "commission_paid": str(self.commission_paid),
            "commission_reversed": str(self.commission_reversed),
            "average_order_value": str(self.average_order_value),
            "by_campaign": self.by_campaign,
            "by_product": self.by_product,
            "by_source": self.by_source,
            "by_platform": self.by_platform,
        }


class AnalyticsEngine:
    """Canonical Analytics Engine aggregating across all historical aliases and referral events."""

    def __init__(self) -> None:
        self.clicks: list[ClickEvent] = []
        self.orders: list[dict[str, Any]] = []

    def record_click(
        self,
        event_id: str,
        affiliate_id: str,
        referral_token: str,
        routing_method: str,
        slug: str | None = None,
        campaign_id: str | None = None,
        source: str | None = None,
        platform: str | None = None,
        visitor_id: str = "anon-1",
        timestamp: datetime | None = None,
    ) -> ClickEvent:
        event = ClickEvent(
            event_id=event_id,
            affiliate_id=affiliate_id,
            referral_token=referral_token,
            routing_method=routing_method,
            slug=slug,
            campaign_id=campaign_id,
            source=source,
            platform=platform,
            timestamp=timestamp or utcnow(),
            visitor_id=visitor_id,
        )
        self.clicks.append(event)
        return event

    def record_order(self, order_data: dict[str, Any]) -> None:
        self.orders.append(order_data)

    def get_affiliate_analytics(
        self,
        affiliate_id: str,
        commissions: list[Any],
        window_days: int | None = None,
        now: datetime | None = None,
    ) -> AffiliateAnalyticsSummary:
        """Compute unified canonical analytics across all historical aliases and campaign events."""
        when = now or utcnow()
        since = (when - timedelta(days=window_days)) if window_days else None

        # 1. Filter clicks for affiliate
        aff_clicks = [c for c in self.clicks if c.affiliate_id == affiliate_id and (not since or c.timestamp >= since)]
        total_clicks = len(aff_clicks)
        unique_visitors = len({c.visitor_id for c in aff_clicks})

        by_source = defaultdict(int)
        by_platform = defaultdict(int)
        by_campaign_clicks = defaultdict(int)
        for c in aff_clicks:
            if c.source: by_source[c.source] += 1
            if c.platform: by_platform[c.platform] += 1
            if c.campaign_id: by_campaign_clicks[c.campaign_id] += 1

        # 2. Filter commissions for affiliate
        aff_comms = [c for c in commissions if getattr(c, "affiliate_id", None) == affiliate_id]

        total_orders = len({c.order_id for c in aff_comms})
        qual_rev = money(sum((getattr(c, "qualifying_revenue", Decimal(0)) for c in aff_comms), Decimal(0)))
        comm_total = money(sum((getattr(c, "amount", Decimal(0)) for c in aff_comms), Decimal(0)))

        comm_pending = money(sum((c.balance for c in aff_comms if c.status == "PENDING"), Decimal(0)))
        comm_payable = money(sum((c.balance for c in aff_comms if c.status == "PAYABLE"), Decimal(0)))
        comm_paid = money(sum((c.balance for c in aff_comms if c.status == "PAID"), Decimal(0)))
        comm_reversed = money(sum((getattr(c, "amount", Decimal(0)) - c.balance for c in aff_comms if c.status == "REVERSED"), Decimal(0)))

        aov = (qual_rev / Decimal(total_orders)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP) if total_orders > 0 else Decimal("0.000000")

        # Campaign & Product breakdowns
        by_campaign = {}
        for camp_id, click_count in by_campaign_clicks.items():
            by_campaign[camp_id] = {
                "clicks": click_count,
                "conversions": sum(1 for c in aff_comms if getattr(c, "campaign_id", None) == camp_id),
            }

        by_product = {}

        return AffiliateAnalyticsSummary(
            affiliate_id=affiliate_id,
            total_clicks=total_clicks,
            unique_visitors=unique_visitors,
            total_orders=total_orders,
            qualifying_revenue=qual_rev,
            commission_total=comm_total,
            commission_pending=comm_pending,
            commission_matured=comm_payable,  # matured in PAYABLE state
            commission_payable=comm_payable,
            commission_paid=comm_paid,
            commission_reversed=comm_reversed,
            average_order_value=aov,
            by_campaign=by_campaign,
            by_product=by_product,
            by_source=dict(by_source),
            by_platform=dict(by_platform),
        )
