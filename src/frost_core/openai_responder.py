from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from .conversation_loop import Json, ResponderStep, ToolCall


class OpenAIResponsesResponder:
    """Thin OpenAI Responses API adapter for the provider-neutral conversation loop."""

    provider_id = "openai_responses"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout_seconds: int = 120,
        max_response_bytes: int = 4_000_000,
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model or os.environ.get("FROST_AI_MODEL", "gpt-5.6")
        self.base_url = base_url or os.environ.get(
            "OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses"
        )
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the OpenAI responder")
        if not self.model.strip():
            raise RuntimeError("FROST_AI_MODEL/model must not be empty")
        if not self.base_url.startswith("https://"):
            raise RuntimeError("OpenAI Responses URL must use https")

    def respond(
        self,
        *,
        input_items: list[Json],
        previous_response_id: str | None,
        tools: list[Json],
        instructions: str,
    ) -> ResponderStep:
        payload: Json = {
            "model": self.model,
            "instructions": instructions,
            "input": input_items,
            "tools": tools,
            "parallel_tool_calls": False,
        }
        if previous_response_id:
            payload["previous_response_id"] = previous_response_id
        response = self._post(payload)
        return self._parse(response)

    def _post(self, payload: Json) -> Json:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.base_url,
            data=body,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "centinal26-frost-conversation/1.0",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(self.max_response_bytes + 1)
        except urllib.error.HTTPError as exc:
            detail = exc.read(64_000).decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI responder HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI responder transport failure: {exc.reason}") from exc
        if len(raw) > self.max_response_bytes:
            raise RuntimeError("OpenAI responder payload exceeded local size limit")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenAI responder returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise RuntimeError("OpenAI responder returned a non-object payload")
        return parsed

    @staticmethod
    def _parse(response: Json) -> ResponderStep:
        response_id = str(response.get("id") or "")
        if not response_id:
            raise RuntimeError("OpenAI response has no id")
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        output = response.get("output") or []
        if not isinstance(output, list):
            raise RuntimeError("OpenAI response output is not a list")
        for item in output:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            if item_type == "message":
                content = item.get("content") or []
                if not isinstance(content, list):
                    continue
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "output_text":
                        text = part.get("text")
                        if isinstance(text, str):
                            text_parts.append(text)
            elif item_type == "function_call":
                call_id = str(item.get("call_id") or "")
                name = str(item.get("name") or "")
                arguments_raw = item.get("arguments", "{}")
                if not call_id or not name:
                    raise RuntimeError("OpenAI function call is missing call_id/name")
                if isinstance(arguments_raw, str):
                    try:
                        arguments = json.loads(arguments_raw)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            f"OpenAI function call {call_id} has invalid JSON arguments"
                        ) from exc
                elif isinstance(arguments_raw, dict):
                    arguments = arguments_raw
                else:
                    raise RuntimeError(
                        f"OpenAI function call {call_id} arguments are not an object/string"
                    )
                if not isinstance(arguments, dict):
                    raise RuntimeError(f"OpenAI function call {call_id} arguments are not an object")
                tool_calls.append(ToolCall(call_id=call_id, name=name, arguments=arguments))
        return ResponderStep(
            response_id=response_id,
            text="\n".join(text_parts).strip(),
            tool_calls=tuple(tool_calls),
            metadata={
                "status": response.get("status"),
                "usage": response.get("usage"),
            },
        )
