# Fault urgency rules · Tesla training exercise

The Pydantic model validates the output of a simulated fault triage workflow. It accepts three urgency tags and four fixed fix paths. The assignment uses the rules below as the contract for the later classifier and service schedule.

| Urgency | Fix path | Decision |
| --- | --- | --- |
| `safety_urgent` | `priority_safety_inspection` | Escalate to a human service reviewer. They decide whether to arrange towing. |
| `soon` | `book_service_soon` | Schedule a prompt diagnostic visit for a drivable but material fault. |
| `routine` | `routine_service_visit` | Schedule a normal visit for a physical fault requiring inspection or repair. |
| `routine` | `remote_troubleshooting` | Route routine account, app, or settings issues to remote support. |

The six safety alert codes are `BRK_a001`, `BRK_w003`, `ABS_w002`, `ESP_w003`, `EPAS_a191`, and `EPAS_w202`. A credible symptom of impaired braking, ABS, stability control, or steering also routes to safety triage when the alert code is missing. For example, a calm report of a sinking brake pedal is safety urgent even if the code is `NONE`. The subject and description supply the evidence. The customer's tone never downgrades a safety symptom.

This repository contains a training contract and tests with synthetic examples. The schema rejects unknown labels and invalid pairings. A later classifier will use the symptom rule to assign the labels. The schema alone cannot infer the severity of a fault from prose.

**Key implementation prompt.** Build a small Pydantic model with the three exact urgency values and the four agreed fix paths. Record the six safety alert codes and the hidden-symptom rule in the module. Prove that a made-up urgency is rejected.

**One change after review.** I added cross-field validation. Separate enums would accept a valid `routine_service_visit` path paired with `safety_urgent`. Validating the pair keeps a recognized safety case from being routed to a routine action.

```sh
python -m pip install -r requirements.txt
python -m unittest -v
```

## Stage 2 · classify the overnight batch

`classify_batch.py` reads the course CSV and writes message ID, urgency, fix path, and the human-review flag. The model recommends a fix path. The code derives the matching urgency, validates the pair and keeps known safety codes in the safety queue. The evaluation columns are read only for the end-of-run comparison with reviewed safety cases.

For local inference, run Ollama on this Mac and pull `qwen2.5:3b`. Keep the input and output CSVs outside the public repository.

```sh
python classify_batch.py /path/to/course-input.csv /path/to/result.csv
```

For OpenRouter, supply `OPENROUTER_API_KEY` through the environment. For a fresh setup, copy `.env.example` to `.env` and put the key in that ignored file. Keep the key out of messages, screenshots, and commits.

Convert the course file to a minimized input locally. This projection emits fixed technical phrases and recognized alert codes. It keeps row IDs and review labels for local bookkeeping, while the HTTP payload holds only the generic subject, fixed phrases and the code. The projection may lose context, including nuance in negated or truncated descriptions.

```sh
python minimize_reports.py /path/to/course-input.csv /path/to/technical-input.csv
set -a
. ./.env
set +a
python classify_batch.py /path/to/technical-input.csv /path/to/result.csv \
  --provider openrouter --model nvidia/nemotron-3.5-super-vl:free --external-approved
```

This path makes one request per record, starts requests at a shared rate, and checkpoints each valid decision next to the output. If a single record exhausts its retries, the program can keep working on others and resume only the missing records on the next run. The default configuration permits only free fallback models and records the model that served every result. A synthetic brake-pedal case verified access. The annotated subset can measure recall for reviewed positives.

```sh
python verify_results.py /path/to/course-input.csv /path/to/result.csv tagged-fault-messages.csv
```

The verification step checks all 300 message IDs, urgency and path consistency, safety codes and review flags. It applies a local safety recheck to concrete evidence that the projection can miss, such as a grinding brake pedal or a wobbling steering wheel. It reports model results and any overrides separately. Its export contains the exercise IDs and final decisions. The course input, minimized input and model receipts stay local. Use human review on safety classifications.

### Overnight batch results

The free OpenRouter run produced 300 validated decisions. The initial model and alert-code checks detected 53 of 60 reviewed safety faults. The local safety review promoted 8 additional cases with concrete symptoms in the original text. One remaining miss, heavy steering that catches at low speed, prompted the final recheck rule. The exported queue covers 60 of 60 reviewed positives after review on this batch. That comparison measures recall on reviewed positives for the initial run and coverage after revision for the export. It does not estimate general accuracy.

The [tagged output](tagged-fault-messages.csv) contains 105 safety-urgent, 66 soon, and 129 routine records. Every safety record is flagged for human review.

## Stage 3 · service schedule

The [schedule](service-schedule.csv) gives every exercise record a booking outcome. The [safety report](safety-report.md) compares the original and corrected safety tags and records capacity exceptions.

Supply the original course CSV, the open-slot inventory and the initial OpenRouter predictions locally. The free model requests one call to `book_service_slot` per message. An API response can contain several separate calls. Its arguments contain only an ordinal with the urgency and route. The Python function validates each call and reserves an actual inventory slot in the canonical urgency order.

```sh
python service_schedule.py \
  --original /path/to/overnight.csv --tags tagged-fault-messages.csv \
  --slots /path/to/open-slots.csv --baseline /path/to/classification.csv \
  --checkpoints /path/to/booking-calls.checkpoint.json \
  --output service-schedule.csv --report safety-report.md
```

Use the `OPENROUTER_API_KEY` environment variable from Stage 2. Reuse the same inputs and checkpoint to resume. Safety demand exceeding Monday's capacity is escalated immediately and reserves the earliest available priority bay later in the week. Remote demand exceeding compatible capacity stays in the advisor queue.
