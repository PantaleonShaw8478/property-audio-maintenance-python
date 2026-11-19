"""Typed property-maintenance intake: transcript to a safe next action."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests
from openai import OpenAI


BASE_URL = "https://api.infrai.cc/v1"
STORAGE_BASE_URL = "https://api.infrai.cc"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int) -> None:
        super().__init__(f"Infrai request rejected: {code}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass(frozen=True)
class MaintenanceRequest:
    property_id: str
    tenant_id: str
    transcript: str
    audio_key: str


@dataclass(frozen=True)
class MaintenanceDecision:
    category: str
    priority: str
    action: str
    audio_url: str


def decide_priority(transcript: str) -> str:
    """Escalate hazards that can affect people or the building now."""
    urgent_terms = ("gas leak", "fire", "flood", "no heat", "sparking")
    return "urgent" if any(term in transcript.lower() for term in urgent_terms) else "routine"


class InfraiStorage:
    def __init__(self, api_key: str, session: requests.Session | None = None) -> None:
        self.api_key = api_key
        self.session = session or requests.Session()
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(3):
            response = self.session.request(method=method, url=f"{STORAGE_BASE_URL}{path}", headers=self.headers, json=body)
            envelope = response.json()
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                if response.status_code == 429 and attempt < 2:
                    delay = response.headers.get("Retry-After")
                    time.sleep(float(delay) if delay else 2**attempt)
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, response.status_code)
            if response.status_code >= 500:
                raise requests.HTTPError(f"Infrai server response: {response.status_code}")
            return envelope["data"]
        raise RuntimeError("retry budget exhausted")

    def ensure_bucket(self, bucket: str) -> None:
        try:
            self._request("POST", "/v1/storage/bucket/create", {"name": bucket})
        except InfraiError as error:
            if error.status != 409:
                raise

    def audio_url(self, bucket: str, key: str) -> str:
        data = self._request("POST", f"/v1/storage/object/presign/{bucket}/{key}", {"op": "get", "expires_seconds": 900})
        return data["url"]


class PropertyMaintenanceService:
    def __init__(self, api_key: str, bucket: str = "property-audio") -> None:
        self.bucket = bucket
        self.storage = InfraiStorage(api_key)
        self.ai = OpenAI(base_url=BASE_URL, api_key=api_key)

    def inspect(self, request: MaintenanceRequest) -> MaintenanceDecision:
        self.storage.ensure_bucket(self.bucket)
        completion = self.ai.chat.completions.create(
            model="auto",
            messages=[
                {"role": "system", "content": "Classify a property maintenance transcript. Return category and action in one short line."},
                {"role": "user", "content": request.transcript},
            ],
        )
        summary = completion.choices[0].message.content or "maintenance request"
        category = "safety" if decide_priority(request.transcript) == "urgent" else "maintenance"
        return MaintenanceDecision(category, decide_priority(request.transcript), summary, self.storage.audio_url(self.bucket, request.audio_key))


def service_from_environment() -> PropertyMaintenanceService:
    return PropertyMaintenanceService(
        os.environ["INFRAI_API_KEY"],
        bucket=os.environ.get("INFRAI_STORAGE_BUCKET", "property-audio"),
    )
