import asyncio
import io

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
        if message:
            self.queue.put_nowait(message)

    async def join(self):
        await self.queue.join()
        self.watch.cancel()
