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


def _run_entrypoint(tmp_path: Path, env: dict[str, str]) -> str:
    root = Path(__file__).resolve().parents[1]
    entrypoint = root / "scripts" / "docker-entrypoint.sh"
    _write_fake_command(tmp_path, "embykeeper")
    _write_fake_command(tmp_path, "embykeeperweb")
    result = subprocess.run(
        ["bash", str(entrypoint), "--no-wait"],
        env={"PATH": f"{tmp_path}:{os.environ['PATH']}", **env},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_docker_entrypoint_defaults_to_worker_with_password_only(tmp_path: Path):
    assert _run_entrypoint(tmp_path, {"EK_WEBPASS": "configured-password"}) == (
        "embykeeper --basedir /app --no-wait"
    )


def test_docker_entrypoint_runs_web_when_explicitly_enabled(tmp_path: Path):
    assert _run_entrypoint(tmp_path, {"EK_ENABLE_WEB": "1", "EK_WEBPASS": "configured-password"}) == (
        "embykeeperweb --basedir /app --public --no-wait"
    )


def test_fnos_compose_restarts_after_host_boot_and_enables_web_console():
    compose_file = Path(__file__).resolve().parents[1] / "deploy" / "docker-compose.fnos.yml"
    content = compose_file.read_text(encoding="utf-8")
    assert "restart: always" in content
    assert 'EK_ENABLE_WEB: "1"' in content
