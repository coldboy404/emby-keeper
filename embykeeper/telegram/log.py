import asyncio
import io
import re

import httpx
from rich.text import Text
from loguru import logger

from embykeeper.schema import TelegramAccount
from embykeeper.utils import show_exception

from .link import Link
from .session import ClientsSession

logger = logger.bind(scheme="telenotifier", nonotify=True)


class TelegramStream(io.TextIOWrapper):
    """消息推送处理器类"""

    def _prettify_message(self, message: str) -> str:
        message = message.strip()

        replacements = [
            (r"^WARNING#每日签到 \((.*?)\): Auth Bot 不可用, 已跳过 CHECKINER 总认证并直接启动签到站点\.$", "⚠️ 每日签到：总认证不可用，已直接开始各站点签到。"),
            (r"^WARNING#每日签到 \((.*?)\): \((.*?)\) 接收到异常返回信息: (.*?), 正在尝试智能回答\.$", r"⚠️ \2：收到异常返回，正在尝试智能处理。\n└─ \3"),
            (r'^WARNING#每日签到 \((.*?)\): \((.*?)\) 初始化错误: "", 签到器将停止\.$', r"❌ \2：初始化失败，已跳过该站点。"),
            (r'^WARNING#每日签到 \((.*?)\): \((.*?)\) 初始化错误: "(.*?)", 签到器将停止\.$', r"❌ \2：初始化失败，已跳过该站点。\n└─ \3"),
            (r'^WARNING#每日签到 \((.*?)\): \((@?.*?)\) 初始化错误: "", 签到器将停止\.$', r"❌ \2：初始化失败，已跳过该站点。"),
            (r'^WARNING#每日签到 \((.*?)\): \((@?.*?)\) 初始化错误: "(.*?)", 签到器将停止\.$', r"❌ \2：初始化失败，已跳过该站点。\n└─ \3"),
            (r"^ERROR#每日签到 \((.*?)\): 签到失败 \((.*?)\): (.*?)$", r"❌ 每日签到失败\n• 统计：\2\n• 失败站点：\3"),
            (r"^ERROR#每日签到 \((.*?)\): 签到部分失败 \((.*?)\): (.*?)$", r"⚠️ 每日签到部分失败\n• 统计：\2\n• 失败站点：\3"),
            (r"^INFO#每日签到 \((.*?)\): 签到成功 \((.*?)\)\.$", r"✅ 每日签到完成\n• 统计：\2"),
        ]

        for pattern, replacement in replacements:
            new_message = re.sub(pattern, replacement, message)
            if new_message != message:
                return new_message

        message = re.sub(r"^(DEBUG|INFO|WARNING|ERROR)#", "", message)
        message = re.sub(r"^每日签到 \((.*?)\): ", "", message)
        return message.strip()

    def __init__(self, account: TelegramAccount = None, instant=False, bot_token: str = None, chat_id=None):
        super().__init__(io.BytesIO(), line_buffering=True)
        self.account = account
        self.instant = instant
        self.bot_token = bot_token
        self.chat_id = str(chat_id) if chat_id is not None else None

        self.queue = asyncio.Queue()
        self.watch = asyncio.create_task(self.watchdog())

    async def watchdog(self):
        while True:
            message = await self.queue.get()
            try:
                result = await asyncio.wait_for(self.send(message), 20)
            except asyncio.TimeoutError:
                logger.warning("推送消息到 Telegram 超时.")
            except Exception as e:
                logger.warning("推送消息到 Telegram 失败.")
                show_exception(e)
            else:
                if not result:
                    logger.warning(f"推送消息到 Telegram 失败.")
            finally:
                self.queue.task_done()

    async def send(self, message):
        if self.bot_token and self.chat_id:
            method = "sendMessage"
            url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": True,
            }
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(url, json=payload)
                if r.is_success:
                    data = r.json()
                    return bool(data.get("ok"))
                logger.warning(f"推送消息到 Telegram Bot API 失败: HTTP {r.status_code} {r.text[:300]}")
                return False

        async with ClientsSession([self.account]) as clients:
            async for _, tg in clients:
                if self.instant:
                    return await Link(tg).send_msg(message)
                else:
                    return await Link(tg).send_log(message)
            else:
                return False

    def write(self, message):
        message = Text.from_markup(message).plain
        if message.endswith("\n"):
            message = message[:-1]
        message = self._prettify_message(message)
        if message:
            self.queue.put_nowait(message)

    async def join(self):
        await self.queue.join()
        self.watch.cancel()
