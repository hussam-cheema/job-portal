"""Reviewed PBS survey snapshot and conservative website-only classifications."""
from copy import deepcopy
from collections import Counter

from app.constants import PAKISTAN_ALL_CITIES, PAKISTAN_PROVINCES, PAKISTAN_CITIES
from app.utils import as_list

SOURCE = "https://www.pbs.gov.pk/wp-content/uploads/2020/07/LFS-2024-25-Annual-Report.pdf"
PBS_EMPLOYMENT = {
    "dataset_id": "pbs-lfs-2024-25-19th-icls-v1",
    "period": "2024-25", "verified_at": "2026-09-09",
    "provider": "Pakistan Bureau of Statistics · Labour Force Survey",
    "definition": "Employed persons aged 10 and over, 19th ICLS framework. Survey estimates, not vacancies or monthly hiring.",
    "source_url": SOURCE,
    "occupations": {
        "unit": "% of employed persons", "table": "4.7", "page": 43,
        "source_url": SOURCE + "#page=77",
        "items": [
            {"name": name, "value": value} for name, value in [
                ("Managers", 2.3), ("Professionals", 6.1),
                ("Technicians & associate professionals", 4.4),
                ("Clerical support workers", 1.8), ("Service and sales workers", 17.2),
                ("Skilled agricultural, forestry & fishery workers", 28.0),
                ("Craft & related trades workers", 13.7),
                ("Plant/machine operators & assemblers", 8.3), ("Elementary occupations", 18.3),
            ]
        ],
    },
    "provinces": {
        "unit": "million employed persons", "table": "4.1", "page": 37,
        "source_url": SOURCE + "#page=71", "pakistan_total": 77.2,
        "items": [{"name": name, "value": value} for name, value in [
            ("Punjab", 44.7), ("Sindh", 17.5), ("Khyber Pakhtunkhwa", 11.3), ("Balochistan", 3.8),
        ]],
    },
    "notes": "Published rounded values are preserved: occupation shares sum to 100.1%, and provincial counts to 77.3 million versus the published Pakistan total of 77.2 million. This table reports four provinces; no separate estimates are supplied here for ICT, AJK or Gilgit-Baltistan. Reviewed survey data is versioned, not presented as live monthly data.",
}


def national_breakdowns():
    return deepcopy(PBS_EMPLOYMENT)


# Only explicit occupational categories are mapped. Government/private, employer
# names and broad industries are not occupations; titles are not guessed.
OCCUPATION_TAGS = {
    "Managers": {"managers", "management"},
    "Professionals": {"professionals", "teachers", "teaching", "doctors", "nurses", "engineers", "software engineering", "accountants", "lecturers"},
    "Technicians & associate professionals": {"technicians", "associate professionals"},
    "Clerical support workers": {"clerks", "clerical", "data entry"},
    "Service and sales workers": {"sales workers", "security guards", "sales"},
    "Skilled agricultural, forestry & fishery workers": {"farmers", "skilled agricultural workers", "fishery workers"},
    "Craft & related trades workers": {"electricians", "plumbers", "carpenters", "welders"},
    "Plant/machine operators & assemblers": {"drivers", "machine operators", "assemblers"},
    "Elementary occupations": {"cleaners", "labourers", "laborers", "helpers"},
}


def occupation_group(tags):
    keys = {value.casefold().strip() for value in as_list(tags)}
    matches = [name for name, aliases in OCCUPATION_TAGS.items() if keys & (aliases | {name.casefold()})]
    return matches[0] if len(matches) == 1 else "Multiple occupation groups" if matches else "Unclassified"


def listing_provinces(cities, provinces, province_by_city):
    cities = as_list(cities)
    provinces = as_list(provinces)
    city_keys = {city.casefold() for city in cities}
    all_cities = {city.casefold() for city in PAKISTAN_CITIES}
    province_keys = {province.casefold() for province in provinces}
    if (PAKISTAN_ALL_CITIES.casefold() in city_keys
        or (all_cities and all_cities.issubset(city_keys))
        or (len(city_keys) >= 20 and len(city_keys & all_cities) / max(1, len(all_cities)) >= .9)
        or {p.casefold() for p in PAKISTAN_PROVINCES}.issubset(province_keys)):
        return ["Pakistan / nationwide"]
    allowed = {p.casefold(): p for p in PAKISTAN_PROVINCES}
    derived = {province_by_city.get(c.casefold()) for c in cities} - {None, ""}
    # Explicit cities take precedence over stale province tags.
    selected = derived or {allowed[p.casefold()] for p in provinces if p.casefold() in allowed}
    return sorted(selected) if selected else ["Location unspecified"]


def new_breakdown():
    return {"occupations": Counter(), "provinces": Counter()}


def serialize_breakdown(value):
    return {key: [{"name": name, "value": count} for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))] for key, counts in value.items()}
