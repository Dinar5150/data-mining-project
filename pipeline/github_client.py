from __future__ import annotations

import os
import time
from typing import Any

import requests

from pipeline.config import GitHubConfig


class GitHubClient:
    def __init__(self, config: GitHubConfig):
        token = os.environ.get(config.token_env)
        if not token:
            raise RuntimeError(
                f"Missing GitHub token in environment variable {config.token_env}."
            )

        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": config.api_version,
                "User-Agent": "gh-trace-dataset-mvp",
            }
        )

    def get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        response = self._request("GET", url, params=params)
        return response.json()

    def get_paginated(
        self, url: str, params: dict[str, Any] | None = None
    ) -> list[Any]:
        request_params = dict(params or {})
        request_params.setdefault("per_page", self.config.per_page)

        items: list[Any] = []
        next_url: str | None = url
        next_params: dict[str, Any] | None = request_params

        while next_url:
            response = self._request("GET", next_url, params=next_params)
            payload = response.json()
            if isinstance(payload, list):
                items.extend(payload)
            else:
                raise RuntimeError(f"Expected a list response from {next_url}.")

            next_url = response.links.get("next", {}).get("url")
            next_params = None

        return items

    def get_text(self, url: str, accept: str) -> str:
        response = self._request("GET", url, headers={"Accept": accept})
        return response.text

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        timeout = kwargs.pop("timeout", self.config.request_timeout_seconds)

        last_response: requests.Response | None = None
        for attempt in range(self.config.retry_count):
            response = self.session.request(method, url, timeout=timeout, **kwargs)
            last_response = response

            if self._should_wait_for_rate_limit(response):
                self._sleep_until_rate_limit_reset(response)
                continue

            if response.status_code in (500, 502, 503, 504):
                time.sleep(min(5 * (attempt + 1), 30))
                continue

            if response.status_code == 403 and self._is_secondary_rate_limit(response):
                time.sleep(min(15 * (attempt + 1), 60))
                continue

            response.raise_for_status()
            return response

        if last_response is None:
            raise RuntimeError(f"No response received for {method} {url}.")

        last_response.raise_for_status()
        return last_response

    def _should_wait_for_rate_limit(self, response: requests.Response) -> bool:
        if not self.config.sleep_on_rate_limit or response.status_code != 403:
            return False
        return self._looks_like_rate_limit(response)

    @staticmethod
    def _looks_like_rate_limit(response: requests.Response) -> bool:
        message = ""
        try:
            payload = response.json()
            message = str(payload.get("message", ""))
        except ValueError:
            message = response.text
        return "rate limit" in message.lower()

    def _sleep_until_rate_limit_reset(self, response: requests.Response) -> None:
        reset_at = int(response.headers.get("X-RateLimit-Reset", "0") or "0")
        now = int(time.time())
        sleep_for = max(reset_at - now + 5, 30)
        time.sleep(sleep_for)

    @staticmethod
    def _is_secondary_rate_limit(response: requests.Response) -> bool:
        if response.status_code != 403:
            return False
        try:
            payload = response.json()
        except ValueError:
            return False
        message = str(payload.get("message", ""))
        return "secondary rate limit" in message.lower()
