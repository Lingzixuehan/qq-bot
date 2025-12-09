"""
Steam商店和价格API模块
支持ITAD (IsThereAnyDeal) API和Steam Store API集成
"""
import asyncio
import httpx
import re
from html import unescape
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
from nonebot.log import logger


def _parse_low_timestamp(timestamp: Any) -> Optional[str]:
    """将史低时间戳或日期字符串解析为 YYYY-MM-DD"""

    if not timestamp:
        return None

    try:
        parsed_ts: Optional[int] = None

        if isinstance(timestamp, (int, float)):
            parsed_ts = int(timestamp)
        elif isinstance(timestamp, str):
            cleaned = timestamp.strip()
            if cleaned.isdigit():
                parsed_ts = int(cleaned)
            else:
                try:
                    parsed_dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
                    return parsed_dt.strftime("%Y-%m-%d")
                except Exception:
                    date_match = re.search(r"\d{4}-\d{2}-\d{2}", cleaned)
                    if date_match:
                        return date_match.group(0)

        if parsed_ts is not None:
            # ITAD 返回的时间戳可能是毫秒，需要兼容处理
            if parsed_ts > 10 ** 11:
                parsed_ts = parsed_ts / 1000
            return datetime.fromtimestamp(parsed_ts).strftime("%Y-%m-%d")
    except Exception:
        logger.debug("解析史低时间戳失败", exc_info=True)

    return None


