"""
Steam工具函数模块
"""
import httpx
from io import BytesIO
from PIL import Image
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime, timezone, timedelta


async def _fetch_avatar(avatar_url: str, proxy: Optional[str] = None) -> Image.Image:
    """
    异步获取头像图片

    Args:
        avatar_url: 头像URL
        proxy: 代理地址

    Returns:
        PIL Image对象，失败时返回默认头像
    """
    try:
        async with httpx.AsyncClient(proxies=proxy, timeout=30.0) as client:
            response = await client.get(avatar_url)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
    except Exception:
        # 返回默认头像
        default_avatar_path = Path(__file__).parent / "res/unknown_avatar.jpg"
        return Image.open(default_avatar_path)


async def fetch_avatar(
    player: Dict[str, Any],
    avatar_dir: Path,
    proxy: Optional[str] = None
) -> Image.Image:
    """
    获取头像（带缓存）

    Args:
        player: 玩家信息字典
        avatar_dir: 头像缓存目录
        proxy: 代理地址

    Returns:
        PIL Image对象
    """
    steam_id = player.get("steamid", "")
    avatar_hash = player.get("avatarhash", "")
    cache_path = avatar_dir / f"{steam_id}_{avatar_hash}.png"

    # 检查缓存
    if cache_path.exists():
        try:
            return Image.open(cache_path)
        except Exception:
            pass

    # 下载头像
    avatar_url = player.get("avatarfull") or player.get("avatarmedium") or player.get("avatar", "")
    if not avatar_url:
        default_avatar_path = Path(__file__).parent / "res/unknown_avatar.jpg"
        return Image.open(default_avatar_path)

    avatar = await _fetch_avatar(avatar_url, proxy)

    # 保存缓存
    try:
        avatar_dir.mkdir(parents=True, exist_ok=True)
        avatar.save(cache_path)
    except Exception:
        pass

    return avatar


def convert_player_name_to_nickname(
    data: Dict[str, Any],
    parent_id: str,
    bind_data: Any
) -> str:
    """
    将玩家名称转换为昵称

    Args:
        data: 玩家数据
        parent_id: 群组ID
        bind_data: 绑定数据对象

    Returns:
        昵称或原始名称
    """
    steam_id = data.get("steamid", "")
    bind_info = bind_data.get_by_steam_id(parent_id, steam_id)

    if bind_info and bind_info.get("nickname"):
        return bind_info["nickname"]

    return data.get("personaname", steam_id)


def simplize_steam_player_data(
    player: Dict[str, Any],
    proxy: Optional[str] = None,
    avatar_dir: Optional[Path] = None
) -> Dict[str, Any]:
    """
    简化Steam玩家数据

    Args:
        player: 原始玩家数据
        proxy: 代理地址
        avatar_dir: 头像缓存目录

    Returns:
        简化后的数据字典
    """
    # 获取在线状态文本
    persona_state = player.get("personastate", 0)
    state_map = {
        0: "离线",
        1: "在线",
        2: "忙碌",
        3: "离开",
        4: "打盹",
        5: "想交易",
        6: "想玩游戏"
    }
    state_text = state_map.get(persona_state, "未知")

    return {
        "steamid": player.get("steamid", ""),
        "personaname": player.get("personaname", "Unknown"),
        "avatar": player.get("avatarfull", ""),
        "profileurl": player.get("profileurl", ""),
        "personastate": persona_state,
        "personastate_text": state_text,
        "gameextrainfo": player.get("gameextrainfo"),
        "gameid": player.get("gameid"),
        "lastlogoff": player.get("lastlogoff", 0),
    }


def image_to_bytes(image: Image.Image) -> bytes:
    """
    将PIL Image转换为字节数据

    Args:
        image: PIL Image对象

    Returns:
        PNG格式的字节数据
    """
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def hex_to_rgb(hex_color: str) -> tuple:
    """
    将十六进制颜色转换为RGB元组

    Args:
        hex_color: 十六进制颜色字符串 (如 "#FFFFFF")

    Returns:
        RGB元组 (r, g, b)
    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def convert_timestamp_to_beijing_time(timestamp: int) -> str:
    """
    将Unix时间戳转换为北京时间字符串

    Args:
        timestamp: Unix时间戳

    Returns:
        格式化的时间字符串 "YYYY-MM-DD HH:MM:SS"
    """
    beijing_tz = timezone(timedelta(hours=8))
    dt = datetime.fromtimestamp(timestamp, tz=beijing_tz)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_play_duration(seconds: int) -> str:
    """
    格式化游戏时长

    Args:
        seconds: 秒数

    Returns:
        格式化的时长字符串
    """
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes}分钟"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时"
