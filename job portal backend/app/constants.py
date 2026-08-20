"""Static reference data for Pakistan job portal filters."""

from __future__ import annotations

PAKISTAN_CITIES: list[str] = sorted(
    [
        "Abbottabad", "Attock", "Bahawalpur", "Bannu", "Batagram", "Bhakkar",
        "Chakwal", "Charsadda", "Chitral", "Dadu", "Dera Ghazi Khan",
        "Dera Ismail Khan", "Faisalabad", "Ghotki", "Gilgit", "Gujranwala",
        "Gujrat", "Gwadar", "Hafizabad", "Haripur", "Hyderabad", "Islamabad",
        "Jacobabad", "Jhang", "Jhelum", "Karachi", "Kasur", "Khairpur",
        "Khanewal", "Khuzdar", "Kohat", "Lahore", "Larkana", "Lasbela",
        "Layyah", "Lodhran", "Mandi Bahauddin", "Mansehra", "Mardan",
        "Mianwali", "Mirpur", "Mirpur Khas", "Multan", "Muzaffarabad",
        "Muzaffargarh", "Nawabshah", "Nowshera", "Okara", "Pakpattan",
        "Peshawar", "Quetta", "Rahim Yar Khan", "Rawalpindi", "Sahiwal",
        "Sargodha", "Sheikhupura", "Sialkot", "Skardu", "Sukkur", "Swabi",
        "Swat", "Tando Allahyar", "Thatta", "Turbat", "Vehari",
        "Wah Cantonment",
    ]
)

# Provinces plus the three territory-level regions used by nationwide
# employers. Keeping these separate from cities lets an administrator target a
# whole region without selecting every city individually.
PAKISTAN_PROVINCES: list[str] = [
    "Punjab",
    "Sindh",
    "Khyber Pakhtunkhwa",
    "Balochistan",
    "Islamabad Capital Territory",
    "Gilgit-Baltistan",
    "Azad Jammu and Kashmir",
]

# A single canonical location map powers the public city/province directories.
# Province-wide vacancies are expanded to every city in that province, while a
# city-only vacancy is also discoverable from its province page.
PAKISTAN_CITIES_BY_PROVINCE: dict[str, list[str]] = {
    "Punjab": [
        "Attock", "Bahawalpur", "Bhakkar", "Chakwal", "Dera Ghazi Khan",
        "Faisalabad", "Gujranwala", "Gujrat", "Hafizabad", "Jhang", "Jhelum",
        "Kasur", "Khanewal", "Lahore", "Layyah", "Lodhran", "Mandi Bahauddin",
        "Mianwali", "Multan", "Muzaffargarh", "Okara", "Pakpattan",
        "Rahim Yar Khan", "Rawalpindi", "Sahiwal", "Sargodha", "Sheikhupura",
        "Sialkot", "Vehari", "Wah Cantonment",
    ],
    "Sindh": [
        "Dadu", "Ghotki", "Hyderabad", "Jacobabad", "Karachi", "Khairpur",
        "Larkana", "Mirpur Khas", "Nawabshah", "Sukkur", "Tando Allahyar",
        "Thatta",
    ],
    "Khyber Pakhtunkhwa": [
        "Abbottabad", "Bannu", "Batagram", "Charsadda", "Chitral",
        "Dera Ismail Khan", "Haripur", "Kohat", "Mansehra", "Mardan",
        "Nowshera", "Peshawar", "Swabi", "Swat",
    ],
    "Balochistan": ["Gwadar", "Khuzdar", "Lasbela", "Quetta", "Turbat"],
    "Islamabad Capital Territory": ["Islamabad"],
    "Gilgit-Baltistan": ["Gilgit", "Skardu"],
    "Azad Jammu and Kashmir": ["Mirpur", "Muzaffarabad"],
}

PAKISTAN_PROVINCE_BY_CITY: dict[str, str] = {
    city: province
    for province, cities in PAKISTAN_CITIES_BY_PROVINCE.items()
    for city in cities
}

# The newspaper field remains free-form in the editor. These common values keep
# the new directory useful before older posts are manually backfilled.
PAKISTAN_NEWSPAPERS: list[str] = [
    "Daily Jang",
    "Dawn",
    "Express",
    "Nawa-i-Waqt",
    "The Nation",
    "The News",
]

DEFAULT_CATEGORIES: list[str] = sorted(
    [
        "Accounting", "AI Engineer", "Banking & Finance", "Customer Service",
        "Data & Analytics", "Education", "Engineering",
        "Healthcare", "HR & Admin", "Legal", "Marketing", "Police", "Product",
        "Sales", "Software Engineering", "Teaching", "Telecom",
    ]
)

SECTORS = ["govt", "private"]
JOB_TYPES = ["government", "private"]
