from __future__ import annotations

from types import SimpleNamespace

import pytest

from gps_art_wizzard.llm.anthropic_provider import (
    AnthropicProvider,
    _supports_structured_outputs,
)
from gps_art_wizzard.llm.base import ImageInput, LLMError, Message
from gps_art_wizzard.llm.ollama_provider import OllamaProvider
from gps_art_wizzard.llm.openai_provider import (
    OpenAIProvider,
)
from gps_art_wizzard.llm.openai_provider import (
    _supports_structured_outputs as openai_supports_structured_outputs,
)
from gps_art_wizzard.llm.opencode_provider import OpenCodeProvider

_SCHEMA = {
    "type": "object",
    "properties": {"closed": {"type": "boolean"}},
    "required": ["closed"],
    "additionalProperties": False,
}
_PNG = ImageInput("data:image/png;base64,iVBORw0KGgo=")


class _Recorder:
    def __init__(self, response):
        self.kwargs = None
        self._response = response

    def create(self, **kwargs):
        self.kwargs = kwargs
        return self._response


def test_opencode_provider_uses_responses_schema_model_for_structured_calls():
    recorder = _Recorder(
        SimpleNamespace(
            output_text='{"closed":true}',
            status="completed",
            usage=SimpleNamespace(input_tokens=12, output_tokens=5),
        )
    )
    provider = OpenCodeProvider.__new__(OpenCodeProvider)
    provider._client = SimpleNamespace(responses=recorder)
    provider._model = "deepseek-v4-flash"
    provider._structured_model = "gpt-5.4-mini"
    provider._temperature = 0.2
    provider._max_tokens = 256

    response = provider.complete(
        [Message(role="user", content="draw")],
        json_mode=True,
        json_schema=_SCHEMA,
        system="Return JSON only.",
    )

    assert recorder.kwargs is not None
    assert recorder.kwargs["model"] == "gpt-5.4-mini"
    assert recorder.kwargs["input"] == [
        {"role": "system", "content": "Return JSON only."},
        {"role": "user", "content": "draw"},
    ]
    assert recorder.kwargs["text"]["format"] == {
        "type": "json_schema",
        "name": "gps_art_structured_response",
        "strict": True,
        "schema": _SCHEMA,
    }
    assert recorder.kwargs["reasoning"] == {"effort": "low"}
    assert recorder.kwargs["max_output_tokens"] == 256
    assert response.text == '{"closed":true}'
    assert response.model == "gpt-5.4-mini"
    assert response.usage == {"prompt": 12, "completion": 5}


def test_opencode_provider_rejects_incomplete_structured_output():
    recorder = _Recorder(
        SimpleNamespace(
            output_text='{"closed":',
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            usage=None,
        )
    )
    provider = OpenCodeProvider.__new__(OpenCodeProvider)
    provider._client = SimpleNamespace(responses=recorder)
    provider._model = "deepseek-v4-flash"
    provider._structured_model = "gpt-5.4-mini"
    provider._temperature = 0.2
    provider._max_tokens = 256

    with pytest.raises(LLMError, match="max_output_tokens"):
        provider.complete(
            [Message(role="user", content="draw")],
            json_schema=_SCHEMA,
        )


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


def test_openai_provider_uses_responses_api_for_visual_schema_review():
    recorder = _Recorder(
        SimpleNamespace(
            output_text='{"closed":true}',
            status="completed",
            usage=SimpleNamespace(input_tokens=20, output_tokens=5),
        )
    )
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider._client = SimpleNamespace(responses=recorder)
    provider._model = "gpt-4o-mini"
    provider._temperature = 0.2
    provider._max_tokens = 256

    response = provider.complete(
        [Message(role="user", content="review")],
        json_schema=_SCHEMA,
        images=[_PNG],
    )

    blocks = recorder.kwargs["input"][0]["content"]
    assert blocks[0] == {"type": "input_text", "text": "review"}
    assert blocks[1]["type"] == "input_image"
    assert blocks[1]["image_url"] == _PNG.data_url
    assert recorder.kwargs["text"]["format"]["schema"] is _SCHEMA
    assert response.usage == {"prompt": 20, "completion": 5}


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


