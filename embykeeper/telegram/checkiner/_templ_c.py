from datetime import datetime, timedelta
import asyncio
import random
import string
from typing import List, Optional, Union

from loguru import logger
from pydantic import BaseModel, ValidationError

from embykeeper.runinfo import RunStatus
from embykeeper.utils import to_iterable

from ..monitor import UniqueUsername
from ..embyboss import EmbybossRegister
from . import BotCheckin


__ignore__ = True


class TemplateCCheckinConfig(BaseModel):
    """自定义群组签到 / 发言模板配置."""

    name: Optional[str] = None
    mode: Optional[str] = None
    chat_id: Optional[Union[int, str]] = None
    chat_name: Optional[Union[int, str]] = None
    bot_checkin_cmd: Union[str, List[str], None] = None
    bot_send_interval: int = 3
    bot_use_captcha: bool = False
    bot_success_keywords: Union[str, List[str]] = []
    bot_checked_keywords: Union[str, List[str]] = []
    bot_fail_keywords: Union[str, List[str]] = []
    bot_account_fail_keywords: Union[str, List[str]] = []
    bot_text_ignore: Union[str, List[str]] = []
    bot_success_pat: str = r"(\d+)[^\d]*(\d+)"
    wait_response: bool = False


class TemplateCCheckin(BotCheckin):
    """模板 C.

    默认保持旧行为: 定时开注测试器.
    当配置了 bot_checkin_cmd / chat_id / chat_name, 或 mode = "chat" / "group" 时,
    切换为自定义群组签到 / 群组发言模板.
    """

    bot_use_captcha = False
    unique_cache = UniqueUsername()

    def get_unique_name(self):
        unique_name = self.config.get("unique_name", None)
        if unique_name:
            return unique_name
        else:
            return self.__class__.unique_cache[self.client.me]

    def is_group_checkin_mode(self):
        return bool(
            self.config.get("bot_checkin_cmd")
            or self.config.get("chat_id")
            or self.config.get("chat_name")
            or self.config.get("mode") in {"chat", "group", "message", "speak", "checkin"}
        )

    @staticmethod
    def normalize_chat(chat):
        """Normalize chat identifiers from config/template syntax.

        Telegram private supergroup links often expose `tg://openmessage?chat_id=3849837200`,
        while Pyrogram expects `-1003849837200`.  A bare 10+ digit positive integer/string is
        treated as that tg:// chat_id form.  Existing negative ids and usernames are preserved.
        """
        if isinstance(chat, int):
            if chat > 0 and len(str(chat)) >= 10:
                return int(f"-100{chat}")
            return chat
        if isinstance(chat, str):
            value = chat.strip()
            if value.startswith("-100") and value[4:].isdigit():
                return int(value)
            if value.isdigit() and len(value) >= 10:
                return int(f"-100{value}")
            return value.lstrip("@")
        return chat

    async def init_group_checkin(self):
        try:
            self.t_config = TemplateCCheckinConfig.model_validate(self.config)
        except ValidationError as e:
            self.log.warning(f"初始化失败: 签到自定义模板 C 的配置错误:\n{e}")
            return False

        self.name = self.t_config.name or self.name or "自定义群组签到"
        self.chat_name = self.normalize_chat(self.t_config.chat_id or self.t_config.chat_name or self.bot_username)
        self.bot_username = None
        self.bot_checkin_cmd = self.t_config.bot_checkin_cmd or "签到"
        self.bot_send_interval = self.t_config.bot_send_interval
        self.bot_use_captcha = self.t_config.bot_use_captcha
        self.bot_success_keywords = self.t_config.bot_success_keywords
        self.bot_checked_keywords = self.t_config.bot_checked_keywords
        self.bot_fail_keywords = self.t_config.bot_fail_keywords
        self.bot_account_fail_keywords = self.t_config.bot_account_fail_keywords
        self.bot_text_ignore = self.t_config.bot_text_ignore
        self.bot_success_pat = self.t_config.bot_success_pat
        self.log = logger.bind(scheme="telechecker", name=self.name, username=self.client.me.full_name)
        return True

    async def start(self):
        if self.is_group_checkin_mode():
            if not await self.init_group_checkin():
                return self.ctx.finish(RunStatus.FAIL, "初始化错误")
            return await super().start()

        random_code = "".join(random.choices(string.ascii_letters + string.digits, k=4))
        if await EmbybossRegister(self.client, self.log, self.get_unique_name(), random_code).run(
            self.bot_username
        ):
            self.log.bind(log=True).info(f"定时开注测试器成功注册机器人 {self.bot_username}.")
            return self.ctx.finish(RunStatus.SUCCESS, "机器人注册成功")
        else:
            interval = self.config.get("interval", 7200)
            self.ctx.next_time = datetime.now() + timedelta(seconds=interval)
            return self.ctx.finish(RunStatus.RESCHEDULE, "机器人未开注")

    async def send_checkin(self, retry=False):
        cmds = to_iterable(self.bot_checkin_cmd)
        for i, cmd in enumerate(cmds):
            if retry and not i:
                await asyncio.sleep(2)
            if i:
                await asyncio.sleep(self.bot_send_interval)
            await self.send(cmd)
        if not self.t_config.wait_response:
            await self.finish(message="群组签到命令已发送")


def use(**kw):
    return type("TemplatedClass", (TemplateCCheckin,), kw)
