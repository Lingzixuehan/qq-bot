"""
Steam商店和价格API模块
支持ITAD (IsThereAnyDeal) API和Steam Store API集成
"""
import asyncio
import httpx
import re
from html import unescape
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
from nonebot.log import logger


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
    ) -> Optional[Dict]:
        """
        获取游戏详细信息

        Args:
            appid: Steam游戏ID
            country: 国家代码

        Returns:
            游戏详情字典
        """
        session = client or httpx.AsyncClient(timeout=30)
        try:
            url = f"{self.steam_store_url}/appdetails"
            params = {
                "appids": appid,
                "cc": country,
                "l": "schinese"
            }

            response = await session.get(url, params=params)
            if response.status_code != 200:
                return None

            data = response.json()
            if str(appid) in data and data[str(appid)]["success"]:
                return data[str(appid)]["data"]

            return None
        except Exception as e:
            logger.error(f"获取游戏详情失败 (appid={appid}): {e}")
            return None
        finally:
            if client is None:
                await session.aclose()

    async def get_historical_low(
        self,
        appid: int,
        client: Optional[httpx.AsyncClient] = None
    ) -> Optional[Dict]:
        """
        获取游戏史低价格（使用ITAD API）

        Args:
            appid: Steam游戏ID

        Returns:
            史低价格信息
        """
        if not self.itad_api_key:
            logger.warning("ITAD API密钥未配置，无法获取史低价格")
            return None

        session = client or httpx.AsyncClient(timeout=30)
        try:
            # 首先搜索游戏ID
            url = f"{self.itad_base_url}/games/lookup/v1"
            params = {
                "key": self.itad_api_key,
                "shop": "steam",
                "game_id": f"app/{appid}"
            }

            response = await session.get(url, params=params)
            if response.status_code != 200:
                return None

            data = response.json()
            if not data or "game" not in data:
                return None

            game_id = data["game"]["id"]

            # 获取历史最低价
            url = f"{self.itad_base_url}/games/historylow/v1"
            params = {
                "key": self.itad_api_key,
                "id": game_id,
                "country": "CN",
                "shops": "steam"
            }

            response = await session.get(url, params=params)
            if response.status_code != 200:
                return None

            history_data = response.json()
            return history_data.get("data", {})

        except Exception as e:
            logger.error(f"获取史低价格失败 (appid={appid}): {e}")
            return None
        finally:
            if client is None:
                await session.aclose()

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
                    historical_low = await self.get_historical_low(appid, client=itad_client)
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

                # 格式化结果
                results = []
                for item in items:
                    results.append({
                        "appid": item.get("id"),
                        "name": item.get("name"),
                        "price": item.get("price", {}).get("final", 0) / 100 if item.get("price") else 0,
                        "discount": item.get("discount_percent", 0),
                        "image": item.get("tiny_image", "")
                    })

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
