from __future__ import annotations

import asyncio
import collections.abc
import contextlib
import dataclasses
import logging
import re
import typing as ty
from urllib.parse import urljoin

import bs4
from playwright.async_api import Browser, async_playwright

from .config import FilterConfig, SearchConfig
from .data_store import AdItem, DataStore
from .error import UnexpectedHTMLResponse

_logger = logging.getLogger(__name__.split(".", 1)[0])

T = ty.TypeVar("T")

# Default timeout for page navigation in milliseconds
PAGE_TIMEOUT_MS = 30_000

# Max concurrent page fetches to avoid overloading
MAX_CONCURRENT_PAGES = 4


async def achain(*iterables: ty.AsyncIterable[T]) -> ty.AsyncIterator[T]:
    """Chain async iterables"""
    for iterable in iterables:
        async for item in iterable:
            yield item


@contextlib.asynccontextmanager
async def create_browser() -> ty.AsyncIterator[Browser]:
    """Create a shared headless browser instance"""
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        try:
            yield browser
        finally:
            await browser.close()


@dataclasses.dataclass
class Result:
    """Result of a search for new ads"""

    search_config: SearchConfig
    num_already_in_datastore: int = 0
    num_excluded: int = 0
    ad_items: list[AdItem] = dataclasses.field(default_factory=list)

    def get_url(self) -> str:
        """Get the URL for notifications"""
        return self.search_config.url

    def get_title(self) -> str:
        """Get title for notifications"""
        return self.search_config.name

    def get_message(self) -> str:
        """Get the message to use in notifications"""
        plural = "" if len(self.ad_items) == 1 else "s"
        return f"🤖 Found {len(self.ad_items)} new ad{plural}"


async def get_soup(browser: Browser, url: str, semaphore: asyncio.Semaphore | None = None) -> bs4.BeautifulSoup:
    """Open a page in the headless browser and parse its markup using BeautifulSoup"""
    _logger.info("Getting soup for '%s'", url)

    async def _fetch() -> bs4.BeautifulSoup:
        page = await browser.new_page()
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
            if response is None:
                raise UnexpectedHTMLResponse("No response received")

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("text/html"):
                content = await page.content()
                raise UnexpectedHTMLResponse(content)

            content = await page.content()
            return bs4.BeautifulSoup(content, features="lxml")
        finally:
            await page.close()

    if semaphore is not None:
        async with semaphore:
            return await _fetch()
    return await _fetch()


def get_all_pagination_urls(soup: bs4.BeautifulSoup, url: str) -> list[str]:
    """Get the URL of all anchor elements with class pagination-page

    :param soup: BeautifulSoup object to get the pagination URLS from
    :type soup: bs4.BeautifulSoup
    :param url: URL of the `soup` object to build absolute URLs
    :type url: str
    :return: List of URLs
    :rtype: list[str]
    """
    anchors = soup.select("a.pagination-page")
    return [urljoin(url, href) for link_element in anchors if isinstance(href := link_element.get("href"), str)]


async def resolve_all_pages(
    browser: Browser,
    url: str,
    soup_map: collections.abc.MutableMapping[str, bs4.BeautifulSoup],
    semaphore: asyncio.Semaphore,
) -> None:
    """
    Resolve all pagination links of the search query and parse their HTML.

    First all pagination URLs are parsed from the initial page. Afterwards they all get resolved and parsed again.
    Any new links are then recursively passed to this function again.

    :param browser: Playwright Browser instance to use
    :param url: URL to use as the starting page
    :param soup_map: Map, mapping URLs to parsed HTML results. Used to store all already parsed pages.
    :param semaphore: Semaphore to limit concurrent page fetches
    """
    soup = soup_map[url]

    pagination_urls = get_all_pagination_urls(soup, url)

    if missing_pages := set(pagination_urls).difference(set(soup_map)):
        plural = "" if len(missing_pages) == 1 else "s"
        _logger.info("Found %d new page%s on '%s'", len(missing_pages), plural, url)

        async def add_to_soup_map(browser: Browser, url: str) -> None:
            soup_map[url] = await get_soup(browser, url, semaphore)

        await asyncio.gather(*[add_to_soup_map(browser, url_) for url_ in missing_pages])
        await resolve_all_pages(browser, pagination_urls[-1], soup_map, semaphore)


