"""Attribution Link Standard for Budly Social-to-Sale Conversion Spine (STS-1)."""

from __future__ import annotations

import hashlib
import re
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Any

# Allowed characters for standard identifiers (prevent PII / secrets / script injection)
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-\.]{1,80}$")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}")
PHONE_PATTERN = re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b")

# Approved base domains / routes in ecosystem
APPROVED_ROUTES = {
    "ask_budly": "https://www.wakenbakelounge.com/ask-budly",
    "ask_budly_shop": "https://cccultivate.com/ask-budly/",
    "brand_home": "https://www.wakenbakelounge.com/",
    "shop_catalog": "https://cccultivate.com/shop/",
}


@dataclass(frozen=True)
class AttributionContext:
    source: str
    platform: str
    content_id: str
    campaign_id: str
    cta_id: str
    product_or_topic: str = "UNKNOWN"
    published_post_id: str = ""

    def validate(self) -> None:
        for field_name, value in asdict(self).items():
            if value:
                if EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value):
                    raise ValueError(f"Attribution field '{field_name}' must never contain PII")
                if len(value) > 120:
                    raise ValueError(f"Attribution field '{field_name}' exceeds maximum length of 120 characters")

    @property
    def is_empty(self) -> bool:
        return not any([
            self.source, self.platform, self.content_id,
            self.campaign_id, self.cta_id, self.published_post_id
        ])

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def direct(cls) -> "AttributionContext":
        return cls(
            source="direct",
            platform="web",
            content_id="",
            campaign_id="",
            cta_id="CTA-ASK-BUDLY-001",
            product_or_topic="GENERAL_CONVERSATION",
            published_post_id="",
        )


class AttributionStandard:
    @staticmethod
    def clean_param(value: Any, max_length: int = 80) -> str:
        if value is None:
            return ""
        val = str(value).strip()
        # Remove PII if present
        if EMAIL_PATTERN.search(val) or PHONE_PATTERN.search(val):
            return ""
        # Keep only safe identifier characters
        cleaned = re.sub(r"[^A-Za-z0-9_\-\.]", "", val)
        return cleaned[:max_length]

    @classmethod
    def build_url(
        cls,
        base_url: str,
        context: AttributionContext,
        additional_params: dict[str, str] | None = None,
    ) -> str:
        context.validate()
        params: dict[str, str] = {
            "source": cls.clean_param(context.source),
            "platform": cls.clean_param(context.platform),
            "content_id": cls.clean_param(context.content_id),
            "campaign_id": cls.clean_param(context.campaign_id),
            "cta_id": cls.clean_param(context.cta_id),
        }
        if context.product_or_topic and context.product_or_topic != "UNKNOWN":
            params["product_or_topic"] = cls.clean_param(context.product_or_topic)
        if context.published_post_id:
            params["published_post_id"] = cls.clean_param(context.published_post_id)

        if additional_params:
            for k, v in additional_params.items():
                params[cls.clean_param(k)] = cls.clean_param(v)

        # Filter empty params
        filtered = {k: v for k, v in params.items() if v}
        query_str = urllib.parse.urlencode(filtered)
        separator = "&" if "?" in base_url else "?"
        return f"{base_url}{separator}{query_str}" if query_str else base_url

    @classmethod
    def parse_query_params(cls, params: dict[str, Any]) -> AttributionContext:
        source = cls.clean_param(params.get("source")) or "direct"
        platform = cls.clean_param(params.get("platform")) or "web"
        content_id = cls.clean_param(params.get("content_id"))
        campaign_id = cls.clean_param(params.get("campaign_id"))
        cta_id = cls.clean_param(params.get("cta_id")) or "CTA-ASK-BUDLY-001"
        product_or_topic = cls.clean_param(params.get("product_or_topic")) or "UNKNOWN"
        published_post_id = cls.clean_param(params.get("published_post_id"))

        ctx = AttributionContext(
            source=source,
            platform=platform,
            content_id=content_id,
            campaign_id=campaign_id,
            cta_id=cta_id,
            product_or_topic=product_or_topic,
            published_post_id=published_post_id,
        )
        ctx.validate()
        return ctx

    @classmethod
    def parse_url(cls, url: str) -> tuple[str, AttributionContext]:
        parsed = urllib.parse.urlparse(url)
        query_dict = urllib.parse.parse_qs(parsed.query)
        flat_dict = {k: v[0] for k, v in query_dict.items() if v}
        landing_route = f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme else parsed.path
        return landing_route, cls.parse_query_params(flat_dict)

    @staticmethod
    def generate_idempotency_key(session_id: str, content_id: str, cta_id: str) -> str:
        payload = f"{session_id}:{content_id}:{cta_id}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
