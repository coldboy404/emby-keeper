import asyncio
import logging

from loguru import logger

from embykeeper.log import formatter
from embykeeper.config import config
from embykeeper.apprise import AppriseStream

debug_logger = logger.bind(scheme="debugtool")
logger = logger.bind(scheme="notifier", nonotify=True)

stream_log = None
stream_msg = None
handler_log_id = None
handler_msg_id = None
change_handle_telegram = None
change_handle_notifier = None


async def _stop_notifier():
    global stream_log, stream_msg, handler_log_id, handler_msg_id

    if handler_log_id is not None:
        logger.remove(handler_log_id)
        handler_log_id = None
    if handler_msg_id is not None:
        logger.remove(handler_msg_id)
        handler_msg_id = None

    if stream_log:
        stream_log.close()
        await stream_log.join()
        stream_log = None
    if stream_msg:
        stream_msg.close()
        await stream_msg.join()
        stream_msg = None


def _handle_config_change(*args):
    async def _async():
        global stream_log, stream_msg

        await _stop_notifier()
        if config.notifier and config.notifier.enabled:
            streams = await start_notifier()
            if streams:
                stream_log, stream_msg = streams

    logger.debug("正在刷新 Telegram 消息通知.")
    asyncio.create_task(_async())


async def start_notifier():
    """消息通知初始化函数."""
    global stream_log, stream_msg, handler_log_id, handler_msg_id, change_handle_telegram, change_handle_notifier

    def _filter_log(record):
        extra = record.get("extra", {})
        notify = extra.get("log", None)
        nonotify = extra.get("nonotify", None)
        scheme = extra.get("scheme", None)
        level_no = record["level"].no
        message = record.get("message", "")
        runtime_warning_schemes = {
            "telechecker",
            "embywatcher",
            "subsonic",
            "telemonitor",
            "telemessager",
            "teleregistrar",
            "telelink",
        }
        if nonotify:
            return False

        # 屏蔽单站点初始化失败的逐条通知，只保留最终汇总
        if (
            scheme == "telechecker"
            and level_no >= logging.WARNING
            and "初始化错误" in message
            and "签到器将停止" in message
        ):
            return False

        if notify or level_no >= logging.ERROR:
            return True
        if level_no >= logging.WARNING and scheme in runtime_warning_schemes:
            return True
        return False

    def _filter_msg(record):
        notify = record.get("extra", {}).get("msg", None)
        nonotify = record.get("extra", {}).get("nonotify", None)
        if (not nonotify) and notify:
            return True
        else:
            return False

    def _formatter(record):
        return "{level}#" + formatter(record)

    notifier = config.notifier
    if not notifier or not notifier.enabled:
        if not change_handle_notifier:
            change_handle_notifier = config.on_change("notifier", _handle_config_change)
        return None

    if notifier.method == "apprise":
        if not notifier.apprise_uri:
            logger.error("Apprise URI 未配置, 无法发送消息推送.")
            return None

        logger.info("关键消息将通过 Apprise 推送.")
        stream_log = AppriseStream(uri=notifier.apprise_uri)
        handler_log_id = logger.add(
            stream_log,
            format=_formatter,
            filter=_filter_log,
            enqueue=True,
        )
        stream_msg = AppriseStream(uri=notifier.apprise_uri)
        handler_msg_id = logger.add(
            stream_msg,
            format=_formatter,
            filter=_filter_msg,
            enqueue=True,
        )
        if not change_handle_notifier:
            change_handle_notifier = config.on_change("notifier", _handle_config_change)
        return stream_log, stream_msg

    if notifier.method == "telegram":
        if notifier.bot_token and notifier.chat_id:
            from .telegram.log import TelegramStream

            logger.info(f'计划任务的关键消息将通过自定义 Telegram Bot 发送至 chat_id="{notifier.chat_id}".')
            stream_log = TelegramStream(
                instant=config.notifier.immediately,
                bot_token=notifier.bot_token,
                chat_id=notifier.chat_id,
            )
            handler_log_id = logger.add(
                stream_log,
                format=_formatter,
                filter=_filter_log,
            )
            stream_msg = TelegramStream(
                instant=True,
                bot_token=notifier.bot_token,
                chat_id=notifier.chat_id,
            )
            handler_msg_id = logger.add(
                stream_msg,
                format=_formatter,
                filter=_filter_msg,
            )
            if not change_handle_notifier:
                change_handle_notifier = config.on_change("notifier", _handle_config_change)
            return stream_log, stream_msg

    logger.error("当前仅支持 Telegram Bot 或 Apprise 推送, 已移除 Telegram 账号转发模式。")
    if not change_handle_notifier:
        change_handle_notifier = config.on_change("notifier", _handle_config_change)
    return None


async def debug_notifier():
    streams = await start_notifier()
    if streams:
        logger.info("以下是发送的日志:")
        debug_logger.bind(msg=True).info("这是一条用于测试的即时消息, 使用 debug_notify 触发 😉.")
        debug_logger.bind(log=True).info("这是一条用于测试的日志消息, 使用 debug_notify 触发 😉.")
        if config.notifier.method == "apprise":
            logger.info("已尝试发送, 请至 Apprise 配置的接收端查看.")
        elif config.notifier.method == "telegram":
            if config.notifier.bot_token and config.notifier.chat_id:
                logger.info(f'已尝试发送, 请至自定义 Telegram 机器人 chat_id="{config.notifier.chat_id}" 查看.')
            else:
                logger.info("Telegram 账号转发模式已移除, 请配置 bot_token 和 chat_id。")
        await asyncio.gather(*[stream.join() for stream in streams if stream])
    else:
        logger.error("您当前没有配置有效的日志通知 (未启用日志通知或未配置账号), 请检查配置文件.")
