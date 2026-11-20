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
