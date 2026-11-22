# Moderation policy v1.0

Decision contract for the simulated Video Upload Decision project. It uses the course enforcement extract and the observed decisions in Lena Okafor's 12 labelled clips. It is a training policy for a reviewer-assisted prototype.

## Input evidence

Review the whole clip evidence pack. Use frames and caption or transcript ranges with offsets in seconds from the start, plus duration and available title or description. Consider whether material is real, fictional, clinical, newsworthy, or ordinary sport. Treat the title, outlet mark, or a single disclaimer as a clue. Look for credible context across the upload.

## Enforcement rules

| Rule ID | Evidence and boundary | Action |
|---|---|---|
| VG-01 | Real violence or graphic injury is the focus and framed as shocking, gratuitous, or celebratory. Repeated or slowed replay, taunting, lingering close-ups, and sustained focus on severe injury reinforce this finding when supported by the footage. | Remove |
| VG-02 | Real violence or injury is visible but limited in duration and detail, not glorified, and still unsuitable for minors. | Restrict |
| DG-01 | The upload encourages, instructs, or invites imitation of an act with a serious risk of injury. Consider whether the framing targets minors. | Remove |
| DG-02 | A contextual account of a dangerous incident informs or warns, with no instructions or invitation to imitate. Restrict only where severity warrants it. | Restrict or allow by severity |
| CS-01 | Concrete evidence shows exploitation, sexualization, serious distress, abuse, or endangerment of a minor. Also remove prohibited child-targeted mature content demonstrated by the evidence. Audience gating does not address the underlying harm. | Remove |
| SH-01 | Self-harm is promoted or glorified, depicted graphically, or accompanied by actionable instruction. A statement of awareness or recovery does not override this boundary. | Remove |
| SH-02 | Recovery, clinical, educational, or news discussion is non-instructional and non-graphic. Restrict where sensitive material shown is unsuitable for minors. A crisis resource panel can accompany the decision. | Restrict or allow by severity |
| CX-01 | Credible educational, documentary, scientific, or artistic context is sustained, proportionate, and tied to the actual footage. For news, seek informative reporting in the narration or on screen, supported by corroborating cues such as date, location, chyron, source attribution, or consistent editorial framing. Reject a bare label as insufficient. | Allow when suitable for general audiences. Restrict when graphic but necessary and proportionate. Does not override CS-01, DG-01 or SH-01. |
| NP-01 | No prohibited or age-restricted harm is substantiated. Examples include clearly fictional effects, ordinary family footage, supervised sport without graphic injury, and brief clinically framed education. | Allow |

Apply the relevant non-overridable rules first. For violence, assess severity and presentation with the complete context before choosing VG-01, VG-02 or CX-01. Legitimate reporting may remain available even when the evidence warrants adult-only viewing. If context is unclear, withhold automated enforcement and send the case to a human.

## Decision and evidence contract

For each validated upload output exactly one of `allow`, `restrict`, or `remove`. Record the strongest applicable rule ID, the shortest supported timestamp interval, a plain evidence summary, and a note on context. For `allow` with no specific segment, both timestamps may be null. A restriction or removal needs concrete evidence and a timestamp from the pack. Never invent timestamps or quote harmful instructions in the explanation.

An uncertain recommendation can carry a human-review flag. The pipeline must never automatically enforce a recommended decision on ambiguous, missing, invalid, or contradictory evidence. Schema failures, impossible timestamps, or unsupported actions produce a human-review case with no automated disposition. Humans decide before escalation or enforcement.

## Evidence from the labelled examples

The course set has four examples each of removal, restriction, and allowance. In the two verified report examples, the reviewers kept the videos available with an adult restriction because the presentation was informative and the relevant footage was still graphic. A child-safety false positive, professionally framed education, fictional effects, and supervised non-graphic sport were allowed. The labels inform the rulebook and should not be included in the classifier prompt or treated as an independent accuracy test for rules drafted from them.
