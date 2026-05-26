import asyncio
from types import SimpleNamespace

from pyrogram.errors import MessageIdInvalid

from embykeeper.runinfo import RunStatus
from embykeeper.telegram.checkiner.mooncake_ai import MooncakeAICheckin


class DummyLog:
    def __getattr__(self, name):
        return lambda *args, **kwargs: None


class DummyMessage:
    def __init__(self, *, text=None, photo=False, reply_markup=None, click_exception=None):
        self.text = text
        self.caption = None
        self.photo = photo
        self.reply_markup = reply_markup
        self.edit_date = None
        self.is_first_response = False
        self.clicked = []
        self.click_exception = click_exception

    async def click(self, button):
        self.clicked.append(button)
        if self.click_exception:
            raise self.click_exception
        return SimpleNamespace(message="签到成功")


class DummyMarkup:
    def __init__(self, buttons):
        self.inline_keyboard = [[SimpleNamespace(text=button) for button in buttons]]


def make_checkiner():
    checkiner = MooncakeAICheckin.__new__(MooncakeAICheckin)
    checkiner.log = DummyLog()
    checkiner.ctx = SimpleNamespace(status=None, status_info=None)
    checkiner.current_retries = 0
    checkiner.finished = asyncio.Event()
    checkiner._captcha_options_event = asyncio.Event()
    checkiner._captcha_options_message = None
    checkiner.llm_button_match_threshold = 95
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


def test_mooncake_photo_continues_after_first_successful_captcha_round(monkeypatch):
    checkiner = make_checkiner()
    first_option_message = DummyMessage(
        text="请选择",
        reply_markup=DummyMarkup(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]),
    )
    second_option_message = DummyMessage(
        text="请选择",
        reply_markup=DummyMarkup(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]),
    )
    first_photo_message = DummyMessage(photo=True)
    second_photo_message = DummyMessage(photo=True)
    checkiner.remember_captcha_options_message(first_option_message)

    async def fake_download_media(message, in_memory=True):
        return b"first-image" if message is first_photo_message else b"second-image"

    async def fake_solve_with_llm(image, options):
        return "7" if image == b"first-image" else "3"

    async def fake_on_captcha_button_answer(result):
        checkiner.results.append(result)

    checkiner.results = []
    checkiner.client = SimpleNamespace(download_media=fake_download_media)
    monkeypatch.setattr(checkiner, "solve_with_llm", fake_solve_with_llm)
    monkeypatch.setattr(checkiner, "on_captcha_button_answer", fake_on_captcha_button_answer)

    asyncio.run(checkiner.on_photo(first_photo_message))
    checkiner.remember_captcha_options_message(second_option_message)
    asyncio.run(checkiner.on_photo(second_photo_message))

    assert first_option_message.clicked == ["7"]
    assert second_option_message.clicked == ["3"]
    assert len(checkiner.results) == 2
    assert not checkiner.finished.is_set()


def test_mooncake_refuses_ambiguous_digit_answers():
    checkiner = make_checkiner()
    options = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]

    assert checkiner.match_button("可能是 3 或 8", options) is None


def test_mooncake_refuses_fuzzy_non_digit_answers():
    checkiner = make_checkiner()
    options = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]

    assert checkiner.match_button("返回", options) is None


def test_mooncake_retry_stops_without_resending_checkin(monkeypatch):
    checkiner = make_checkiner()
    sent = []

    async def fake_send_checkin(*args, **kwargs):
        sent.append((args, kwargs))

    monkeypatch.setattr(checkiner, "send_checkin", fake_send_checkin)

    asyncio.run(checkiner.retry())

    assert sent == []
    assert checkiner.finished.is_set()
    assert checkiner.ctx.status == RunStatus.FAIL
    assert checkiner.ctx.status_info == "月饼 AI 验证失败, 已停止自动重试"


def test_mooncake_click_failure_stops_without_waiting_for_global_timeout(monkeypatch):
    checkiner = make_checkiner()
    option_message = DummyMessage(
        text="请选择",
        reply_markup=DummyMarkup(["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]),
        click_exception=MessageIdInvalid,
    )
    photo_message = DummyMessage(photo=True)
    checkiner.remember_captcha_options_message(option_message)

    async def fake_download_media(message, in_memory=True):
        return b"image"

    async def fake_solve_with_llm(image, options):
        return "7"

    async def fake_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    checkiner.client = SimpleNamespace(download_media=fake_download_media)
    monkeypatch.setattr(checkiner, "solve_with_llm", fake_solve_with_llm)

    asyncio.run(checkiner.on_photo(photo_message))

    assert option_message.clicked == ["7"]
    assert checkiner.finished.is_set()
    assert checkiner.ctx.status == RunStatus.FAIL
    assert checkiner.ctx.status_info == "月饼 AI 验证失败, 已停止自动重试"


def test_mooncake_rejects_uncertain_single_digit_answer():
    checkiner = make_checkiner()
    options = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "返回"]

    assert checkiner.match_button("可能是 7", options) is None
    assert checkiner.match_button("不确定，像是 7", options) is None


def test_mooncake_extract_answer_rejects_prompt_or_button_contamination():
    checkiner = make_checkiner()

    assert checkiner.extract_answer("[ANSWER]验证码是 7，不是按钮 4[/ANSWER]") is None
    assert checkiner.extract_answer("[ANSWER]7[/ANSWER]") == "7"


def test_mooncake_prompt_tells_model_to_ignore_button_digits():
    checkiner = make_checkiner()
    prompt = checkiner.build_prompt(["3", "9", "5", "7", "2", "6", "8", "4", "1", "返回"])

    assert "忽略按钮" in prompt
    assert "最大" in prompt
    assert "单个阿拉伯数字" in prompt