def test_ollama_provider_attaches_base64_images_to_user_message(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"message": {"content": '{"closed":true}'}}

    def post(_url, *, json, timeout):
        captured.update(json)
        return Response()

    monkeypatch.setattr("gps_art_wizzard.llm.ollama_provider.httpx.post", post)
    provider = OllamaProvider("http://localhost:11434", model="vision-model")
    provider.complete([Message(role="user", content="review")], images=[_PNG])

    assert captured["messages"][0]["images"] == ["iVBORw0KGgo="]


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


def test_anthropic_provider_converts_inline_image_to_native_block():
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
        [Message(role="user", content="review")],
        json_schema=_SCHEMA,
        images=[_PNG],
    )

    blocks = recorder.kwargs["messages"][0]["content"]
    assert blocks[0] == {"type": "text", "text": "review"}
    assert blocks[1]["source"] == {
        "type": "base64",
        "media_type": "image/png",
        "data": "iVBORw0KGgo=",
    }


# --------------------------------------------------------------------------- #
# Factory behaviour: fallback rotation, stickiness, cooldowns, budgets        #
# --------------------------------------------------------------------------- #
from gps_art_wizzard.llm import factory as llm_factory  # noqa: E402
from gps_art_wizzard.llm.base import LLMResponse, NoProviderError  # noqa: E402
from gps_art_wizzard.state import WorkflowState  # noqa: E402
from gps_art_wizzard.workflow_runtime import WorkflowRuntime  # noqa: E402


class _StubProvider:
    def __init__(self, name, *, available=True, response=None, error=None):
        self.name = name
        self._available = available
        self._response = response or LLMResponse(
            text="ok", provider=name, model="stub", usage={}, raw=None
        )
        self._error = error
        self.probe_count = 0
        self.calls = 0

    def is_available(self) -> bool:
        self.probe_count += 1
        return self._available

    def complete(self, **_kwargs):
        self.calls += 1
        if self._error is not None:
            raise LLMError(self._error)
        return self._response


@pytest.fixture
def isolated_factory():
    llm_factory.reset_sticky()
    yield llm_factory
    llm_factory.reset_sticky()


def _install_providers(monkeypatch, *providers):
    monkeypatch.setattr(llm_factory, "available_providers", lambda: tuple(providers))
    return providers


def _fallback():
    return "deterministic"


def test_try_complete_rotates_to_the_next_provider_and_pins_it(isolated_factory, monkeypatch):
    failing, working = _install_providers(
        monkeypatch,
        _StubProvider("first", error="boom"),
        _StubProvider("second"),
    )

    response = llm_factory.try_complete(_fallback, prompt="x")

    assert response.provider == "second"
    assert failing.calls == 1
    assert working.calls == 1
    assert llm_factory._probe_in_cooldown("first")  # failure opened a cooldown
    assert llm_factory.get_llm() is working  # sticky pinning skips the probe


def test_try_complete_reports_provider_failure_to_the_workflow_trace(
    isolated_factory, monkeypatch
):
    a, b = _install_providers(
        monkeypatch,
        _StubProvider("a", error="down"),
        _StubProvider("b", error="also down"),
    )
    runtime = WorkflowRuntime(WorkflowState(prompt="trace"), max_duration_seconds=60, max_llm_calls=8)

    with runtime.activate():
        result = llm_factory.try_complete(_fallback)

    assert result == "deterministic"
    assert a.calls == 1 and b.calls == 1
    assert runtime.trace.deterministic_fallbacks == 1
    assert "llm_fallback:provider_failure" in runtime.trace.degraded_reasons
    assert runtime.trace.llm_attempts == 2
    assert runtime.trace.error_category is None  # quality stays separate


