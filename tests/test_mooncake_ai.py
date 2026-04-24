import asyncio
from types import SimpleNamespace

from embykeeper.telegram.checkiner.mooncake_ai import MooncakeAICheckin


class DummyLog:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class DummyMessage:
    def __init__(self, *, text=None, photo=False, reply_markup=None):
        self.text = text
        self.caption = None
        self.photo = photo
        self.reply_markup = reply_markup
        self.edit_date = None
        self.is_first_response = False
        self.clicked = []

    async def click(self, button):
        self.clicked.append(button)
        return SimpleNamespace(message="签到成功")


class DummyMarkup:
    def __init__(self, buttons):
        self.inline_keyboard = [[SimpleNamespace(text=button) for button in buttons]]


def make_checkiner():
    checkiner = MooncakeAICheckin.__new__(MooncakeAICheckin)
    checkiner.log = DummyLog()
    checkiner._captcha_options_event = asyncio.Event()
    checkiner._captcha_options_message = None
    checkiner.llm_button_match_threshold = 70
    checkiner.bot_checkin_button = ["签到"]
    checkiner.templ_panel_keywords = None
    return checkiner


def test_mooncake_options_message_without_prompt_text_is_cached():
    checkiner = make_checkiner()
    message = DummyMessage(text="请选择", reply_markup=DummyMarkup(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]))

    assert checkiner.is_captcha_options_message(message, message.text)


def test_mooncake_photo_uses_cached_options_message_when_options_arrive_first(monkeypatch):
    checkiner = make_checkiner()
    option_message = DummyMessage(
        text="请选择",
        reply_markup=DummyMarkup(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]),
    )
    photo_message = DummyMessage(photo=True)
    checkiner.remember_captcha_options_message(option_message)

    async def fake_download_media(message, in_memory=True):
        return b"image"

    async def fake_solve_with_llm(image, options):
        assert image == b"image"
        assert "7" in options
        return "验证码是 7"

    async def fake_on_captcha_button_answer(result):
        checkiner.result = result

    checkiner.client = SimpleNamespace(download_media=fake_download_media)
    monkeypatch.setattr(checkiner, "solve_with_llm", fake_solve_with_llm)
    monkeypatch.setattr(checkiner, "on_captcha_button_answer", fake_on_captcha_button_answer)

    asyncio.run(checkiner.on_photo(photo_message))

    assert option_message.clicked == ["7"]
    assert checkiner.result.message == "签到成功"
