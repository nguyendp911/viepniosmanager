from types import SimpleNamespace
import pytest
from viepn import tools


def test_tool_error_keeps_both_streams_and_final_device_error(monkeypatch):
    monkeypatch.setattr(tools.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1,
        stderr="Uploading IPA...\n" + "progress\n" * 300,
        stdout="Device installation rejected: ApplicationVerificationFailed 0xe8008016",
    ))
    with pytest.raises(tools.ExternalToolError) as error:
        tools.run(["pymobiledevice3", "apps", "install"])
    message = str(error.value)
    assert "stderr:" in message
    assert "stdout:" in message
    assert "0xe8008016" in message


def test_tool_error_redacts_secret_before_truncation(monkeypatch):
    monkeypatch.setattr(tools.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
        returncode=1, stderr="secret-token " + "x" * 15000, stdout="secret-token rejected",
    ))
    with pytest.raises(tools.ExternalToolError) as error:
        tools.run(["example"], secret="secret-token")
    assert "secret-token" not in str(error.value)
    assert "[REDACTED] rejected" in str(error.value)
