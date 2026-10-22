"""Minimal Azure OpenAI chat-completions client (plain requests, no extra dependency)."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import requests

from services.config import azure_settings, request_timeout
from services.http_events import IntegrationError


def chat_json(messages: List[Dict[str, Any]], max_tokens: int = 600, temperature: float = 0.1) -> Dict[str, Any]:
    """Call the configured deployment and return the reply parsed as a JSON object."""
    azure = azure_settings()
    if not azure.configured:
        raise IntegrationError("Azure OpenAI: AZURE_API_KEY / AZURE_ENDPOINT / DEPLOYMENT_NAME / API_VERSION not set")
    url = (
        f"{azure.endpoint.rstrip('/')}/openai/deployments/{azure.deployment}"
        f"/chat/completions?api-version={azure.api_version}"
    )
    try:
        response = requests.post(
            url,
            headers={"api-key": azure.api_key},
            json={
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            },
            timeout=request_timeout(),
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
    except requests.HTTPError as exc:
        raise IntegrationError(f"Azure OpenAI HTTP {exc.response.status_code}: {exc.response.text[:200]}") from exc
    except (requests.RequestException, KeyError, ValueError) as exc:
        raise IntegrationError(f"Azure OpenAI: {exc}") from exc
