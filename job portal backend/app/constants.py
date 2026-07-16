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
