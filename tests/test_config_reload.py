import asyncio
from pathlib import Path

from embykeeper.config import ConfigManager


def test_reload_conf_keeps_file_observer(monkeypatch, tmp_path: Path):
    config_file = tmp_path / "config.toml"
    config_file.write_text("[telegram]\naccount = []\n", encoding="utf-8")

    manager = ConfigManager()
    calls = 0

    async def fake_start_observer(self):
        nonlocal calls
        calls += 1
        self._observer = asyncio.Future()

    monkeypatch.setattr(ConfigManager, "start_observer", fake_start_observer)

    assert asyncio.run(manager.reload_conf(config_file)) is True
    assert manager._conf_file == config_file
    assert calls == 1

    config_file.write_text("[telegram]\naccount = []\n[checkiner]\ntimeout = 180\n", encoding="utf-8")
    assert asyncio.run(manager.reload_conf(config_file)) is True
    assert manager._conf_file == config_file
    assert calls == 1
    assert manager.checkiner.timeout == 180


def test_set_can_preserve_observed_config_file(tmp_path: Path):
    config_file = tmp_path / "config.toml"
    manager = ConfigManager(config_file)

    assert manager.set({"telegram": {"account": []}}, keep_conf_file=True)
    assert manager._conf_file == config_file

    assert manager.set({"telegram": {"account": []}})
    assert manager._conf_file is None
