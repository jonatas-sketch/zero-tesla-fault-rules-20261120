"""Validate the fault-routing outputs for the Tesla training scenario.

A credible symptom of impaired braking, ABS, stability control, or steering
requires safety triage even if the report has no corresponding alert code.
The driver's tone never downgrades a safety symptom. A human service team
decides whether towing is appropriate for an active loss of control.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, model_validator

SAFETY_ALERT_CODES = [
    "BRK_a001",
    "BRK_w003",
    "ABS_w002",
    "ESP_w003",
    "EPAS_a191",
    "EPAS_w202",
]


class UrgencyTag(str, Enum):
    SAFETY_URGENT = "safety_urgent"
    SOON = "soon"
    ROUTINE = "routine"


class FixPath(str, Enum):
    PRIORITY_SAFETY_INSPECTION = "priority_safety_inspection"
    BOOK_SERVICE_SOON = "book_service_soon"
    ROUTINE_SERVICE_VISIT = "routine_service_visit"
    REMOTE_TROUBLESHOOTING = "remote_troubleshooting"


ALLOWED_PATHS = {
    UrgencyTag.SAFETY_URGENT: {FixPath.PRIORITY_SAFETY_INSPECTION},
    UrgencyTag.SOON: {FixPath.BOOK_SERVICE_SOON},
    UrgencyTag.ROUTINE: {
        FixPath.ROUTINE_SERVICE_VISIT,
        FixPath.REMOTE_TROUBLESHOOTING,
    },
}


class FaultUrgencyRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    urgency_tag: UrgencyTag
    fix_path: FixPath

    @model_validator(mode="after")
    def validate_fix_path(self) -> "FaultUrgencyRule":
        if self.fix_path not in ALLOWED_PATHS[self.urgency_tag]:
            raise ValueError("fix_path does not match urgency_tag")
        return self
