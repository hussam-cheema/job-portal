// Reviewed PBS snapshot for browser tests only; production reads the backend.
const pbsBreakdowns = {
  "dataset_id": "pbs-lfs-2024-25-19th-icls-v1",
  "period": "2024-25",
  "verified_at": "2026-09-09",
  "provider": "Pakistan Bureau of Statistics \u00b7 Labour Force Survey",
  "definition": "Employed persons aged 10 and over, 19th ICLS framework. Survey estimates, not vacancies or monthly hiring.",
  "source_url": "https://www.pbs.gov.pk/wp-content/uploads/2020/07/LFS-2024-25-Annual-Report.pdf",
  "occupations": {
    "unit": "% of employed persons",
    "table": "4.7",
    "page": 43,
    "source_url": "https://www.pbs.gov.pk/wp-content/uploads/2020/07/LFS-2024-25-Annual-Report.pdf#page=77",
    "items": [
      {
        "name": "Managers",
        "value": 2.3
      },
      {
        "name": "Professionals",
        "value": 6.1
      },
      {
        "name": "Technicians & associate professionals",
        "value": 4.4
      },
      {
        "name": "Clerical support workers",
        "value": 1.8
      },
      {
        "name": "Service and sales workers",
        "value": 17.2
      },
      {
        "name": "Skilled agricultural, forestry & fishery workers",
        "value": 28.0
      },
      {
        "name": "Craft & related trades workers",
        "value": 13.7
      },
      {
        "name": "Plant/machine operators & assemblers",
        "value": 8.3
      },
      {
        "name": "Elementary occupations",
        "value": 18.3
      }
    ]
  },
  "provinces": {
    "unit": "million employed persons",
    "table": "4.1",
    "page": 37,
    "source_url": "https://www.pbs.gov.pk/wp-content/uploads/2020/07/LFS-2024-25-Annual-Report.pdf#page=71",
    "pakistan_total": 77.2,
    "items": [
      {
        "name": "Punjab",
        "value": 44.7
      },
      {
        "name": "Sindh",
        "value": 17.5
      },
      {
        "name": "Khyber Pakhtunkhwa",
        "value": 11.3
      },
      {
        "name": "Balochistan",
        "value": 3.8
      }
    ]
  },
  "notes": "Published rounded values are preserved: occupation shares sum to 100.1%, and provincial counts to 77.3 million versus the published Pakistan total of 77.2 million. This table reports four provinces; no separate estimates are supplied here for ICT, AJK or Gilgit-Baltistan. Reviewed survey data is versioned, not presented as live monthly data."
};
export default pbsBreakdowns;
