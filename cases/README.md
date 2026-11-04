# Cases

Each case is told as a story on the website with the same structure:
**context → question → KPI → finding → decision → how it keeps being measured.**

| # | Case | KPIs | Data | Plan B |
|---|------|------|------|--------|
| 1 | [Service operations & SLA](01_service/README.md) | first response, resolution time, SLA compliance, aged backlog, FCR, reopen rate | Synthetic ticket queue simulation | - (always synthetic) |
| 2 | [Maintenance](02_maintenance/README.md) | MTBF, MTTR, availability, PM compliance, planned share | UCI AI4I 2020 + work-order generator | AI4I re-generated from its published rules |
| 3 | [Inventory & demand](03_inventory/README.md) | fill rate, OTIF, turnover, days of cover, stockouts, obsolescence, MAPE, WAPE, bias | UCI Online Retail II demand + stock simulation | Synthetic transaction log with the same schema and defects |
| 4 | [Customers](04_customers/README.md) | retention, repeat purchase, RFM revenue at risk, NPS | UCI Online Retail II + simulated survey | Same synthetic log as case 3 |
| 5 | [Data quality as a KPI](05_data_quality/README.md) | completeness, uniqueness, validity, timeliness | The landing data of cases 1-4 | Follows the other cases |

The provenance actually used by the last build is in `data/processed/manifest.json`
and on the website's *Data sources* page.
