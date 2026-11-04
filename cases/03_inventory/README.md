# Case 3 · Inventory & demand

**Real data:** [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii)
(UCI, CC BY 4.0) - every invoice line of a UK online gift retailer, Dec 2009 - Dec 2011.

**Plan B:** `generate()` in `src/kpistory/data/retail.py`, seed `2011`: ~4,200
customers with heterogeneous purchase rates and lifetimes, ~900 SKUs with
Zipf-like popularity, a Q4 gift season, 15% Christmas SKUs, SKUs launched and
faded over time, plus the real file's defects (24% guest invoices, 2%
cancellations, postage lines, zero prices, 0.8% duplicates).

**Stock simulation (always synthetic, seed 31)** - the public data has demand but not stock:

| Element | Rule |
|---|---|
| SKUs | 40 best sellers by units + 8 "faded" SKUs (no sales in the last 200 days) |
| Forecast | 8-week moving average of weekly demand, made the week before |
| Replenishment | weekly review; order up to 5 weeks of forecast; lead time 10-17 days |
| Service | demand not served from stock is lost; daily stock allocated first-come-first-served |
| Delivery | promised in 3 days; transit 1-4 days, 15% of Nov-Dec parcels take 4-6 days |
| Cost | 60% of the SKU's median selling price |

**Reading the results:** demand is real when the download works; stock, forecast
and delivery are a transparent simulation. Findings illustrate the method.
