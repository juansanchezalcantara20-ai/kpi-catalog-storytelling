# Case 4 · Customers

**Real data:** Online Retail II (see case 3). Only invoices with a customer id are
used for retention, repeat purchase and RFM - the share excluded is measured in case 5.

**Plan B:** the same synthetic transaction log as case 3.

**Survey (always synthetic, seed 404):** one NPS wave sent to every customer active
in the last 12 months; 30% respond. The score mix depends on the RFM segment
(e.g. Champions 62% promoters, At risk 46% detractors). This dependency is an
assumption of the generator, so the page uses the survey to show *how to compute
and read NPS*, not to prove that RFM predicts loyalty.

**RFM:** 12-month window ending the day after the last invoice; recency, frequency
and monetary scored 1-5 by quintile; segments by explicit rules in
`src/kpistory/formulas/customers.py`.
