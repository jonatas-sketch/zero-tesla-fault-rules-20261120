# Google stage 4 — clip decision report

**Partial benchmark submitted for review.** Four of twelve rows have scored decisions. Four more have verified evidence packs awaiting classification. Four are still awaiting suitable footage. The full benchmark threshold has not been met.

## Scored results

| Clip | Lena's decision | Gemini decision | Rule |
| --- | --- | --- | --- |
| CLIP-001 | Remove | Remove | VG-01 |
| CLIP-003 | Allow | Allow | NP-01 |
| CLIP-007 | Restrict | Restrict | CX-01 |
| CLIP-011 | Restrict | Restrict | CX-01 |

All four scored decisions agree with the reference. Neither of the two evaluated news clips was removed. Each successful classification has a LangSmith trace. The CLIP-011 rate-limit attempt and retry were recorded separately.

## Coverage and limitations

| State | Clip IDs |
| --- | --- |
| Scored with traced Gemini calls | CLIP-001, CLIP-003, CLIP-007, CLIP-011 |
| Verified packs, awaiting a model decision | CLIP-004, CLIP-006, CLIP-008, CLIP-012 |
| Awaiting corresponding licensed footage | CLIP-002, CLIP-005, CLIP-009, CLIP-010 |

The four scored clips are hand-verified equivalents from XD-Violence. The additional packs are documented external substitutes. For pending rows, footage must preserve the context that supports the reviewer's action. Rehearsal fixtures have no scored entries.

The legacy filter was compared against the reviewer's binary intervention flag, with both restrict and remove counted as intervention. The twelve reference rows yielded 4 true positives, 4 false positives, 4 false negatives and 0 true negatives. This baseline comparison uses the reviewer sheet and filter flags. The Gemini results above cover four rows.

The evaluation target is twelve scored clips, at least eleven exact action matches, zero news removals and a trace for every call. The current figures describe the scored subset. No aggregate accuracy is reported for the full set.

## Implementation

- [Evidence pack builder](build_verified_packs.py) checks each source interval and creates frames and a timestamped transcript.
- [Gemini classifier](classify_upload.py) validates structured findings and routes failures to human review.
- [Benchmark scorer](score_benchmark.py) reports source coverage and action matches separately.
- [LangSmith tracing](trace_langsmith.py) records call status and decision metadata from local configuration.
