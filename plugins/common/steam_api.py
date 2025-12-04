"""
Steam Web API 工具类
用于查询Steam用户信息、游戏库等
"""
import httpx
from typing import Optional, List, Dict
import os


class SteamAPI:
    """Steam Web API封装"""

    BASE_URL = "https://api.steampowered.com"

    def __init__(self, api_key: str):
        """
        初始化Steam API

        Args:
            api_key: Steam Web API Key
        """
        self.api_key = api_key

    async def get_player_summaries(self, steam_id: str) -> Optional[Dict]:
        """
        获取玩家资料

        Args:
            steam_id: Steam ID (64位)

        Returns:
            玩家资料字典，包含昵称、头像、状态等信息
        """
        try:
            url = f"{self.BASE_URL}/ISteamUser/GetPlayerSummaries/v0002/"
            params = {
                "key": self.api_key,
                "steamids": steam_id
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    players = data.get("response", {}).get("players", [])
                    if players:
                        return players[0]
        except Exception as e:
            print(f"获取玩家资料失败: {e}")

        return None

    async def get_multiple_player_summaries(self, steam_ids: List[str]) -> List[Dict]:
        """
        批量获取玩家资料

        Args:
            steam_ids: Steam ID列表 (最多100个)

        Returns:
            玩家资料列表
        """
        try:
            # Steam API限制一次最多100个ID
            if len(steam_ids) > 100:
                steam_ids = steam_ids[:100]

            url = f"{self.BASE_URL}/ISteamUser/GetPlayerSummaries/v0002/"
            params = {
                "key": self.api_key,
                "steamids": ",".join(steam_ids)
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    players = data.get("response", {}).get("players", [])
                    return players
        except Exception as e:
            print(f"批量获取玩家资料失败: {e}")

        return []

    async def get_owned_games(self, steam_id: str, include_appinfo: bool = True) -> Optional[List[Dict]]:
        """
        获取拥有的游戏列表

        Args:
            steam_id: Steam ID
            include_appinfo: 是否包含游戏详细信息

        Returns:
            游戏列表
        """
        try:
            url = f"{self.BASE_URL}/IPlayerService/GetOwnedGames/v0001/"
            params = {
                "key": self.api_key,
                "steamid": steam_id,
                "include_appinfo": 1 if include_appinfo else 0,
                "include_played_free_games": 1,
                "format": "json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    games = data.get("response", {}).get("games", [])
                    return games
        except Exception as e:
            print(f"获取游戏库失败: {e}")

        return None

    async def get_recently_played_games(self, steam_id: str, count: int = 5) -> Optional[List[Dict]]:
        """
        获取最近玩的游戏

        Args:
            steam_id: Steam ID
            count: 返回游戏数量

        Returns:
            最近玩的游戏列表
        """
        try:
            url = f"{self.BASE_URL}/IPlayerService/GetRecentlyPlayedGames/v0001/"
            params = {
                "key": self.api_key,
                "steamid": steam_id,
                "count": count,
                "format": "json"
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    games = data.get("response", {}).get("games", [])
                    return games
        except Exception as e:
            print(f"获取最近玩的游戏失败: {e}")

        return None

    async def resolve_vanity_url(self, vanity_url: str) -> Optional[str]:
        """
        解析个性化URL到Steam ID

        Args:
            vanity_url: 个性化URL (例如: "gaben")

        Returns:
            Steam ID (64位)
        """
        try:
            url = f"{self.BASE_URL}/ISteamUser/ResolveVanityURL/v0001/"
            params = {
                "key": self.api_key,
                "vanityurl": vanity_url
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    if data.get("response", {}).get("success") == 1:
                        return data["response"]["steamid"]
        except Exception as e:
            print(f"解析个性化URL失败: {e}")

        return None


def format_playtime(minutes: int) -> str:
    """
    格式化游戏时长

    Args:
        minutes: 游戏时长（分钟）

    Returns:
        格式化后的时长字符串
    """
    if minutes < 60:
        return f"{minutes}分钟"

    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}小时"

    days = hours / 24
    return f"{days:.1f}天"


def get_player_state_text(state: int) -> str:
    """
    获取玩家状态文本

    Args:
        state: 状态代码

    Returns:
        状态文本
    """
    states = {
        0: "离线",
        1: "在线",
        2: "忙碌",
        3: "离开",
        4: "打盹",
        5: "想交易",
        6: "想玩游戏"
    }
    return states.get(state, "未知")