def test_try_complete_honours_an_exhausted_deadline_without_calling_providers(
    isolated_factory, monkeypatch
):
    clock = {"now": 0.0}
    provider = _install_providers(monkeypatch, _StubProvider("only"))[0]
    state = WorkflowState(prompt="deadline")
    runtime = WorkflowRuntime(state, max_duration_seconds=5, max_llm_calls=8, clock=lambda: clock["now"])
    clock["now"] = 99.0  # budget blown before the first call

    with runtime.activate():
        result = llm_factory.try_complete(_fallback)

    assert result == "deterministic"
    assert provider.calls == 0
    assert provider.probe_count == 0  # never even probed for availability
    assert runtime.trace.llm_attempts == 0
    assert "llm_fallback:deadline_exceeded" in runtime.trace.degraded_reasons


def test_try_complete_honours_an_exhausted_call_budget(isolated_factory, monkeypatch):
    provider = _install_providers(monkeypatch, _StubProvider("only"))[0]
    state = WorkflowState(prompt="budget")
    runtime = WorkflowRuntime(state, max_duration_seconds=60, max_llm_calls=0)

    with runtime.activate():
        result = llm_factory.try_complete(_fallback)

    assert result == "deterministic"
    assert provider.calls == 0
    assert "llm_fallback:call_budget_exhausted" in runtime.trace.degraded_reasons


def test_exclude_provider_skips_a_broken_primary_entirely(isolated_factory, monkeypatch):
    broken, healthy = _install_providers(
        monkeypatch,
        _StubProvider("broken", error="nope"),
        _StubProvider("healthy"),
    )

    response = llm_factory.try_complete(
        _fallback, exclude_provider="broken", prompt="x"
    )

    assert response.provider == "healthy"
    assert broken.calls == 0 and broken.probe_count == 0
    assert llm_factory._probe_in_cooldown("broken") is False  # never penalised


def test_pin_provider_false_leaves_sticky_unset(isolated_factory, monkeypatch):
    provider = _install_providers(monkeypatch, _StubProvider("solo"))[0]

    llm_factory.try_complete(_fallback, pin_provider=False, prompt="x")

    assert provider.calls == 1
    assert llm_factory._STICKY is None  # noqa: SLF001 - success was not pinned


def test_max_provider_attempts_stops_after_the_first_failure(isolated_factory, monkeypatch):
    first, second = _install_providers(
        monkeypatch,
        _StubProvider("first", error="fail"),
        _StubProvider("second"),
    )

    result = llm_factory.try_complete(_fallback, max_provider_attempts=1)

    assert result == "deterministic"
    assert first.calls == 1
    assert second.calls == 0  # attempt cap reached before trying the backup


def test_get_llm_raises_no_provider_error_when_every_probe_fails(
    isolated_factory, monkeypatch
):
    _install_providers(monkeypatch, _StubProvider("down", available=False))

    with pytest.raises(NoProviderError):
        llm_factory.get_llm()


# --------------------------------------------------------------------------- #
# Provider-level error wrapping                                               #
# --------------------------------------------------------------------------- #
def test_opencode_provider_wraps_transport_errors_as_llm_errors():
    class _Exploding:
        class chat:  # noqa: N801 - mirrors the SDK attribute chain
            class completions:
                @staticmethod
                def create(**_kwargs):
                    raise RuntimeError("connection reset")

    provider = OpenCodeProvider.__new__(OpenCodeProvider)
    provider._client = SimpleNamespace(chat=_Exploding())
    provider._model = "glm-5.2"
    provider._structured_model = ""
    provider._temperature = 0.2
    provider._max_tokens = 128

    with pytest.raises(LLMError, match="OpenCode Zen call failed"):
        provider.complete([Message(role="user", content="hi")])


def test_opencode_provider_maps_usage_into_the_response():
    recorder = _Recorder(
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="hello"))],
            usage=SimpleNamespace(prompt_tokens=7, completion_tokens=3),
        )
    )
    provider = OpenCodeProvider.__new__(OpenCodeProvider)
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=recorder))
    provider._model = "glm-5.2"
    provider._structured_model = ""
    provider._temperature = 0.2
    provider._max_tokens = 128

    response = provider.complete([Message(role="user", content="hi")])

    assert response.text == "hello"
    assert response.usage == {"prompt": 7, "completion": 3}
