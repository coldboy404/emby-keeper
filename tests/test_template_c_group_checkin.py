import asyncio
from types import SimpleNamespace

from embykeeper.telegram.dynamic import get_cls
from embykeeper.telegram.checkiner._templ_c import TemplateCCheckin


class DummyLog:
    def warning(self, *args, **kwargs):
        pass


class DummyClient:
    def __init__(self):
        self.me = SimpleNamespace(full_name="tester")
        self.sent = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        return SimpleNamespace(id=len(self.sent))


class DummyCtx:
    def __init__(self):
        self.status = None
        self.status_info = None


def make_template_c(bot_username="3849837200", config=None):
    checkiner = TemplateCCheckin.__new__(TemplateCCheckin)
    checkiner.bot_username = bot_username
    checkiner.name = None
    checkiner.config = config or {}
    checkiner.client = DummyClient()
    checkiner.ctx = DummyCtx()
    checkiner.log = DummyLog()
    checkiner.finished = asyncio.Event()
    return checkiner


def test_dynamic_template_accepts_negative_group_id():
    cls = get_cls("checkiner", names=["templ_c<-1003849837200>"])[0]

    assert cls.templ_name == "templ_c<-1003849837200>"
    assert cls.bot_username == "-1003849837200"


def test_template_c_normalizes_private_openmessage_chat_id():
    checkiner = make_template_c(
        config={
            "name": "公益plus群组签到",
            "bot_checkin_cmd": "/checkin@usernamebot",
        }
    )

    assert asyncio.run(checkiner.init_group_checkin()) is True
    assert checkiner.chat_name == -1003849837200
    assert checkiner.bot_username is None
    assert checkiner.bot_checkin_cmd == "/checkin@usernamebot"


def test_template_c_can_override_chat_id_in_config():
    checkiner = make_template_c(
        bot_username="fallback_group",
        config={
            "chat_id": "-1001234567890",
            "bot_checkin_cmd": "签到",
        },
    )

    assert asyncio.run(checkiner.init_group_checkin()) is True
    assert checkiner.chat_name == -1001234567890


def test_template_c_sends_group_command_and_finishes_without_waiting_response():
    checkiner = make_template_c(
        config={
            "bot_checkin_cmd": "/checkin@usernamebot",
            "wait_response": False,
        }
    )
    asyncio.run(checkiner.init_group_checkin())

    asyncio.run(checkiner.send_checkin())

    assert checkiner.client.sent == [(-1003849837200, "/checkin@usernamebot")]
    assert checkiner.ctx.status_info == "群组签到命令已发送"
    assert checkiner.finished.is_set()
