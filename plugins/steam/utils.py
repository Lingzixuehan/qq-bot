"""
Steam工具函数模块
"""
import httpx
from io import BytesIO
from PIL import Image
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from nonebot.log import logger


async def fetch_qq_group_avatar(group_id: str, size: int = 640) -> Image.Image:
    """
    获取QQ群头像

    Args:
        group_id: QQ群号
        size: 头像尺寸 (100, 640等)

    Returns:
        PIL Image对象，失败时返回默认头像
    """
    avatar_url = f"http://p.qlogo.cn/gh/{group_id}/{group_id}/{size}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(avatar_url)
            response.raise_for_status()
            return Image.open(BytesIO(response.content))
    except Exception as e:
        logger.warning(f"获取QQ群头像失败 {group_id}: {e}")
        # 返回默认头像
        default_avatar_path = Path(__file__).parent / "res/unknown_avatar.jpg"
        if default_avatar_path.exists():
            return Image.open(default_avatar_path)
        # 如果默认头像也不存在，创建一个灰色占位图
        return Image.new("RGB", (size, size), (100, 100, 100))


def _load_default_avatar(size: int = 100) -> Image.Image:
    """返回默认头像"""
    default_avatar_path = Path(__file__).parent / "res/unknown_avatar.jpg"
    if default_avatar_path.exists():
        with Image.open(default_avatar_path) as img:
            return img.convert("RGB")
    return Image.new("RGB", (size, size), (100, 100, 100))


async def _fetch_avatar(avatar_url: str, proxy: Optional[str] = None) -> Tuple[Image.Image, bool]:
    """
    异步获取头像图片

    Args:
        avatar_url: 头像URL
        proxy: 代理地址

    Returns:
        PIL Image对象，失败时返回默认头像
    """
    client_kwargs = {"timeout": 30.0}
    if proxy:
        client_kwargs["proxies"] = proxy

    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            logger.debug(f"正在获取头像: {avatar_url}")
            response = await client.get(avatar_url)
            response.raise_for_status()
            with Image.open(BytesIO(response.content)) as img:
                return img.convert("RGB"), True
    except Exception as e:
        logger.warning(f"获取头像失败 {avatar_url}: {e}")
        return _load_default_avatar(), False


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
    cache_version = "v2"

    # 如果有avatar_hash，使用它作为缓存key
    if avatar_hash:
        cache_path = avatar_dir / f"{steam_id}_{avatar_hash}_{cache_version}.png"
    else:
        cache_path = avatar_dir / f"{steam_id}_{cache_version}.png"

    # 检查缓存
    if cache_path.exists():
        try:
            logger.debug(f"使用缓存头像: {cache_path}")
            with Image.open(cache_path) as img:
                return img.convert("RGB")
        except Exception as e:
            logger.warning(f"读取缓存头像失败 {cache_path}: {e}")

    # 下载头像
    avatar_url = player.get("avatarfull") or player.get("avatarmedium") or player.get("avatar", "")
    if not avatar_url:
        logger.warning(f"玩家 {steam_id} 没有头像URL，使用默认头像")
        return _load_default_avatar()

    logger.debug(f"下载头像 {steam_id}: {avatar_url}")
    avatar, downloaded = await _fetch_avatar(avatar_url, proxy)

    # 保存缓存
    try:
        if downloaded:
            avatar_dir.mkdir(parents=True, exist_ok=True)
            avatar.save(cache_path)
            logger.debug(f"头像已缓存: {cache_path}")
        elif cache_path.exists():
            try:
                cache_path.unlink()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"保存头像缓存失败 {cache_path}: {e}")

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
