"""Approved synthetic company facts for deterministic customer-facing lookup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

CompanyFact = Literal["overview", "location", "hours", "inquiry_channels", "fulfillment"]


@dataclass(frozen=True)
class CompanyFactResult:
    fact: CompanyFact
    value: str


class CompanyInfoService:
    """Return approved demo facts without relying on model-generated business content."""

    _facts: dict[CompanyFact, str] = {
        "overview": "BioMedicHospicare is a synthetic medical-supply portfolio demonstration.",
        "location": "Cali, Colombia (fictional demonstration location).",
        "hours": (
            "In this demo, Saturday hours are 9:00 AM–1:00 PM Colombia time; "
            "real availability is not confirmed."
        ),
        "inquiry_channels": (
            "Synthetic quotation and support inquiries are available in this demonstration."
        ),
        "fulfillment": (
            "Delivery-city inquiries and fictional Cali pickup are demonstration options only."
        ),
    }

    async def get_fact(self, *, fact: CompanyFact) -> CompanyFactResult:
        return CompanyFactResult(fact=fact, value=self._facts[fact])
