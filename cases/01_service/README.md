# Case 1 · Service operations & SLA

**Data:** synthetic, always. There is no public service-desk log with timestamps,
priorities, SLA targets and reopenings, so the generator is the primary source.

**Generator:** `src/kpistory/data/tickets.py`, seed `7`, calendar year 2024.

| Assumption | Value |
|---|---|
| Queues (tickets per weekday) | Billing 9 · Technical 12 · Field Support 8 · Accounts 6; weekends at 30% |
| Priorities | P1 5% · P2 17% · P3 48% · P4 30%; SLA 8 / 24 / 72 / 120 h |
| Capacity | each queue resolves ~1.3× its normal daily demand (Poisson); P1 first, then oldest |
| Event | from 2024-09-01 a product rollout raises Field Support demand by 60%; capacity unchanged |
| Side effects under pressure | slower first response, lower FCR, reopen probability 4% → 10% |
| Defects injected (for case 5) | 0.5% duplicate rows, 1.2% missing channel, 0.2% resolved-before-created, 2.5% loaded > 24 h late |

**Cleaning:** duplicates by `ticket_id` removed; impossible timestamps removed; missing
channel set to `unknown`; derived columns computed once in `derive_ticket_columns`.

**Reading the results:** findings are an illustration of the method on synthetic
data, not a claim about any real service desk.
