"""NSE/BSE Shareholding Pattern (SHP) XBRL parser.

NSE hosts SHP XBRL instances under `https://nsearchives.nseindia.com/corporate/xbrl/`.
These files use the namespace prefix `in-bse-shp` (BSE taxonomy) and XBRL Dimensions.

This module extracts a normalized summary:
- promoter_pct
- public_pct
- fii_pct (Foreign portfolio investors; derived)
- dii_pct (Domestic institutions; derived)
- total_shareholders
- total_shares
- period_end (best-effort)

Important:
- The XBRL expresses percentages as fractions (e.g. 0.623 == 62.3%).
- Context IDs are fairly stable and include buckets like:
  - ShareholdingOfPromoterAndPromoterGroup_ContextI
  - PublicShareholding_ContextI
  - InstitutionsForeignPortfolioInvestorCategoryOne_ContextI
  - InstitutionsForeignPortfolioInvestorCategoryTwo_ContextI
  - InstitutionsDomestic_ContextI

If some contexts are missing, the parser falls back to roll-up contexts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from typing import Any, Dict, Optional
import xml.etree.ElementTree as ET


_XBRLI_NS = "http://www.xbrl.org/2003/instance"
_XBRLDI_NS = "http://xbrl.org/2006/xbrldi"


@dataclass(frozen=True)
class ShareholdingSummary:
    promoter_pct: Optional[float]
    public_pct: Optional[float]
    fii_pct: Optional[float]
    dii_pct: Optional[float]
    total_shareholders: Optional[int]
    total_shares: Optional[int]
    period_end: Optional[date]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "promoter_pct": self.promoter_pct,
            "public_pct": self.public_pct,
            "fii_pct": self.fii_pct,
            "dii_pct": self.dii_pct,
            "total_shareholders": self.total_shareholders,
            "total_shares": self.total_shares,
            "period_end": self.period_end.isoformat() if self.period_end else None,
        }


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _first_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _first_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_period_end(root: ET.Element) -> Optional[date]:
    """Best-effort: look for xbrli:period/xbrli:endDate in any context."""
    # Try a context that looks like *_ContextI first, else any context.
    ctxs = root.findall(f".//{{{_XBRLI_NS}}}context")
    for preferred in (True, False):
        for ctx in ctxs:
            cid = ctx.attrib.get("id", "")
            if preferred and not cid.endswith("_ContextI"):
                continue
            end = ctx.find(f".//{{{_XBRLI_NS}}}period/{{{_XBRLI_NS}}}endDate")
            if end is not None and end.text:
                try:
                    y, m, d = map(int, end.text.strip().split("-")[:3])
                    return date(y, m, d)
                except Exception:
                    continue
    return None


def parse_shp_xbrl(xml_bytes: bytes) -> ShareholdingSummary:
    """Parse an SHP XBRL instance into a normalized summary.

    Percent fields are returned as *fractions* (0..1), not 0..100.
    """

    root = ET.fromstring(xml_bytes)

    wanted = {
        "ShareholdingAsAPercentageOfTotalNumberOfShares",
        "NumberOfShareholders",
        "NumberOfShares",
        "NumberOfFullyPaidUpEquityShares",
    }

    ctx_facts: Dict[str, Dict[str, Any]] = {}
    for el in root.iter():
        ln = _local(el.tag)
        if ln not in wanted:
            continue
        ctx = el.attrib.get("contextRef")
        if not ctx or el.text is None:
            continue
        val = el.text.strip()
        if ln == "ShareholdingAsAPercentageOfTotalNumberOfShares":
            ctx_facts.setdefault(ctx, {})[ln] = _first_float(val)
        else:
            ctx_facts.setdefault(ctx, {})[ln] = _first_int(val)

    def pct(ctx: str) -> Optional[float]:
        return ctx_facts.get(ctx, {}).get("ShareholdingAsAPercentageOfTotalNumberOfShares")

    def shareholders(ctx: str) -> Optional[int]:
        return ctx_facts.get(ctx, {}).get("NumberOfShareholders")

    def shares(ctx: str) -> Optional[int]:
        d = ctx_facts.get(ctx, {})
        return d.get("NumberOfFullyPaidUpEquityShares") or d.get("NumberOfShares")

    # Stable context IDs for roll-ups
    prom_ctx = "ShareholdingOfPromoterAndPromoterGroup_ContextI"
    public_ctx = "PublicShareholding_ContextI"
    inst_foreign_ctx = "InstitutionsForeign_ContextI"
    inst_dom_ctx = "InstitutionsDomestic_ContextI"

    fpi1_ctx = "InstitutionsForeignPortfolioInvestorCategoryOne_ContextI"
    fpi2_ctx = "InstitutionsForeignPortfolioInvestorCategoryTwo_ContextI"

    promoter_pct = pct(prom_ctx)
    public_pct = pct(public_ctx)

    # FII/FPI derived: prefer Cat1+Cat2, else roll-up InstitutionsForeign
    fpi1 = pct(fpi1_ctx)
    fpi2 = pct(fpi2_ctx)
    fii_pct = (fpi1 or 0.0) + (fpi2 or 0.0)
    if (fpi1 is None and fpi2 is None) or fii_pct == 0.0:
        fii_pct = pct(inst_foreign_ctx)

    # DII derived: roll-up InstitutionsDomestic
    dii_pct = pct(inst_dom_ctx)

    # Totals best-effort:
    # - total_shares: shares from promoter ctx is usually total equity shares in that class
    # - total_shareholders: sum promoter + public if available (promoter shareholders are small;
    #   this aligns with what you asked: total number of shareholders)
    total_shares = shares(prom_ctx) or shares(public_ctx)

    sh_prom = shareholders(prom_ctx)
    sh_pub = shareholders(public_ctx)
    total_shareholders = None
    if sh_prom is not None or sh_pub is not None:
        total_shareholders = (sh_prom or 0) + (sh_pub or 0)

    period_end = _parse_period_end(root)

    return ShareholdingSummary(
        promoter_pct=promoter_pct,
        public_pct=public_pct,
        fii_pct=fii_pct,
        dii_pct=dii_pct,
        total_shareholders=total_shareholders,
        total_shares=total_shares,
        period_end=period_end,
    )


def guess_symbol_from_filename(filename: str) -> Optional[str]:
    """Best-effort helper: some SHP filenames don't include symbol. Returns None."""
    # Most SHP filenames are like SHP_<numeric>_<timestamp>_WEB.xml
    # so we usually can't infer symbol.
    m = re.search(r"\b([A-Z]{2,15})\b", filename)
    if m:
        return m.group(1)
    return None
