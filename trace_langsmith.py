"""Send bounded moderation-run metadata to a configured LangSmith project."""

from datetime import datetime, timezone
import os
from uuid import uuid4

from dotenv import dotenv_values


ENDPOINTS = {
    "https://api.smith.langchain.com",
    "https://eu.api.smith.langchain.com",
    "https://apac.api.smith.langchain.com",
    "https://aws.api.smith.langchain.com",
}


class TraceRecorder:
    def __init__(self, client, project):
        self.client = client
        self.project = project

    def __call__(self, start, inputs, result):
        finding = result["finding"] or {}
        run_id = uuid4()
        self.client.create_run(
            "Gemini upload decision",
            inputs=inputs,
            run_type="llm",
            project_name=self.project,
            id=run_id,
            start_time=start,
            end_time=datetime.now(timezone.utc),
            outputs={
                "status": result["status"],
                "action": finding.get("action"),
                "rule_id": finding.get("rule_id"),
                "evidence_start_seconds": finding.get("evidence_start_seconds"),
                "evidence_end_seconds": finding.get("evidence_end_seconds"),
                "reason": result.get("reason"),
            },
        )
        return str(run_id)


def load_tracer(env_file):
    local = dotenv_values(env_file, interpolate=False) if env_file else {}
    def setting(name, default=""):
        return os.environ.get(name, local.get(name) or default)

    if setting("LANGSMITH_TRACING").casefold() != "true":
        return None
    key = setting("LANGSMITH_API_KEY")
    project = setting("LANGSMITH_PROJECT")
    endpoint = setting("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com").rstrip("/")
    if not key or not project or endpoint not in ENDPOINTS:
        raise ValueError("Tracing needs a local key, project, and official LangSmith API endpoint")

    from langsmith import Client

    return TraceRecorder(Client(api_key=key, api_url=endpoint, auto_batch_tracing=False), project)
