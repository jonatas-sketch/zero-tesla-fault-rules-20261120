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
  --provider openrouter --model particle-ai/particle-1:free --external-approved
```

This path makes one request per record, retries transient failures for that record, and checkpoints completed decisions next to the output. Repeat the same command to resume after an interruption. A successful synthetic brake-pedal case verified access with a free OpenRouter model. The annotated subset can measure recall for reviewed positives. Use human review on safety classifications.
