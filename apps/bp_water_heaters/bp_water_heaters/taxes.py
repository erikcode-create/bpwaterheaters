from __future__ import annotations

from dataclasses import dataclass


NEVADA_SOURCE_URL = "https://tax.nv.gov/tax-types/sales-tax-use-tax/"
CALIFORNIA_SOURCE_URL = "https://cdtfa.ca.gov/taxes-and-fees/sales-use-tax-rates.htm/"

NEVADA_COUNTY_RATES = {
	"carson city": ("NV Carson City Sales Tax - BPWH", 7.60),
	"churchill": ("NV Churchill Sales Tax - BPWH", 7.60),
	"clark": ("NV Clark Sales Tax - BPWH", 8.375),
	"douglas": ("NV Douglas Sales Tax - BPWH", 7.10),
	"elko": ("NV Elko Sales Tax - BPWH", 7.10),
	"lander": ("NV Lander Sales Tax - BPWH", 7.10),
	"lincoln": ("NV Lincoln Sales Tax - BPWH", 7.10),
	"lyon": ("NV Lyon Sales Tax - BPWH", 7.10),
	"nye": ("NV Nye Sales Tax - BPWH", 7.60),
	"pershing": ("NV Pershing Sales Tax - BPWH", 7.10),
	"storey": ("NV Storey Sales Tax - BPWH", 7.60),
	"washoe": ("NV Washoe Sales Tax - BPWH", 8.265),
	"white pine": ("NV White Pine Sales Tax - BPWH", 7.725),
}

NEVADA_CITY_COUNTY = {
	"reno": "washoe",
	"sparks": "washoe",
	"incline village": "washoe",
	"carson city": "carson city",
	"minden": "douglas",
	"gardnerville": "douglas",
	"dayton": "lyon",
	"fernley": "lyon",
	"fallon": "churchill",
	"elko": "elko",
	"las vegas": "clark",
	"henderson": "clark",
	"north las vegas": "clark",
}


@dataclass(frozen=True)
class TaxRule:
	template_name: str
	rate: float
	source_url: str
	jurisdiction: str


def select_tax_rule(state: str, city: str | None = None, county: str | None = None) -> TaxRule:
	normalized_state = state.strip().upper()
	if normalized_state == "NV":
		county_key = _normalize(county) or NEVADA_CITY_COUNTY.get(_normalize(city))
		template_name, rate = NEVADA_COUNTY_RATES.get(county_key, ("NV State Base Sales Tax - BPWH", 6.85))
		return TaxRule(template_name, rate, NEVADA_SOURCE_URL, county_key or "Nevada base")

	if normalized_state == "CA":
		return TaxRule("CA Statewide Sales Tax - BPWH", 7.25, CALIFORNIA_SOURCE_URL, "California statewide")

	return TaxRule("Out of Area Sales Tax - BPWH", 0.0, "", "Out of area")


def _normalize(value: str | None) -> str:
	return (value or "").strip().lower()
