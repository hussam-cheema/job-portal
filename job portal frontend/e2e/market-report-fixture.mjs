// Synthetic test observations only. Never imported by application code.
const definitions = {
  unemployment: ["SL.UEM.TOTL.ZS", 5.42], youth_unemployment: ["SL.UEM.1524.ZS", 11.3],
  female_unemployment: ["SL.UEM.TOTL.FE.ZS", 8.4], male_unemployment: ["SL.UEM.TOTL.MA.ZS", 4.8],
  participation: ["SL.TLF.CACT.ZS", 54], female_participation: ["SL.TLF.CACT.FE.ZS", 24], male_participation: ["SL.TLF.CACT.MA.ZS", 82],
  employment_ratio: ["SL.EMP.TOTL.SP.ZS", 51], agriculture: ["SL.AGR.EMPL.ZS", 33], industry: ["SL.IND.EMPL.ZS", 25], services: ["SL.SRV.EMPL.ZS", 42],
  wage_employment: ["SL.EMP.WORK.ZS", 42], vulnerable_employment: ["SL.EMP.VULN.ZS", 52], self_employment: ["SL.EMP.SELF.ZS", 58],
};
export function marketReport(month) {
  const series = Object.fromEntries(Object.entries(definitions).map(([key, [code, value]]) => {
    const points = Array.from({ length: 12 }, (_, i) => ({ year: String(2014 + i), value: value + (11 - i) * .1 }));
    return [key, { code, title: `${key.replaceAll("_", " ")} (modelled ILO estimate)`, unit: "%", points, latest: points.at(-1), source_url: `https://data.worldbank.org/indicator/${code}?locations=PK`, api_url: `https://api.worldbank.org/v2/country/PAK/indicator/${code}?format=json` }];
  }));
  return { schema_version: 1, month, published_at: `${month}-01T00:15:00Z`, national_data_changed: false,
    national: { series, provider: "World Bank / ILO", source_updated: ["2026-07-13"], license_url: "https://datacatalog.worldbank.org/public-licenses#cc-by" },
    site_supplement: { month: "2026-08", total: 100, government: 60, private: 35, unspecified: 5, source_url: "/", scope: "Website only" },
  };
}
