from types import SimpleNamespace

import anthropic

from app import briefing as briefing_module
from app import main


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["vault_ok"] is True
    assert body["notes"] > 0
    assert body["api_key_configured"] is False


def test_health_degraded_without_vault(client, settings, tmp_path):
    settings.vault_path = tmp_path / "missing"
    assert client.get("/health").json()["status"] == "degraded"
    assert client.get("/tasks").status_code == 503


def test_tasks(client):
    body = client.get("/tasks").json()
    assert body["open"] == len(body["tasks"])
    assert body["overdue"] == 2
    assert all(not t["done"] for t in body["tasks"])
    assert body["tasks"][0]["priority"] == 1


def test_tasks_include_done_and_limit(client):
    assert any(t["done"] for t in client.get("/tasks?include_done=true").json()["tasks"])
    assert len(client.get("/tasks?limit=2").json()["tasks"]) == 2


def test_study(client):
    (roadmap,) = client.get("/study").json()["roadmaps"]
    assert roadmap["current"]["title"] == "Cloud Concepts, 24 %"


def test_pet(client):
    body = client.get("/pet").json()
    assert body["name"] == "Zebot"
    assert body["difficulty"] == "normal"


def test_briefing_fallback_without_api_key_is_not_cached(client):
    first = client.get("/briefing").json()
    assert first["source"] == "fallback"
    assert "Zebot" in first["text"]
    assert client.get("/briefing").json()["source"] == "fallback"


def test_briefing_is_cached_per_day(client, monkeypatch):
    calls = []

    def fake_generate(settings, context, difficulty):
        calls.append(context)
        return f"GG #{len(calls)}", "claude"

    monkeypatch.setattr(main, "generate_briefing", fake_generate)
    assert client.get("/briefing").json()["source"] == "claude"
    cached = client.get("/briefing").json()
    assert (cached["source"], cached["text"]) == ("cache", "GG #1")
    assert client.get("/briefing?refresh=true").json()["text"] == "GG #2"
    assert len(calls) == 2


def test_briefing_refresh_limit(client, settings, monkeypatch):
    settings.briefing_max_refresh_per_day = 1
    monkeypatch.setattr(main, "generate_briefing", lambda s, c, d: ("GG", "claude"))
    client.get("/briefing")
    assert client.get("/briefing?refresh=true").status_code == 200
    assert client.get("/briefing?refresh=true").status_code == 429


# --- Claude call (SDK mocked: tests never hit the real API) -------------------


class FakeMessages:
    def __init__(self, result):
        self.result = result
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def fake_client(monkeypatch, result) -> FakeMessages:
    messages = FakeMessages(result)
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: SimpleNamespace(messages=messages))
    return messages


CONTEXT = {"pendientes_prioritarios": [{"tarea": "Leer la guía", "proyecto": "CLF"}], "estudio": []}


def test_generate_briefing_calls_claude(settings, monkeypatch):
    settings.anthropic_api_key = "sk-test"
    response = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="¡GG, Zeb!")],
        stop_reason="end_turn",
        usage=SimpleNamespace(output_tokens=10),
        _request_id="req_1",
    )
    messages = fake_client(monkeypatch, response)
    text, source = briefing_module.generate_briefing(settings, CONTEXT, "hardcore")
    assert (text, source) == ("¡GG, Zeb!", "claude")
    assert messages.kwargs["model"] == "claude-haiku-4-5"
    assert "hardcore" in messages.kwargs["system"]
    assert "Leer la guía" in messages.kwargs["messages"][0]["content"]


def test_generate_briefing_falls_back_on_connection_error(settings, monkeypatch):
    settings.anthropic_api_key = "sk-test"
    fake_client(monkeypatch, anthropic.APIConnectionError(request=SimpleNamespace(method="POST", url="https://x")))
    text, source = briefing_module.generate_briefing(settings, CONTEXT, "normal")
    assert source == "fallback"
    assert "Leer la guía" in text


def test_generate_briefing_falls_back_on_refusal(settings, monkeypatch):
    settings.anthropic_api_key = "sk-test"
    response = SimpleNamespace(content=[], stop_reason="refusal", usage=None, _request_id="r")
    fake_client(monkeypatch, response)
    assert briefing_module.generate_briefing(settings, CONTEXT, "normal")[1] == "fallback"