class SteamStoreAPI:
    """Steam商店和价格查询API"""

    def __init__(self, itad_api_key: Optional[str] = None):
        """
        初始化Steam商店API

        Args:
            itad_api_key: IsThereAnyDeal API密钥（可选）
        """
        self.itad_api_key = itad_api_key
        self.itad_base_url = "https://api.isthereanydeal.com"
        self.steam_store_url = "https://store.steampowered.com/api"
        self.cache_dir = Path(__file__).parent / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 缓存配置
        self.cache_duration = timedelta(hours=1)  # 缓存1小时

    async def _translate_to_english(self, text: str) -> Optional[str]:
        """简单的中文->英文翻译兜底，提升外文原名搜索命中率"""
        if not text:
            return None

        if not re.search(r"[\u4e00-\u9fff]", text):
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://fanyi.youdao.com/translate",
                    params={"doctype": "json", "type": "AUTO", "i": text},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                # 解析有道翻译结果
                translate_result = data.get("translateResult")
                if translate_result and isinstance(translate_result, list):
                    first_line = translate_result[0]
                    if first_line and isinstance(first_line, list) and first_line[0].get("tgt"):
                        return first_line[0]["tgt"].strip()
        except Exception:
            logger.debug("翻译失败，跳过", exc_info=True)

        return None

    async def search_games_on_sale(
        self,
        limit: int = 20,
        min_discount: int = 50,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        搜索当前打折游戏

        Args:
            limit: 返回数量限制
            min_discount: 最小折扣百分比
            tags: 游戏标签过滤（如 "Metroidvania", "RPG" 等）

        Returns:
            打折游戏列表
        """
        try:
            # 直接抓取Steam搜索页HTML，解析折扣信息
            params = {
                "specials": "1",
                "cc": "cn",
                "l": "schinese",
                "start": 0,
                "count": max(limit * 2, 50),
            }
            if tags:
                # 将“类型/标签”作为搜索关键词处理
                params["term"] = " ".join(tags)

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SteamBot/1.0"
            }

            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                url = "https://store.steampowered.com/search/"
                logger.debug(f"抓取Steam搜索页: url={url}, params={params}")
                response = await client.get(url, params=params, headers=headers)

                if response.status_code != 200:
                    logger.error(f"Steam搜索页请求失败: {response.status_code}, 响应: {response.text[:200]}")
                    return []

                html = response.text

            pattern = re.compile(
                r'<a[^>]*class="search_result_row[^"]*"[^>]*>(?P<body>.*?)</a>',
                re.S
            )
            filtered_items: List[Dict] = []
            seen_appids = set()

            for match in pattern.finditer(html):
                block = match.group("body")
                appid_match = re.search(r'data-ds-appid="([^"]+)"', match.group(0))
                if not appid_match:
                    continue
                appid_raw = appid_match.group(1)
                appid = appid_raw.split(",")[0].strip()
                if not appid.isdigit() or appid in seen_appids:
                    continue

                discount_match = re.search(r'data-discount="(\d+)"', match.group(0))
                discount = int(discount_match.group(1)) if discount_match else 0
                if discount < min_discount:
                    continue

                price_match = re.search(r'data-price-final="(\d+)"', match.group(0))
                final_price = int(price_match.group(1)) / 100 if price_match else None

                title_match = re.search(r'<span class="title">(.*?)</span>', block, re.S)
                title = unescape(title_match.group(1)).strip() if title_match else "未知游戏"

                seen_appids.add(appid)
                filtered_items.append({
                    "id": int(appid),
                    "name": title,
                    "discount_percent": discount,
                    "final_price": final_price,
                })

                if len(filtered_items) >= limit * 2:
                    break

            logger.info(f"Steam搜索解析到 {len(filtered_items)} 个折扣游戏")
            return filtered_items[:limit]

        except Exception as e:
            logger.error(f"搜索打折游戏失败: {e}", exc_info=True)
            return []

    async def get_game_details(
        self,
        appid: int,
        country: str = "cn",
        client: Optional[httpx.AsyncClient] = None,
        language: str = "schinese",
    ) -> Optional[Dict]:
        """
        获取游戏详细信息

        Args:
            appid: Steam游戏ID
            country: 国家代码

        Returns:
            游戏详情字典
        """
        session = client or httpx.AsyncClient(timeout=30, follow_redirects=True)
        try:
            url = f"{self.steam_store_url}/appdetails"
            params = {
                "appids": appid,
                "cc": (country or "cn").lower(),
                "l": language,
            }

            response = await session.get(url, params=params)
            if response.status_code != 200:
                return None

            data = response.json()
            if str(appid) in data and data[str(appid)]["success"]:
                return data[str(appid)]["data"]

            return None
        except Exception as e:
            logger.warning(f"获取游戏详情失败 (appid={appid}, cc={country}, lang={language}): {e}")
            return None
        finally:
            if client is None:
                await session.aclose()

    async def _store_search(self, term: str, country: str, language: str) -> List[Dict]:
        """调用 Steam storesearch API 并处理异常（带重试）"""
        last_error = ""
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    resp = await client.get(
                        "https://store.steampowered.com/api/storesearch/",
                        params={"term": term, "cc": country, "l": language},
                    )
                if resp.status_code != 200:
                    last_error = f"status={resp.status_code}"
                    continue
                return resp.json().get("items", [])
            except Exception as err:
                last_error = str(err) or repr(err)
        logger.warning(f"storesearch 请求失败: country={country}, err={last_error}")
        return []

    async def _search_apps(self, term: str) -> Optional[Dict]:
        """使用社区 SearchApps 接口兜底"""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(f"https://steamcommunity.com/actions/SearchApps/{term}")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and data:
                    return data[0]
        except Exception:
            logger.debug("SearchApps 兜底搜索失败", exc_info=True)
        return None

    async def _get_region_details(
        self,
        client: httpx.AsyncClient,
        appid: int,
        region: str,
    ) -> Optional[Dict]:
        """按区域获取详情，自动尝试多种语言"""
        region = (region or "cn").lower()
        language_order = ["schinese", "english"] if region == "cn" else ["english", "schinese"]
        tried = set()
        for lang in language_order:
            if lang in tried:
                continue
            tried.add(lang)
            details = await self.get_game_details(appid, country=region, client=client, language=lang)
            if details:
                return details
        return None

    async def get_historical_low(
        self,
        appid: int,
        country: str = "CN",
        client: Optional[httpx.AsyncClient] = None
    ) -> Optional[Dict]:
        """
        获取游戏史低价格（使用ITAD API v3）

        Args:
            appid: Steam游戏ID
            country: 国家代码，默认CN

        Returns:
            史低价格信息，包含price, currency, timestamp等字段
        """
        if not self.itad_api_key:
            logger.debug("ITAD API密钥未配置，无法获取史低价格")
            return None

        session = client or httpx.AsyncClient(timeout=30)
        try:
            lookup_url = f"{self.itad_base_url}/games/lookup/v1"
            lookup_params = {
                "appid": appid,
                "key": self.itad_api_key
            }

            response = await session.get(lookup_url, params=lookup_params)
            if response.status_code != 200:
                logger.debug(f"ITAD lookup失败: {response.status_code}, 响应: {response.text}")
                return None

            lookup_data = response.json()
            if not lookup_data or "game" not in lookup_data:
                logger.debug(f"ITAD lookup未返回游戏信息: appid={appid}")
                return None

            gid = lookup_data["game"].get("id")
            if not gid:
                logger.debug(f"ITAD lookup缺少游戏ID: appid={appid}")
                return None

            logger.debug(f"ITAD game ID: {gid}")

            # 先尝试 v3 接口获取更精确的史低数据
            low_info = await self._get_historical_low_v3(session, gid, country)

            # v3 可能因为区域或权限问题失败，尝试 v1 概览接口兜底
            if not low_info:
                low_info = await self._get_historical_low_v1(session, gid, country)
            elif not low_info.get("timestamp"):
                # v3 成功但没有时间戳，尝试从 v1 补充时间戳
                logger.debug("v3 返回的史低数据缺少时间戳，尝试从 v1 补充")
                v1_info = await self._get_historical_low_v1(session, gid, country)
                if v1_info and v1_info.get("timestamp"):
                    low_info["timestamp"] = v1_info["timestamp"]
                    logger.debug(f"成功从 v1 补充时间戳: {v1_info['timestamp']}")

            return low_info

        except Exception as e:
            logger.error(f"获取史低价格失败 (appid={appid}): {e}", exc_info=True)
            return None
        finally:
            if client is None:
                await session.aclose()

    async def _get_historical_low_v3(self, session: httpx.AsyncClient, gid: str, country: str) -> Optional[Dict]:
        prices_url = f"{self.itad_base_url}/games/prices/v3"
        prices_params = {
            "key": self.itad_api_key,
            "country": country,
            "shops": 61  # Steam
        }

        response = await session.post(prices_url, params=prices_params, json=[gid])
        if response.status_code != 200:
            logger.debug(f"ITAD prices API失败: {response.status_code}")
            return None

        prices_data = response.json()
        if not prices_data:
            logger.debug(f"ITAD prices API未返回数据: gid={gid}")
            return None

        game_data = prices_data[0]
        history_low = game_data.get("historyLow", {})
        logger.debug(f"ITAD v3 historyLow 原始数据: {history_low}")

        lowest_price = None
        lowest_currency = "CNY"
        lowest_timestamp = None

        for period in ["m3", "y1", "all"]:
            if period in history_low and history_low[period]:
                low_data = history_low[period]
                logger.debug(f"ITAD v3 使用 {period} 周期数据: {low_data}")
                if "amount" in low_data:
                    lowest_price = low_data.get("amount")
                    lowest_currency = low_data.get("currency", "CNY").upper()
                    # 尝试多种可能的时间戳字段名
                    lowest_timestamp = (
                        low_data.get("timestamp")
                        or low_data.get("recorded")
                        or low_data.get("date")
                    )
                    break

        if lowest_price is None:
            return None

        current_price = None
        current_currency = lowest_currency
        deals = game_data.get("deals", [])
        for deal in deals:
            shop = deal.get("shop", {})
            if shop.get("id") == 61:
                price_data = deal.get("price", {})
                current_price = price_data.get("amount")
                current_currency = price_data.get("currency", current_currency).upper()
                break

        return {
            "price": lowest_price,
            "currency": lowest_currency,
            "timestamp": lowest_timestamp,
            "current_price": current_price,
            "current_currency": current_currency,
        }

    async def _get_historical_low_v1(self, session: httpx.AsyncClient, gid: str, country: str) -> Optional[Dict]:
        """使用 ITAD /games/historylow/v1 接口兜底史低价格及时间"""
        history_url = f"{self.itad_base_url}/games/historylow/v1"
        params = {
            "key": self.itad_api_key,
            "country": country.upper(),
        }

        response = await session.post(history_url, params=params, json=[gid])
        if response.status_code != 200:
            logger.debug(f"ITAD historylow 接口失败: {response.status_code}")
            return None

        records = response.json()
        if not records or not isinstance(records, list):
            return None

        record = next((item for item in records if item.get("id") == gid), records[0])
        low = (record or {}).get("low") if record else None
        if not low:
            return None

        price_info = low.get("price") or {}
        currency = (price_info.get("currency") or "CNY").upper()
        return {
            "price": price_info.get("amount"),
            "currency": currency,
            "timestamp": low.get("timestamp"),
            "current_price": None,
            "current_currency": currency,
        }

    async def search_game(self, keyword: str) -> Optional[Dict]:
        """
        搜索游戏并返回官方英文名（支持中文输入自动翻译）

        Args:
            keyword: 游戏关键字（支持中文/英文）

        Returns:
            包含 appid、name(中文名)、english_name(官方英文名)、image 的字典
        """
        if not keyword:
            return None

        try:
            search_terms = [keyword]
            translated = await self._translate_to_english(keyword)
            if translated and translated.lower() != keyword.lower():
                search_terms.append(translated)

            cn_items: List[Dict] = []
            en_items: List[Dict] = []
            fallback_item: Optional[Dict] = None

            for term in search_terms:
                cn_items = await self._store_search(term, "cn", "schinese")
                en_items = await self._store_search(term, "us", "english")
                if cn_items or en_items:
                    break
                if not fallback_item:
                    fallback_item = await self._search_apps(term)

            if not (cn_items or en_items) and not fallback_item:
                fallback_item = await self._search_apps(keyword)

            # 优先中文结果，其次英文结果，最后兜底
            item = cn_items[0] if cn_items else en_items[0] if en_items else None
            if not item and fallback_item:
                item = {
                    "id": fallback_item.get("appid"),
                    "name": fallback_item.get("name"),
                    "tiny_image": fallback_item.get("icon"),
                }

            if not item:
                return None

            appid = item.get("id")
            localized_name = item.get("name")
            image = item.get("tiny_image")

            english_name = localized_name
            # 再获取官方英文名，兼容中文输入
            try:
                if en_items:
                    english_name = en_items[0].get("name", english_name)
            except Exception:
                pass

            # 如果有appid，优先用app详情获取官方英文名和本地化名称，确保准确
            if appid:
                try:
                    en_details = await self.get_game_details(
                        appid, country="us", language="english"
                    )
                    if en_details:
                        english_name = en_details.get("name", english_name)
                    cn_details = await self.get_game_details(
                        appid, country="cn", language="schinese"
                    )
                    if cn_details:
                        localized_name = cn_details.get("name", localized_name)
                        image = cn_details.get("header_image", image)
                except Exception:
                    logger.debug("获取游戏详情失败，使用搜索结果", exc_info=True)

            return {
                "appid": appid,
                "name": localized_name,
                "english_name": english_name,
                "image": image,
            }
        except Exception as e:
            logger.error(f"搜索Steam游戏失败: {e}", exc_info=True)
            return None

    async def get_game_price_info(
        self,
        appid: int,
        regions: List[str],
        exchange_rates: Dict[str, float],
        english_name: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        获取游戏价格、折扣、史低信息

        Args:
            appid: Steam 游戏ID
            regions: 需要查询的国家/地区代码列表
            exchange_rates: 货币到人民币的汇率字典
            english_name: 官方英文名（可选）

        Returns:
            包含价格信息的字典
        """
        if not appid:
            return None

        unique_regions = []
        for region in regions or ["cn"]:
            region = region.lower()
            if region and region not in unique_regions:
                unique_regions.append(region)
        if not unique_regions:
            unique_regions = ["cn"]

        prices: List[Dict] = []
        image = ""
        localized_name: Optional[str] = None

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for region in unique_regions:
                details = await self._get_region_details(client, appid, region)
                if not details:
                    logger.debug(f"无法获取 {appid} 的 {region} 区信息")
                    continue

                if not localized_name:
                    localized_name = details.get("name")
                if not image:
                    image = details.get("header_image", "")

                price_overview = details.get("price_overview")
                if not price_overview:
                    logger.debug(f"{appid} 在 {region} 区无价格信息")
                    continue

                currency = price_overview.get("currency", "CNY").upper()
                price = price_overview.get("final", 0) / 100
                original_price = price_overview.get("initial", 0) / 100
                discount = price_overview.get("discount_percent", 0)

                converted_price = None
                if currency in exchange_rates:
                    converted_price = price * float(exchange_rates[currency])

                prices.append(
                    {
                        "region": region,
                        "currency": currency,
                        "price": price,
                        "original_price": original_price,
                        "discount": discount,
                        "converted_price": converted_price,
                    }
                )

            if not prices:
                fallback_region = "cn" if "cn" not in unique_regions else unique_regions[0]
                details = await self._get_region_details(client, appid, fallback_region)
                if details:
                    price_overview = details.get("price_overview")
                    if price_overview:
                        if not localized_name:
                            localized_name = details.get("name")
                        if not image:
                            image = details.get("header_image", "")

                        currency = price_overview.get("currency", "CNY").upper()
                        price = price_overview.get("final", 0) / 100
                        original_price = price_overview.get("initial", 0) / 100
                        discount = price_overview.get("discount_percent", 0)
                        converted_price = None
                        if currency in exchange_rates:
                            converted_price = price * float(exchange_rates[currency])
                        prices.append(
                            {
                                "region": fallback_region,
                                "currency": currency,
                                "price": price,
                                "original_price": original_price,
                                "discount": discount,
                                "converted_price": converted_price,
                            }
                        )
                        if fallback_region not in unique_regions:
                            unique_regions.insert(0, fallback_region)

        # 获取英文名
        if not english_name:
            try:
                region_for_english = unique_regions[0] if unique_regions else "us"
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    en_details = await self.get_game_details(
                        appid, country=region_for_english, client=client, language="english"
                    )
                    if not en_details and region_for_english != "us":
                        en_details = await self.get_game_details(
                            appid, country="us", client=client, language="english"
                        )
                    if en_details:
                        english_name = en_details.get("name", english_name)
            except Exception:
                pass

        historical_low_price = None
        historical_low_currency = "CNY"
        historical_low_date = None

        if self.itad_api_key:
            async with httpx.AsyncClient(timeout=30) as itad_client:
                low_country = (unique_regions[0] if unique_regions else "cn").upper()
                low_info = await self.get_historical_low(appid, country=low_country, client=itad_client)
                if low_info:
                    historical_low_price = low_info.get("price")
                    historical_low_currency = low_info.get("currency", "CNY").upper()
                    timestamp = (
                        low_info.get("timestamp")
                        or low_info.get("recorded")
                        or low_info.get("date")
                    )

                    parsed_date = _parse_low_timestamp(timestamp)
                    if parsed_date:
                        historical_low_date = parsed_date

        if not prices:
            return None

        return {
            "appid": appid,
            "name": localized_name or english_name,
            "english_name": english_name,
            "prices": prices,
            "image": image,
            "historical_low": historical_low_price,
            "historical_low_currency": historical_low_currency,
            "historical_low_date": historical_low_date,
        }

    async def get_free_games(self, limit: int = 8) -> List[Dict]:
        """获取当前限时免费的Steam游戏"""
        try:
            params = {
                "specials": "1",
                "maxprice": "free",
                "cc": "cn",
                "l": "schinese",
                "start": 0,
                "count": max(limit * 2, 30),
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SteamBot/1.0",
            }
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get("https://store.steampowered.com/search/", params=params, headers=headers)
                if response.status_code != 200:
                    logger.error(f"获取喜加一列表失败: {response.status_code}")
                    return []

                html = response.text

            pattern = re.compile(
                r'<a[^>]*class="search_result_row[^"]*"[^>]*>(?P<body>.*?)</a>',
                re.S
            )
            free_games: List[Dict] = []
            seen_ids = set()

            for match in pattern.finditer(html):
                block = match.group("body")
                appid_match = re.search(r'data-ds-appid="([^"]+)"', match.group(0))
                if not appid_match:
                    continue
                appid_raw = appid_match.group(1)
                appid = appid_raw.split(",")[0].strip()
                if not appid.isdigit() or appid in seen_ids:
                    continue

                discount_match = re.search(r'data-discount="(\d+)"', match.group(0))
                discount = int(discount_match.group(1)) if discount_match else 0

                price_match = re.search(r'data-price-final="(\d+)"', match.group(0))
                final_price = int(price_match.group(1)) / 100 if price_match else None

                if final_price not in (0, 0.0) and discount <= 0:
                    continue

                title_match = re.search(r'<span class="title">(.*?)</span>', block, re.S)
                title = unescape(title_match.group(1)).strip() if title_match else "未知游戏"

                image_match = re.search(r'data-ds-background-image="([^"]+)"', match.group(0))
                image = image_match.group(1) if image_match else ""

                seen_ids.add(appid)
                free_games.append({
                    "id": int(appid),
                    "name": title,
                    "discount_percent": discount,
                    "final_price": final_price or 0,
                    "image": image,
                })

                if len(free_games) >= limit:
                    break

            return free_games
        except Exception as e:
            logger.error(f"获取喜加一列表失败: {e}", exc_info=True)
            return []

    async def get_discount_recommendations(self, limit: int = 8, min_discount: int = 60) -> List[Dict]:
        """获取高折扣游戏推荐"""
        try:
            raw_items = await self.search_games_on_sale(limit=limit * 2, min_discount=min_discount)
            if not raw_items:
                return []

            results: List[Dict] = []
            async with httpx.AsyncClient(timeout=30) as client:
                for item in raw_items:
                    appid = item.get("id")
                    if not appid:
                        continue
                    try:
                        details = await self.get_game_details(appid, client=client)
                    except Exception:
                        logger.debug("获取折扣游戏详情失败", exc_info=True)
                        details = None

                    price_overview = details.get("price_overview") if details else None
                    final_price = price_overview.get("final", 0) / 100 if price_overview else item.get("final_price", 0)
                    discount_percent = price_overview.get("discount_percent", item.get("discount_percent", 0)) if price_overview else item.get("discount_percent", 0)
                    original_price = price_overview.get("initial", 0) / 100 if price_overview else None

                    tags = []
                    header_image = item.get("image", "")
                    if details:
                        tags = [genre.get("description", "") for genre in details.get("genres", []) if genre.get("description")]
                        header_image = details.get("header_image", header_image)

                    results.append({
                        "appid": appid,
                        "name": item.get("name"),
                        "price": final_price,
                        "discount": discount_percent,
                        "original_price": original_price,
                        "image": header_image,
                        "tags": tags,
                    })

                    if len(results) >= limit:
                        break

            return results
        except Exception as e:
            logger.error(f"获取折扣推荐失败: {e}", exc_info=True)
            return []

    async def find_historical_low_deals(
        self,
        limit: int = 10,
        tags: Optional[str] = None
    ) -> List[Dict]:
        """
        查找当前打到史低价的游戏

        Args:
            limit: 返回数量
            tags: 游戏标签（如"Metroidvania"）

        Returns:
            史低游戏列表，每个包含 {appid, name, current_price, historical_low, discount, image}
        """
        logger.info(f"开始查找史低游戏，limit={limit}, tags={tags}")

        # 搜索当前打折的游戏（降低最小折扣要求到10%）
        tag_list = [tags] if tags else None
        games_on_sale = await self.search_games_on_sale(
            limit=max(limit * 2, limit),  # 获取更多，因为要筛选
            min_discount=10,  # 降低到10%，获取所有有折扣的游戏
            tags=tag_list
        )

        logger.info(f"搜索到 {len(games_on_sale)} 个打折游戏")

        if not games_on_sale:
            logger.warning("未找到打折游戏")
            return []

        # 并发处理游戏信息以提升速度，限制并发数量避免触发平台风控
        semaphore = asyncio.Semaphore(8)

        async def process_game(
            game: Dict,
            steam_client: httpx.AsyncClient,
            itad_client: Optional[httpx.AsyncClient]
        ) -> Optional[Dict]:
            appid = game.get("id")
            if not appid:
                logger.debug(f"游戏缺少ID，跳过: {game}")
                return None

            async with semaphore:
                details = await self.get_game_details(appid, client=steam_client)

            if not details:
                logger.debug(f"无法获取游戏详情: appid={appid}")
                return None

            if details.get("is_free", False):
                logger.debug(f"跳过免费游戏: {details.get('name')}")
                return None

            price_overview = details.get("price_overview")
            if not price_overview:
                logger.debug(f"游戏无价格信息: {details.get('name')}")
                return None

            current_price = price_overview.get("final", 0) / 100
            discount_percent = price_overview.get("discount_percent", 0)

            historical_low = None
            is_historical_low = False

            if self.itad_api_key and itad_client:
                async with semaphore:
                    historical_low = await self.get_historical_low(appid, country="CN", client=itad_client)
                if historical_low:
                    low_price = historical_low.get("price", 0)
                    if current_price > 0 and low_price > 0:
                        diff_percent = abs(current_price - low_price) / low_price * 100
                        is_historical_low = diff_percent <= 5
                        logger.debug(f"史低对比: 当前={current_price}, 史低={low_price}, 差异={diff_percent:.1f}%")

            return {
                "appid": appid,
                "name": details.get("name", "Unknown"),
                "current_price": current_price,
                "original_price": price_overview.get("initial", 0) / 100,
                "discount_percent": discount_percent,
                "historical_low": historical_low.get("price", 0) if historical_low else None,
                "image": details.get("header_image", ""),
                "short_description": details.get("short_description", ""),
                "tags": [genre["description"] for genre in details.get("genres", [])],
                "is_historical_low": is_historical_low,
                "priority": (100 if is_historical_low else 0) + discount_percent,
            }

        async with httpx.AsyncClient(timeout=30) as steam_client:
            itad_client: Optional[httpx.AsyncClient] = None
            if self.itad_api_key:
                itad_client = httpx.AsyncClient(timeout=30)

            try:
                tasks = [
                    asyncio.create_task(process_game(game, steam_client, itad_client))
                    for game in games_on_sale
                ]
                processed_games = await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                if itad_client:
                    await itad_client.aclose()

        all_games = []
        for item in processed_games:
            if isinstance(item, Exception):
                logger.error(f"处理史低游戏时出现异常: {item}")
                continue
            if item:
                all_games.append(item)

        if not all_games:
            logger.warning("处理后无可用游戏")
            return []

        # 按优先级排序：史低优先，然后按折扣从高到低
        all_games.sort(key=lambda x: x["priority"], reverse=True)

        # 取前N个
        results = all_games[:limit]

        logger.info(f"史低游戏查找完成，共找到 {len(results)} 个")
        for game in results:
            logger.info(f"  - {game['name']}: 折扣{game['discount_percent']}%, 史低={game['is_historical_low']}")

        return results

    async def get_top_sellers(self, limit: int = 10) -> List[Dict]:
        """
        获取Steam热销榜

        Args:
            limit: 返回数量

        Returns:
            热销游戏列表
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = "https://store.steampowered.com/search/results/"
                params = {
                    "json": "1",
                    "query": "",
                    "start": 0,
                    "count": limit,
                    "cc": "cn",
                    "l": "schinese",
                    "filter": "topsellers"
                }

                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.error(f"获取热销榜失败: {response.status_code}")
                    return []

                data = response.json()
                items = data.get("items", [])

                # 同步补充标签与高清头图
                async def enrich_item(item: Dict) -> Optional[Dict]:
                    appid = item.get("id")
                    if not appid:
                        return None
                    try:
                        details = await self.get_game_details(appid, client=client)
                    except Exception:
                        logger.debug("获取热销榜详情失败", exc_info=True)
                        details = None

                    tags = []
                    header_image = item.get("tiny_image", "")
                    if details:
                        tags = [genre.get("description", "") for genre in details.get("genres", []) if genre.get("description")]
                        header_image = details.get("header_image", header_image)
                    return {
                        "appid": appid,
                        "name": item.get("name"),
                        "price": item.get("price", {}).get("final", 0) / 100 if item.get("price") else 0,
                        "discount": item.get("discount_percent", 0),
                        "image": header_image,
                        "tags": tags,
                    }

                tasks = [enrich_item(item) for item in items]
                results_raw = await asyncio.gather(*tasks)
                results = [r for r in results_raw if r]

                return results

        except Exception as e:
            logger.error(f"获取热销榜失败: {e}")
            return []

    async def get_steam_specials_info(self) -> Optional[Dict]:
        """
        检测当前Steam特卖活动

        Returns:
            特卖信息字典，包含 {name, start_date, end_date, is_active}
        """
        # Steam特卖通常在特定时间段
        # 这里可以检查Steam的特卖页面或特定appid

        # 常见Steam特卖时间（近似）
        now = datetime.now()
        year = now.year

        sales_events = [
            {
                "name": "春季特卖",
                "start": datetime(year, 3, 15),
                "end": datetime(year, 3, 29)
            },
            {
                "name": "夏季特卖",
                "start": datetime(year, 6, 23),
                "end": datetime(year, 7, 7)
            },
            {
                "name": "秋季特卖",
                "start": datetime(year, 10, 31),
                "end": datetime(year, 11, 7)
            },
            {
                "name": "冬季特卖",
                "start": datetime(year, 12, 20),
                "end": datetime(year + 1, 1, 3)
            }
        ]

        # 检查当前是否在特卖期间
        for sale in sales_events:
            if sale["start"] <= now <= sale["end"]:
                return {
                    "name": sale["name"],
                    "start_date": sale["start"].strftime("%Y-%m-%d"),
                    "end_date": sale["end"].strftime("%Y-%m-%d"),
                    "is_active": True,
                    "days_left": (sale["end"] - now).days
                }

        # 检查即将到来的特卖（7天内）
        for sale in sales_events:
            days_until = (sale["start"] - now).days
            if 0 < days_until <= 7:
                return {
                    "name": sale["name"],
                    "start_date": sale["start"].strftime("%Y-%m-%d"),
                    "end_date": sale["end"].strftime("%Y-%m-%d"),
                    "is_active": False,
                    "days_until": days_until
                }

        return None

    # ==================== 新增 ITAD API 方法 ====================

    async def search_games_itad(
        self,
        title: str,
        limit: int = 20
    ) -> List[Dict]:
        """
        使用ITAD增强游戏搜索

        Args:
            title: 游戏名称关键字
            limit: 返回数量限制

        Returns:
            搜索结果列表，每个包含 {id, slug, title, type, mature}
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置，无法使用增强搜索")
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.itad_base_url}/games/search/v1"
                params = {
                    "key": self.itad_api_key,
                    "title": title,
                    "results": min(limit, 50)
                }

                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.error(f"ITAD搜索失败: {response.status_code}")
                    return []

                data = response.json()
                results = []

                for item in data:
                    results.append({
                        "id": item.get("id"),
                        "slug": item.get("slug"),
                        "title": item.get("title"),
                        "type": item.get("type"),
                        "mature": item.get("mature", False)
                    })

                logger.info(f"ITAD搜索 '{title}' 返回 {len(results)} 个结果")
                return results

        except Exception as e:
            logger.error(f"ITAD搜索失败: {e}", exc_info=True)
            return []

    async def get_itad_deals(
        self,
        limit: int = 20,
        offset: int = 0,
        sort: str = "-cut",
        country: str = "CN",
        shops: Optional[List[int]] = None
    ) -> Dict:
        """
        获取ITAD全网热门优惠

        Args:
            limit: 返回数量限制 (1-200)
            offset: 偏移量
            sort: 排序方式 ("-cut"=最高折扣, "price"=最低价格)
            country: 国家代码
            shops: 商店ID列表 (如 [61, 35] = Steam + GOG)

        Returns:
            优惠信息字典，包含 {nextOffset, hasMore, list}
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置，无法获取全网优惠")
            return {"nextOffset": 0, "hasMore": False, "list": []}

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.itad_base_url}/deals/v2"
                params = {
                    "key": self.itad_api_key,
                    "limit": min(limit, 200),
                    "offset": offset,
                    "sort": sort,
                    "country": country.upper(),
                    "nondeals": "false",
                    "mature": "false"
                }

                if shops:
                    params["shops"] = ",".join(map(str, shops))

                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.error(f"ITAD获取优惠失败: {response.status_code}")
                    return {"nextOffset": 0, "hasMore": False, "list": []}

                data = response.json()

                # 处理返回数据
                deals_list = []
                for item in data.get("list", []):
                    deal = item.get("deal", {})
                    shop = deal.get("shop", {})
                    price_info = deal.get("price", {})
                    regular_info = deal.get("regular", {})

                    deals_list.append({
                        "id": item.get("id"),
                        "slug": item.get("slug"),
                        "title": item.get("title"),
                        "type": item.get("type"),
                        "shop_id": shop.get("id"),
                        "shop_name": shop.get("name"),
                        "price": price_info.get("amount"),
                        "currency": price_info.get("currency"),
                        "regular_price": regular_info.get("amount"),
                        "cut": deal.get("cut", 0),
                        "voucher": deal.get("voucher"),
                        "url": deal.get("url"),
                        "drm": deal.get("drm", []),
                        "platforms": deal.get("platforms", []),
                        "timestamp": deal.get("timestamp"),
                        "expiry": deal.get("expiry"),
                        "history_low": deal.get("historyLow"),
                        "store_low": deal.get("storeLow")
                    })

                logger.info(f"ITAD获取到 {len(deals_list)} 个优惠")
                return {
                    "nextOffset": data.get("nextOffset", 0),
                    "hasMore": data.get("hasMore", False),
                    "list": deals_list
                }

        except Exception as e:
            logger.error(f"ITAD获取优惠失败: {e}", exc_info=True)
            return {"nextOffset": 0, "hasMore": False, "list": []}

    async def get_price_history(
        self,
        game_id: str,
        country: str = "CN",
        shops: Optional[List[int]] = None,
        since: Optional[str] = None
    ) -> List[Dict]:
        """
        获取游戏历史价格走势

        Args:
            game_id: ITAD游戏ID (UUID格式)
            country: 国家代码
            shops: 商店ID列表
            since: 起始日期 (ISO 8601格式)，默认最近3个月

        Returns:
            价格历史记录列表
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置，无法获取价格历史")
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.itad_base_url}/games/history/v2"
                params = {
                    "key": self.itad_api_key,
                    "id": game_id,
                    "country": country.upper()
                }

                if shops:
                    params["shops"] = ",".join(map(str, shops))
                if since:
                    params["since"] = since

                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.error(f"ITAD获取价格历史失败: {response.status_code}")
                    return []

                data = response.json()

                # 处理返回数据
                history_list = []
                for record in data:
                    shop = record.get("shop", {})
                    price_info = record.get("price", {})
                    regular_info = record.get("regular", {})

                    history_list.append({
                        "shop_id": shop.get("id"),
                        "shop_name": shop.get("name"),
                        "timestamp": record.get("timestamp"),
                        "price": price_info.get("amount"),
                        "currency": price_info.get("currency"),
                        "regular_price": regular_info.get("amount") if regular_info else None,
                        "cut": record.get("cut", 0)
                    })

                # 按时间排序
                history_list.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

                logger.info(f"ITAD获取到 {len(history_list)} 条价格历史")
                return history_list

        except Exception as e:
            logger.error(f"ITAD获取价格历史失败: {e}", exc_info=True)
            return []

    async def get_game_subscriptions(
        self,
        game_ids: List[str],
        country: str = "CN"
    ) -> List[Dict]:
        """
        查询游戏所在的订阅服务

        Args:
            game_ids: ITAD游戏ID列表 (UUID格式)
            country: 国家代码

        Returns:
            订阅信息列表，每个包含 {id, subs: [{id, name}]}
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置，无法查询订阅服务")
            return []

        if not game_ids:
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.itad_base_url}/games/subs/v1"
                params = {
                    "key": self.itad_api_key,
                    "country": country.upper()
                }

                # 使用POST请求，请求体为游戏ID列表
                response = await client.post(url, params=params, json=game_ids[:200])
                if response.status_code != 200:
                    logger.error(f"ITAD获取订阅信息失败: {response.status_code}")
                    return []

                data = response.json()

                # 处理返回数据
                results = []
                for item in data:
                    subs = []
                    for sub in item.get("subs", []):
                        subs.append({
                            "id": sub.get("id"),
                            "name": sub.get("name")
                        })

                    results.append({
                        "id": item.get("id"),
                        "subs": subs
                    })

                logger.info(f"ITAD查询到 {len(results)} 个游戏的订阅信息")
                return results

        except Exception as e:
            logger.error(f"ITAD获取订阅信息失败: {e}", exc_info=True)
            return []

    async def get_all_platform_prices(
        self,
        game_ids: List[str],
        country: str = "CN",
        shops: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        获取游戏在所有平台的价格（跨平台比价）

        Args:
            game_ids: ITAD游戏ID列表 (UUID格式)
            country: 国家代码
            shops: 商店ID列表，None表示所有商店

        Returns:
            价格信息列表
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置，无法获取跨平台价格")
            return []

        if not game_ids:
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.itad_base_url}/games/prices/v3"
                params = {
                    "key": self.itad_api_key,
                    "country": country.upper()
                }

                if shops:
                    params["shops"] = ",".join(map(str, shops))

                response = await client.post(url, params=params, json=game_ids[:200])
                if response.status_code != 200:
                    logger.error(f"ITAD获取跨平台价格失败: {response.status_code}")
                    return []

                data = response.json()

                # 处理返回数据
                results = []
                for item in data:
                    deals = []
                    for deal in item.get("deals", []):
                        shop = deal.get("shop", {})
                        price_info = deal.get("price", {})
                        regular_info = deal.get("regular", {})

                        deals.append({
                            "shop_id": shop.get("id"),
                            "shop_name": shop.get("name"),
                            "price": price_info.get("amount"),
                            "currency": price_info.get("currency"),
                            "regular_price": regular_info.get("amount"),
                            "cut": deal.get("cut", 0),
                            "voucher": deal.get("voucher"),
                            "url": deal.get("url"),
                            "drm": deal.get("drm", []),
                            "platforms": deal.get("platforms", []),
                            "store_low": deal.get("storeLow"),
                            "history_low": deal.get("historyLow")
                        })

                    # 按价格排序
                    deals.sort(key=lambda x: x.get("price", 999999) or 999999)

                    results.append({
                        "id": item.get("id"),
                        "deals": deals,
                        "history_low": item.get("historyLow")
                    })

                logger.info(f"ITAD获取到 {len(results)} 个游戏的跨平台价格")
                return results

        except Exception as e:
            logger.error(f"ITAD获取跨平台价格失败: {e}", exc_info=True)
            return []

    async def lookup_game_id(
        self,
        appid: Optional[int] = None,
        title: Optional[str] = None
    ) -> Optional[str]:
        """
        通过Steam appid或游戏名称查找ITAD游戏ID

        Args:
            appid: Steam游戏ID
            title: 游戏名称

        Returns:
            ITAD游戏ID (UUID格式)
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置")
            return None

        if not appid and not title:
            return None

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.itad_base_url}/games/lookup/v1"
                params = {"key": self.itad_api_key}

                if appid:
                    params["appid"] = appid
                elif title:
                    params["title"] = title

                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.debug(f"ITAD lookup失败: {response.status_code}")
                    return None

                data = response.json()
                if data and "game" in data:
                    return data["game"].get("id")

                return None

        except Exception as e:
            logger.error(f"ITAD lookup失败: {e}", exc_info=True)
            return None

    async def get_shops_list(self) -> List[Dict]:
        """
        获取ITAD支持的商店列表

        Returns:
            商店列表，每个包含 {id, title}
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置")
            return []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                url = f"{self.itad_base_url}/service/shops/v1"
                params = {"key": self.itad_api_key}

                response = await client.get(url, params=params)
                if response.status_code != 200:
                    logger.error(f"ITAD获取商店列表失败: {response.status_code}")
                    return []

                data = response.json()
                return [{"id": shop.get("id"), "title": shop.get("title")} for shop in data]

        except Exception as e:
            logger.error(f"ITAD获取商店列表失败: {e}", exc_info=True)
            return []
