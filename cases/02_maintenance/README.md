# Case 2 · Maintenance & asset reliability

**Real data:** [AI4I 2020 Predictive Maintenance Dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
(UCI, CC BY 4.0) - 10,000 process records with five failure modes
(tool wear, heat dissipation, power, overstrain, random).

**Plan B:** `generate_ai4i()` in `src/kpistory/data/maintenance.py`, seed `2020`.
AI4I is itself synthetic and its UCI page publishes the generation rules; plan B
re-implements them (air/process temperature random walks, torque ~ N(40, 10),
speed anti-correlated with torque, tool wear +5/+3/+2 min for H/M/L, failure
rules for TWF/HDF/PWF/OSF/RNF). Same columns, same physics, different draws.

**Mapping to a fleet (assumption):** 10 contiguous blocks of 1,000 records = 10
machines M01-M10; each record is a 4-hour run; 4 runs per working day in 2024.

**Work orders (always synthetic, seed 2021):**

| Type | Rule |
|---|---|
| Corrective | one per failure; repair time lognormal by mode (median 1.5-4 h); 9% wait 16-60 h for spare parts |
| Tool change | planned, whenever tool wear resets without a failure |
| Preventive | weekly per machine (due Monday); crews of M07/M08 run late 38% of the time and skip 10% |
| Defects | 3% corrective without failure mode, 0.4% zero labour hours, 0.3% duplicates; M07/M08 log 35% of WOs 1-4 days late |

**Reading the results:** illustration of the method. The relationship between
tool wear and failures comes from the AI4I rules; PM lateness by crew is an
assumption of the generator.
