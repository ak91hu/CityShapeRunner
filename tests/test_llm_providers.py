from __future__ import annotations

from types import SimpleNamespace

from gps_art_wizzard.llm.anthropic_provider import (
    AnthropicProvider,
    _supports_structured_outputs,
)
from gps_art_wizzard.llm.base import Message
from gps_art_wizzard.llm.ollama_provider import OllamaProvider
from gps_art_wizzard.llm.openai_provider import (
    OpenAIProvider,
)
from gps_art_wizzard.llm.openai_provider import (
    _supports_structured_outputs as openai_supports_structured_outputs,
)

_SCHEMA = {
    "type": "object",
    "properties": {"closed": {"type": "boolean"}},
    "required": ["closed"],
    "additionalProperties": False,
}


class _Recorder:
    def __init__(self, response):
        self.kwargs = None
        self._response = response

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


def test_openai_provider_uses_strict_json_schema_when_supplied():
    recorder = _Recorder(
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"closed":true}'))],
            usage=None,
        )
    )
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    provider._model = "gpt-4o-mini"
    provider._temperature = 0.2
    provider._max_tokens = 256

    provider.complete(
        [Message(role="user", content="draw")],
        json_mode=True,
        json_schema=_SCHEMA,
    )

    assert recorder.kwargs is not None
    response_format = recorder.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] is _SCHEMA


def test_openai_provider_keeps_legacy_models_on_json_mode():
    recorder = _Recorder(
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"closed":true}'))],
            usage=None,
        )
    )
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    provider._model = "gpt-3.5-turbo"
    provider._temperature = 0.2
    provider._max_tokens = 256

    provider.complete(
        [Message(role="user", content="draw")],
        json_schema=_SCHEMA,
    )

    assert recorder.kwargs is not None
    assert recorder.kwargs["response_format"] == {"type": "json_object"}
    assert openai_supports_structured_outputs("gpt-4o-mini") is True
    assert openai_supports_structured_outputs("gpt-3.5-turbo") is False


def test_ollama_provider_sends_schema_in_native_format(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": '{"closed":true}'}}

    def post(_url, *, json, timeout):
        captured.update(json)
        assert timeout == 120.0
        return Response()

    monkeypatch.setattr("gps_art_wizzard.llm.ollama_provider.httpx.post", post)
    provider = OllamaProvider("http://localhost:11434", model="test-model")

    provider.complete(
        [Message(role="user", content="draw")],
        json_mode=True,
        json_schema=_SCHEMA,
    )

    assert captured["format"] is _SCHEMA


def test_anthropic_schema_is_gated_by_model_support():
    assert _supports_structured_outputs("claude-sonnet-4-5-20250929") is True
    assert _supports_structured_outputs("claude-opus-4-6") is True
    assert _supports_structured_outputs("claude-3-5-sonnet-latest") is False
    assert _supports_structured_outputs("company-proxy-model") is False


def test_anthropic_provider_keeps_legacy_models_compatible():
    recorder = _Recorder(
        SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"closed":true}')],
            usage=None,
        )
    )
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._client = SimpleNamespace(messages=recorder)
    provider._model = "claude-3-5-sonnet-latest"
    provider._temperature = 0.2
    provider._max_tokens = 256

    provider.complete(
        [Message(role="user", content="draw")],
        json_mode=True,
        json_schema=_SCHEMA,
    )

    assert recorder.kwargs is not None
    assert "output_config" not in recorder.kwargs


def test_anthropic_provider_uses_schema_on_supported_models():
    recorder = _Recorder(
        SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"closed":true}')],
            usage=None,
        )
    )
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider._client = SimpleNamespace(messages=recorder)
    provider._model = "claude-sonnet-4-5-20250929"
    provider._temperature = 0.2
    provider._max_tokens = 256

    provider.complete(
        [Message(role="user", content="draw")],
        json_schema=_SCHEMA,
    )

    assert recorder.kwargs is not None
    assert recorder.kwargs["output_config"] == {
        "format": {"type": "json_schema", "schema": _SCHEMA}
    }
