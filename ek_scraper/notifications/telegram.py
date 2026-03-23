from __future__ import annotations

import asyncio
import collections.abc
import logging
import typing as ty

import aiohttp

from ek_scraper.config import TelegramConfig

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper.scraper import Result

BASE_URL = "https://api.telegram.org"

_logger = logging.getLogger(__name__)


async def send_notification(session: aiohttp.ClientSession, config: TelegramConfig, result: Result) -> None:
    """Send a single notification via Telegram Bot API

    :param session: ClientSession to send requests through
    :param config: Configuration for Telegram
    :param result: Result of the scraper
    """
    text = f"<b>{result.get_title()}</b>\n{result.get_message()}\n<a href=\"{result.get_url()}\">Zur Suche</a>"

    params = {
        "chat_id": config.chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": not config.link_preview,
    }

    _logger.info("Send Telegram notification for '%s'", result.get_title())
    resp = await session.post(f"/bot{config.bot_token}/sendMessage", json=params)
    try:
        resp.raise_for_status()
    except Exception as exc:
        raise NotificationError(f"Received error response: {exc}") from exc


async def send_notifications(results: ty.Sequence[Result], config: TelegramConfig) -> None:
    """Send notifications for all results from the scraper

    :param results: Results from the scraper
    :param config: Configuration for Telegram notifications
    """
    async with aiohttp.ClientSession(BASE_URL) as session:
        tasks: list[collections.abc.Awaitable[ty.Any]] = list()
        for result in results:
            if not result.ad_items:
                continue
            tasks.append(send_notification(session, config=config, result=result))

        await asyncio.gather(*tasks)