async def get_ad_items_from_soup(soup: bs4.BeautifulSoup, url: str) -> ty.AsyncGenerator[AdItem, None]:
    """Get all ad items in a list of BeautifulSoup objects"""
    _logger.debug("Find all ad items in '%s'", url)
    for bs_ad_item in soup.find_all("article", class_="aditem"):
        try:
            ad_item = AdItem(
                id=bs_ad_item.get("data-adid"),
                url=urljoin(url, bs_ad_item.get("data-href")),
                title=bs_ad_item.select(".text-module-begin>a")[0].text.strip(),
                description=bs_ad_item.select(".aditem-main--middle--description")[0].text.strip(),
                location=bs_ad_item.select('i[class*="icon-pin"]')[0].parent.text.strip(),
                price=bs_ad_item.select('p[class*="price"]')[0].text.strip(),
                image_url=bs_ad_item.select(".imagebox")[0].get("data-imgsrc"),
                is_top_ad=bool(bs_ad_item.select(".icon-feature-topad")),
                pruneable=False,
            )
        except (IndexError, AttributeError):
            ad_id = bs_ad_item.get("data-adid", "unknown")
            _logger.debug("Skipping ad '%s' due to unexpected HTML structure", ad_id)
            continue
        yield ad_item


async def get_all_ad_items(
    browser: Browser, url: str, recursive: bool, semaphore: asyncio.Semaphore
) -> collections.abc.AsyncGenerator[AdItem, None]:
    """Get all AdItems for a URL

    :param browser: Shared Playwright Browser instance
    :param url: URL of the initial search page
    :param recursive: Whether to search linked pagination pages as well
    :param semaphore: Semaphore to limit concurrent page fetches
    :yield: AdItems
    """
    soup_map = {url: (await get_soup(browser, url, semaphore))}
    if recursive:
        await resolve_all_pages(browser, url, soup_map, semaphore)

    async for ad_item in achain(*[get_ad_items_from_soup(soup, url) for url, soup in soup_map.items()]):
        yield ad_item


async def get_filtered_search_result(
    browser: Browser,
    search_config: SearchConfig,
    filter_config: FilterConfig,
    data_store: DataStore,
    semaphore: asyncio.Semaphore,
) -> Result:
    """
    Return a result for a search configuration

    The result will only contain all new AdItems which are not yet in the data store and not excluded by the filters

    :param browser: Shared Playwright Browser instance
    :param search_config: Search configuration to get the AdItems from
    :param filter_config: Filter configuration for the AdItems
    :param data_store: Data store object to check if ad_item is new
    :param semaphore: Semaphore to limit concurrent page fetches
    :return: Result for this search configuration
    """
    result = Result(search_config)
    async for ad_item in get_all_ad_items(browser, search_config.url, search_config.recursive, semaphore):
        # First: try to add the AdItem to the datastore, if it is already available continue
        if not data_store.add(ad_item):
            result.num_already_in_datastore += 1
            continue
        # Second: check if the AdItem should be excluded
        if ad_item_is_excluded(ad_item, filter_config):
            result.num_excluded += 1
            continue
        # AdItem is good, add to results
        result.ad_items.append(ad_item)

    return result


async def mark_ad_items_as_non_pruneable(
    browser: Browser, search_config: SearchConfig, data_store: DataStore, semaphore: asyncio.Semaphore
) -> None:
    """
    Mark all ads found by a search config as non-pruneable

    :param browser: Shared Playwright Browser instance
    :param search_config: Search configuration to get the AdItems from
    :param data_store: Data store object to check if ad_item is new
    :param semaphore: Semaphore to limit concurrent page fetches
    """
    async for ad_item in get_all_ad_items(browser, search_config.url, search_config.recursive, semaphore):
        data_store.mark_as_non_pruneable(ad_item)


def _text_matches(text: str, pattern: re.Pattern[str]) -> bool:
    """Check if text matches a pattern"""
    return bool(pattern.search(text))


def ad_item_is_excluded(ad_item: AdItem, filter_config: FilterConfig) -> bool:
    """Return whether an AdItem should be excluded from the results, based on the filter configuration

    :param ad_item: AdItem to check
    :param filter_config: Filter configuration
    :return: Whether to exclude this item
    """
    if filter_config.exclude_topads and ad_item.is_top_ad:
        return True

    searchable_text = f"{ad_item.title} {ad_item.description}"

    for pattern in filter_config.exclude_patterns:
        if _text_matches(searchable_text, pattern):
            _logger.info(
                "Ad '%s' '%s' matches exclude pattern '%s'",
                ad_item.id,
                ad_item.title,
                pattern.pattern,
            )
            return True

    for pattern in filter_config.require_all_patterns:
        if not _text_matches(searchable_text, pattern):
            _logger.info(
                "Ad '%s' '%s' does not match required pattern '%s'",
                ad_item.id,
                ad_item.title,
                pattern.pattern,
            )
            return True

    return False
