# Case 5 · Data quality as a KPI

Measured on the *landing* data of cases 1-4 (before cleaning), with the rules in
`kpis/dq_rules.yaml`: required columns, business key, validity rules and the
timeliness window per dataset.

| Dataset | Origin |
|---|---|
| Service tickets | synthetic (defects injected, documented in case 1) |
| Maintenance work orders | synthetic (defects injected, documented in case 2) |
| Process data (AI4I 2020) | real when downloaded, otherwise plan B |
| Sales transactions (Online Retail II) | real when downloaded, otherwise plan B with the same kinds of defects |
| NPS survey | synthetic |

Datasets without a load timestamp (the two public ones) cannot be measured for
timeliness; the page reports that as a finding instead of inventing a value.
