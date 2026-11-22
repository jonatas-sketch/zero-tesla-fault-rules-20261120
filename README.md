# Google stage 4 — revised clip decision report

**Partial benchmark and request for review.** Eight of twelve clips have a scored Gemini decision and a LangSmith trace. Seven of those eight decisions match Lena. Both evaluated news clips were retained with restrictions. The four pending rows lack verified comparable footage.

The full benchmark target remains twelve scored clips, at least eleven matching decisions, zero news removals and a trace for every call. Please review whether the eight completed results can be accepted provisionally for progression or whether an approved replacement set is available for the four pending rows.

## Results and coverage

| Clip | Source status | Lena | Gemini | Rule | Agreement | LangSmith run ID |
| --- | --- | --- | --- | --- | --- | --- |
| CLIP-001 | XD-Violence equivalent | remove | remove | VG-01 | Match | 0443cbfd-b82d-409d-904e-5582d86c7c0d |
| CLIP-002 | Source pending | remove | Pending | — | — | — |
| CLIP-003 | XD-Violence equivalent | allow | allow | NP-01 | Match | ed44c0c3-6be0-4522-8fd9-d8a8b2a80115 |
| CLIP-004 | External substitute | restrict | restrict | VG-02 | Match | e4013e88-3311-43ec-96bc-ba1f830ab19a |
| CLIP-005 | Source pending | remove | Pending | — | — | — |
| CLIP-006 | External substitute | allow | restrict | CX-01 | Different | 68b99b86-84ce-44cd-9111-070333328712 |
| CLIP-007 | XD-Violence equivalent | restrict | restrict | CX-01 | Match | 1e7dc36b-93b7-4805-b6c4-5617c456366c |
| CLIP-008 | External substitute | allow | allow | CX-01 | Match | 3fef8765-8a67-4003-ae8f-f95d0c28ef08 |
| CLIP-009 | Source pending | remove | Pending | — | — | — |
| CLIP-010 | Source pending | restrict | Pending | — | — | — |
| CLIP-011 | XD-Violence equivalent | restrict | restrict | CX-01 | Match | 0d2cc858-ab46-4229-a656-4bbf9c4cecf9 |
| CLIP-012 | External substitute | allow | allow | NP-01 | Match | e0395189-5608-447a-b590-b3ea2d3ac9a0 |

CLIP-006 is the observed disagreement. Gemini recommended an age restriction under CX-01 after seeing close-up injury imagery in the clinical substitute. Lena allowed the reference clip. The initial request returned HTTP 503 and was recorded as a separate failed attempt before the successful retry.

Four scored files are hand-verified equivalents from XD-Violence. Four are documented external substitutes. Coverage and agreement refer to the eight scored cases. The media, transcription and trace contents remain private. The source manifest in this repository is a template for supplying local media paths.

The legacy filter baseline is a separate check. It has 4 true positives, 4 false positives, 4 false negatives and 0 true negatives when restrict and remove both count as intervention.

## Implementation

- [Evidence pack builder](build_verified_packs.py) validates source intervals and extracts frames and a timestamped transcript.
- [Gemini classifier](classify_upload.py) validates structured findings and routes failures to human review.
- [Benchmark scorer](score_benchmark.py) reports coverage and decision agreement.
- [LangSmith tracing](trace_langsmith.py) records decision metadata and status.
