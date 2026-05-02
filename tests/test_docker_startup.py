import os
import subprocess
from pathlib import Path


def _write_fake_command(tmp_path: Path, name: str) -> None:
    command = tmp_path / name
    command.write_text(
        "#!/bin/sh\n"
        f"printf '{name}'\n"
        "for arg in \"$@\"; do\n"
        "  printf ' %s' \"$arg\"\n"
        "done\n"
        "printf '\\n'\n",
        encoding="utf-8",
    )
    command.chmod(0o755)


def _run_entrypoint(tmp_path: Path, env: dict[str, str] | None = None, args: list[str] | None = None) -> str:
    root = Path(__file__).resolve().parents[1]
    entrypoint = root / "scripts" / "docker-entrypoint.sh"
    _write_fake_command(tmp_path, "embykeeper")
    _write_fake_command(tmp_path, "embykeeperweb")
    result = subprocess.run(
        ["bash", str(entrypoint), *(args or [])],
        env={"PATH": f"{tmp_path}:{os.environ['PATH']}", **(env or {})},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_docker_entrypoint_runs_worker_instantly_by_default(tmp_path: Path):
    assert _run_entrypoint(tmp_path) == "embykeeper --basedir /app --instant"


def test_docker_entrypoint_keeps_worker_mode_even_with_web_password(tmp_path: Path):
    assert _run_entrypoint(tmp_path, {"EK_WEBPASS": "configured-password"}) == (
        "embykeeper --basedir /app --instant"
    )


def test_docker_entrypoint_appends_user_command_after_instant(tmp_path: Path):
    assert _run_entrypoint(tmp_path, args=["--emby"]) == "embykeeper --basedir /app --instant --emby"


def test_fnos_compose_restarts_after_host_boot_without_web_console():
    compose_file = Path(__file__).resolve().parents[1] / "deploy" / "docker-compose.fnos.yml"
    content = compose_file.read_text(encoding="utf-8")
    assert "restart: always" in content
    assert "network_mode: host" in content
    assert "EK_ENABLE_WEB" not in content
    assert "EK_WEBPASS" not in content
    assert "ports:" not in content


def test_complete_compose_example_documents_instant_worker_deployment():
    compose_file = Path(__file__).resolve().parents[1] / "deploy" / "docker-compose.example.yml"
    content = compose_file.read_text(encoding="utf-8")
    assert "image: ghcr.io/coldboy404/emby-keeper:main" in content
    assert "restart: always" in content
    assert "每次启动/重启都会自动执行一次任务" in content
    assert "--instant" in content
    assert "network_mode: host" in content
    assert "./app:/app" in content
    assert "EK_ENABLE_WEB" not in content
    assert "EK_WEBPASS" not in content
    assert '"1818:1818"' not in content
