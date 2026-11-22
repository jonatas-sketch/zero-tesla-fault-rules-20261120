"""Classify one evidence pack with the Gemini API, routing bad responses to review."""

import argparse
import base64
import json
import math
import os
from pathlib import Path
import re
from typing import Literal
from urllib import error, request

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, model_validator


ROOT = Path(__file__).resolve().parent
VALID_RULES = {"VG-01", "VG-02", "DG-01", "DG-02", "CS-01", "SH-01", "SH-02", "CX-01", "NP-01"}
API = "https://generativelanguage.googleapis.com/v1beta/models/"
MAX_INLINE_BYTES = 18 * 1024 * 1024


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    action: Literal["allow", "restrict", "remove"] | None
    rule_id: str | None
    evidence_start_seconds: float | None
    evidence_end_seconds: float | None
    evidence_summary: str = Field(min_length=1, max_length=1000)
    context_summary: str = Field(min_length=1, max_length=1000)
    needs_human_review: bool

    @model_validator(mode="after")
    def check_evidence_contract(self):
        if self.action is None:
            if not self.needs_human_review or self.rule_id is not None:
                raise ValueError("An unresolved action needs human review and no rule")
        elif self.rule_id not in VALID_RULES:
            raise ValueError("Unknown moderation rule ID")

        start = self.evidence_start_seconds
        end = self.evidence_end_seconds
        if self.action is None and (start is not None or end is not None):
            raise ValueError("Unresolved evidence must leave the times blank")
        if (start is None) != (end is None):
            raise ValueError("Evidence times must be paired")
        if start is not None and not 0 <= start <= end:
            raise ValueError("Evidence interval is out of order")
        if self.action in {"restrict", "remove"} and start is None:
            raise ValueError("A restriction or removal needs a grounded interval")
        return self


def load_key(env_file):
    local = dotenv_values(env_file, interpolate=False) if env_file else {}
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or local.get("GEMINI_API_KEY") or local.get("GOOGLE_API_KEY")


def build_payload(manifest, pack, duration):
    model_input = [
        {"text": (ROOT / "moderation-policy-v1.0.md").read_text()},
        {"text": (ROOT / "moderation-prompt-v1.0.md").read_text()},
        {"text": json.dumps({
            "clip_id": pack["clip_id"],
            "duration_seconds": duration,
            "source_kind": pack["source_kind"],
            "transcript_status": pack["transcript_status"],
            "works_from_original_timeline_seconds": True,
            "words": pack["words"],
        })},
    ]
    if not pack["frames"]:
        raise ValueError("No frames are available for this clip")
    for frame in pack["frames"]:
        timestamp = frame["timestamp_seconds"]
        if not isinstance(timestamp, (int, float)) or not 0 <= timestamp < duration:
            raise ValueError("Pack frame timestamp is out of range")
        path = (manifest.parent / frame["file"]).resolve()
        frames_dir = (manifest.parent / "frames").resolve()
        if path.parent != frames_dir or path.suffix.lower() not in {".jpg", ".jpeg"}:
            raise ValueError("Expected a JPEG from the pack's frames directory")
        model_input.extend([
            {"text": f"Evidence frame at {timestamp} seconds"},
            {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(path.read_bytes()).decode("ascii")}},
        ])
    return {
        "contents": [{"role": "user", "parts": model_input}],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 1200,
            "responseMimeType": "application/json",
            "responseJsonSchema": Finding.model_json_schema(),
        },
    }


def request_finding(payload, key, model):
    body = json.dumps(payload).encode("utf-8")
    if len(body) > MAX_INLINE_BYTES:
        raise ValueError("Pack exceeds the inline request size limit")
    if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]+", model):
        raise ValueError("Invalid Gemini model name")
    req = request.Request(
        f"{API}{model}:generateContent", data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with request.urlopen(req, timeout=65) as response:
        result = json.load(response)
    candidate = result["candidates"][0]
    if candidate.get("finishReason") != "STOP":
        raise ValueError("Gemini did not finish the response")
    return "".join(part.get("text", "") for part in candidate["content"]["parts"] if not part.get("thought"))


def classify(manifest, key, model):
    try:
        pack = json.loads(manifest.read_text())
        identifier = pack["clip_id"]
        duration = float(pack["duration_seconds"])
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError("Clip duration is invalid")
        if not key:
            raise ValueError("No Gemini API key configured")
        payload = build_payload(manifest, pack, duration)
        finding = Finding.model_validate_json(request_finding(payload, key, model))
        if finding.evidence_end_seconds is not None and finding.evidence_end_seconds > duration:
            raise ValueError("Finding points outside the clip duration")
        return {
            "clip_id": identifier, "model": model, "source_kind": pack["source_kind"],
            "status": "human_review" if finding.needs_human_review else "validated_recommendation",
            "finding": finding.model_dump(),
        }
    except error.HTTPError as exc:
        reason = f"Gemini HTTP {exc.code}"
    except (OSError, KeyError, TypeError, ValueError, IndexError) as exc:
        reason = type(exc).__name__
    return {"clip_id": locals().get("identifier"), "status": "human_review", "finding": None, "reason": reason}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--model", default="gemini-3.1-flash-lite")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = classify(args.manifest.resolve(), load_key(args.env_file), args.model)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(result["status"])
    return int(result["status"] != "validated_recommendation")


if __name__ == "__main__":
    raise SystemExit(main())
