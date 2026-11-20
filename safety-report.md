# Morning fault queue safety report

The comparison joins 60 hand-checked rows by exercise message ID.
The initial OpenRouter and alert-code pass detected 53 of 60 reviewed positives, with 7 false negatives.
After local evidence review, the submitted tags cover 60 of 60 reviewed positives and have 0 residual false negatives.
The reviewed subset contains only positives. These counts measure batch coverage and cannot establish precision, specificity, or general accuracy.

## Initial model misses

| Exercise ID | Initial | Expected | Technical context |
|---|---|---|---|
| MSG-10101 | soon | safety_urgent | The vehicle pulls to one side while stopping. |
| MSG-10140 | soon | safety_urgent | Grinding or scraping occurs when the brake pedal is pressed. |
| MSG-10170 | routine | safety_urgent | Repeated steering correction is needed on a flat road. |
| MSG-10219 | soon | safety_urgent | The steering wheel shimmies or wobbles while driving. |
| MSG-10230 | routine | safety_urgent | The steering feels unusually heavy or loose. |
| MSG-10278 | routine | safety_urgent | The steering wheel shimmies or wobbles while driving. |
| MSG-10286 | soon | safety_urgent | The brake pedal travels further before the brakes engage. |

## Booking results

- safety same day — 24
- safety overflow escalated — 81
- booked — 189
- awaiting remote capacity — 6
- Safety overflow on 2026-11-17 — 34
- Safety overflow on 2026-11-18 — 42
- Safety overflow on 2026-11-19 — 5

Safety overflow cases get immediate advisor escalation. The later bay remains reserved for priority inspection.
Cases awaiting remote capacity have no slot ID. An advisor reviews them before booking any alternative.
This exercise uses the supplied unique slot IDs. Technician and facility coverage would need separate validation in a live schedule.
