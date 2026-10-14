from __future__ import annotations

import asyncio
import collections.abc
import html
import logging
import typing as ty

import aiohttp

from ek_scraper.config import TelegramConfig

from . import NotificationError

if ty.TYPE_CHECKING:
    from ek_scraper.data_store import AdItem
    from ek_scraper.scraper import Result

BASE_URL = "https://api.telegram.org"

# Maximum length of a Telegram message text
MAX_MESSAGE_LENGTH = 4096

_logger = logging.getLogger(__name__)


def _ad_line(ad: AdItem, max_length: int) -> str:
    """Format a single ad as a line, the title is shortened if the line would exceed max_length"""
    url = html.escape(ad.url)
    price = html.escape(ad.price)
    title = ad.title
    while True:
        line = f'• <a href="{url}">{html.escape(title)}</a> - {price}'
        if len(line) <= max_length or len(title) <= 1:
            return line
        title = title[: max(1, len(title) - (len(line) - max_length) - 1)].rstrip() + "…"


def build_messages(result: Result, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Build the messages for a result, split between whole ad lines if the text is too long

    :param result: Result of the scraper
    :param max_length: Maximum length of a single message
    :return: List of message texts
    """
    title = f"<b>{html.escape(result.get_title())}</b>"
    message = html.escape(result.get_message())
    footer = f'<a href="{html.escape(result.get_url())}">Zur Suche</a>'
    part_label_length = len(" (Teil 99/99)")
    # Space left for the ad lines in each message: title, label, message, footer and separators
    available = max_length - len(title) - part_label_length - len(message) - len(footer) - 3 * len("\n\n")

    chunks: list[list[str]] = [[]]
    chunk_length = 0
    for ad in result.ad_items:
        line = _ad_line(ad, available)
        added_length = len(line) + (1 if chunks[-1] else 0)
        if chunks[-1] and chunk_length + added_length > available:
            chunks.append([])
            chunk_length = 0
            added_length = len(line)
        chunks[-1].append(line)
        chunk_length += added_length

    messages: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        label = f" (Teil {index}/{len(chunks)})" if len(chunks) > 1 else ""
        parts = [title + label, message]
        if chunk:
            parts.append("\n".join(chunk))
        parts.append(footer)
        messages.append("\n\n".join(parts))
    return messages


async def send_notification(session: aiohttp.ClientSession, config: TelegramConfig, result: Result) -> None:
    """Send the notification for a result via Telegram Bot API, split into several messages if necessary

    :param session: ClientSession to send requests through
    :param config: Configuration for Telegram
    :param result: Result of the scraper
    """
    messages = build_messages(result)
    for index, text in enumerate(messages, start=1):
        params = {
            "chat_id": config.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": not config.link_preview,
        }

        _logger.info("Send Telegram notification %d/%d for '%s'", index, len(messages), result.get_title())
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
