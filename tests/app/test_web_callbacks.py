"""Tests for safe local Gradio callback behavior."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from visolexnorm.app import inference, web


def test_callback_returns_normalized_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.inference, "normalize", lambda text: f"đã chuẩn hóa: {text}")

    assert web.normalize_text("mik ko bt") == (
        "đã chuẩn hóa: mik ko bt",
        "✓ Đã chuẩn hóa thành công trên thiết bị này.",
    )


def test_callback_returns_validation_message_without_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(text: str) -> str:
        del text
        raise inference.InputValidationError("Vui lòng nhập văn bản cần chuẩn hóa.")

    monkeypatch.setattr(web.inference, "normalize", fail)

    assert web.normalize_text(" ") == ("", "Vui lòng nhập văn bản cần chuẩn hóa.")


def test_callback_hides_runtime_details(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(text: str) -> str:
        del text
        raise RuntimeError("internal checkpoint path and stack details")

    monkeypatch.setattr(web.inference, "normalize", fail)

    output, status = web.normalize_text("mik ko bt")

    assert output == ""
    assert "internal checkpoint" not in status
    assert status == "Không thể chuẩn hóa lúc này. Hãy kiểm tra mô hình và thử lại."


def test_clear_text_resets_all_visible_fields() -> None:
    assert web.clear_text() == ("", "", web.READY_STATUS)


def test_main_binds_loopback_without_public_share(monkeypatch: pytest.MonkeyPatch) -> None:
    demo = object()
    launches: list[tuple[object, int | None]] = []

    monkeypatch.setattr(web, "create_demo", lambda: demo)
    monkeypatch.setattr(web, "launch_demo", lambda current_demo, *, port: launches.append((current_demo, port)))
    monkeypatch.setattr(sys, "argv", ["web.py", "--port", "7865"])

    web.main()

    assert launches == [(demo, 7865)]


def test_launch_demo_uses_loopback_and_never_enables_share(monkeypatch: pytest.MonkeyPatch) -> None:
    launches: list[dict[str, object]] = []

    class Demo:
        def launch(self, **kwargs: object) -> str:
            launches.append(kwargs)
            return "started"

    theme = object()
    monkeypatch.setitem(sys.modules, "gradio", SimpleNamespace(themes=SimpleNamespace(Soft=lambda **kwargs: theme)))

    assert web.launch_demo(Demo(), port=7865) == "started"
    assert launches[0]["server_name"] == "127.0.0.1"
    assert launches[0]["server_port"] == 7865
    assert launches[0]["share"] is False
    assert launches[0]["theme"] is theme
    assert launches[0]["css"] == web.CUSTOM_CSS


def test_web_source_has_no_gemini_dependency() -> None:
    assert "GEMINI_API_KEYS" not in web.__dict__.get("CUSTOM_CSS", "")
    assert "gemini" not in web.__doc__.lower()