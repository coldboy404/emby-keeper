from types import SimpleNamespace

from embykeeper.telegram.checkin_main import CheckinerManager


class DummyConfig:
    interval_days = "1"
    time_range = "<6:00AM,7:00AM>"
    random_start = 40

    def __init__(self, site_configs=None):
        self.site_configs = site_configs or {}

    def get_site_config(self, site):
        return self.site_configs.get(site, {})


def test_site_time_range_triggers_independent_schedule():
    manager = CheckinerManager.__new__(CheckinerManager)
    config = DummyConfig({"templ_c<3849837200>": {"time_range": "8:00AM"}})

    assert manager._has_independent_schedule("templ_c<3849837200>", config) is True
    assert manager._has_independent_time_range("templ_c<3849837200>", config) is True


def test_site_interval_days_triggers_independent_schedule():
    manager = CheckinerManager.__new__(CheckinerManager)
    config = DummyConfig({"templ_b<bean21bot>": {"interval_days": "2"}})

    assert manager._has_independent_schedule("templ_b<bean21bot>", config) is True


def test_site_random_start_alone_does_not_trigger_independent_schedule():
    manager = CheckinerManager.__new__(CheckinerManager)
    config = DummyConfig({"templ_b<emospg_bot>": {"random_start": 3}})

    assert manager._has_independent_schedule("templ_b<emospg_bot>", config) is False


def test_site_random_start_overrides_global_default():
    manager = CheckinerManager.__new__(CheckinerManager)
    config = DummyConfig()

    assert manager._get_site_random_start({"random_start": 3}, config) == 3
    assert manager._get_site_random_start({}, config) == 40
    assert manager._get_site_random_start({"random_start": 0}, config) == 0
