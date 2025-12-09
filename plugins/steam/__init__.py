"""
Steam功能插件 - 完整版
支持Steam账号绑定、资料查询、游戏库查询、好友状态监控、自动播报等功能
"""
import base64
from datetime import datetime, timezone
import re
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional
import httpx
from PIL import Image

from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.log import logger
from nonebot.plugin import PluginMetadata
from nonebot.exception import FinishedException

# 尝试导入可选依赖
scheduler = None
store = None
HAS_APSCHEDULER = False
HAS_LOCALSTORE = False

try:
    from nonebot import require
    require("nonebot_plugin_apscheduler")
    from nonebot_plugin_apscheduler import scheduler
    HAS_APSCHEDULER = True
    logger.info("nonebot_plugin_apscheduler 已加载，自动播报功能已启用")
except Exception as e:
    logger.warning(f"nonebot_plugin_apscheduler 未安装，自动播报功能已禁用: {e}")

try:
    from nonebot import require
    require("nonebot_plugin_localstore")
    import nonebot_plugin_localstore as store
    HAS_LOCALSTORE = True
    logger.info("nonebot_plugin_localstore 已加载")
except Exception as e:
    logger.warning(f"nonebot_plugin_localstore 未安装，将使用本地目录存储: {e}")

# 导入公共模块
import sys
sys.path.append(str(Path(__file__).parent.parent))
from common.database import SteamDB
from common.steam_api import SteamAPI, format_playtime, get_player_state_text

# 导入新模块
from .data_source import BindData, SteamInfoData, ParentData, DisableParentData, SubscriptionData
from .draw import draw_friends_status, draw_friends_status_steam, draw_start_gaming, draw_game_list_with_tags, draw_game_price_info
from .utils import fetch_avatar, fetch_qq_group_avatar, convert_player_name_to_nickname
from .models import Player, ProcessedPlayer
from .steam_store_api import SteamStoreAPI

# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="Steam功能",
    description="Steam账号绑定、资料查询、游戏状态监控",
    usage=(
        "/绑定steam <Steam ID或个性化URL> - 绑定Steam账号\n"
        "/解绑steam - 解绑Steam账号\n"
        "/steam资料 [@用户] - 查看Steam个人资料\n"
        "/steam游戏 [@用户] - 查看最近在玩的游戏\n"
        "/steam游戏库 [@用户] - 查看游戏库\n"
        "/steam视奸 - 查看所有绑定用户的Steam状态\n"
        "/steam昵称 <昵称> - 设置Steam显示昵称\n"
        "/steam启用播报 - 在当前群启用游戏状态播报\n"
        "/steam禁用播报 - 在当前群禁用游戏状态播报\n"
        "/steam价格 <游戏名> [| 对比区列表] - 查询游戏价格和史低\n"
        "/steam喜加一 - 查看当前限时免费游戏\n"
        "/steam喜加一订阅 / steam喜加一退订 - 订阅或退订喜加一推送\n"
        "/steam折扣订阅 / steam折扣退订 - 订阅或退订高折扣推送\n"
        "/steam帮助 - 显示Steam插件帮助"
    )
)

# 获取配置
driver = get_driver()
config = driver.config
STEAM_API_KEY = getattr(config, "steam_api_key", None)
STEAM_BROADCAST_INTERVAL = getattr(config, "steam_broadcast_interval", 300)  # 默认5分钟
STEAM_BROADCAST_ENABLED = getattr(config, "steam_broadcast_enabled", True)
ITAD_API_KEY = getattr(config, "itad_api_key", None)  # IsThereAnyDeal API密钥
# 价格查询配置
STEAM_PRICE_COMPARE_REGIONS = getattr(
    config, "steam_price_compare_regions", ["cn", "us", "jp"]
)
STEAM_PRICE_EXCHANGE_RATES = getattr(
    config,
    "steam_price_exchange_rates",
    {
        "CNY": 1,
        "USD": 7.2,
        "EUR": 7.8,
        "UAH": 0.2,
        "JPY": 0.052,
    },
)

# 初始化Steam API
steam_api: Optional[SteamAPI] = None
if STEAM_API_KEY:
    steam_api = SteamAPI(STEAM_API_KEY)
else:
    logger.warning("Steam API Key未配置，Steam功能将无法使用")

# 初始化Steam商店API
steam_store_api: Optional[SteamStoreAPI] = None
if ITAD_API_KEY:
    steam_store_api = SteamStoreAPI(ITAD_API_KEY)
    logger.info("Steam商店API已初始化（ITAD支持）")
else:
    steam_store_api = SteamStoreAPI()  # 无ITAD支持，部分功能受限
    logger.warning("ITAD API Key未配置，史低价格查询功能将受限")

# 获取数据目录
if HAS_LOCALSTORE and store:
    plugin_data_dir = store.get_plugin_data_dir()
    plugin_cache_dir = store.get_plugin_cache_dir()
else:
    # 使用本地目录
    plugin_data_dir = Path(__file__).parent / "data"
    plugin_cache_dir = Path(__file__).parent / "cache"
    plugin_data_dir.mkdir(parents=True, exist_ok=True)
    plugin_cache_dir.mkdir(parents=True, exist_ok=True)

# 初始化数据管理类
bind_data = BindData(plugin_data_dir / "bind_data.json")
steam_info_data = SteamInfoData(plugin_cache_dir / "steam_info.json")
parent_data = ParentData(plugin_data_dir / "parent_data.json")
disable_parent_data = DisableParentData(plugin_data_dir / "disabled_parents.json")
subscription_data = SubscriptionData(plugin_data_dir / "steam_subscriptions.json")

# 头像缓存目录
avatar_cache_dir = plugin_cache_dir / "avatars"
avatar_cache_dir.mkdir(parents=True, exist_ok=True)


def pil_image_to_base64(image) -> str:
    """
    将PIL Image转换为base64字符串

    Args:
        image: PIL Image对象

    Returns:
        base64编码的图片字符串
    """
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return f"base64://{base64.b64encode(buffer.getvalue()).decode()}"


async def fetch_image_bytes(url: str, client: httpx.AsyncClient) -> Optional[bytes]:
    """下载图片数据，失败返回None"""
    if not url:
        return None
    try:
        resp = await client.get(url)
        if resp.status_code == 200:
            return resp.content
    except Exception:
        logger.debug(f"下载图片失败: {url}", exc_info=True)
    return None


async def generate_recent_games_image(player_info: Dict, games: List[Dict], qq_user: str = None) -> str:
    """
    生成最近游戏列表图片（使用新的美化样式）

    Args:
        player_info: Steam玩家信息
        games: 最近玩的游戏列表
        qq_user: QQ用户昵称（可选）

    Returns:
        base64编码的图片字符串
    """
    from PIL import Image, ImageDraw, ImageFont
    import asyncio

    # 颜色方案 - 深色主题
    BG_COLOR = (26, 32, 44)
    CARD_BG = (45, 55, 72)
    ACCENT_COLOR = (102, 126, 234)
    TEXT_PRIMARY = (237, 242, 247)
    TEXT_SECONDARY = (160, 174, 192)
    GAME_HIGHLIGHT = (72, 187, 120)

    WIDTH = 800
    PADDING = 30
    AVATAR_SIZE = 80

    # 字体路径
    font_dir = Path(__file__).parent.parent.parent / "fonts"
    try:
        font_title = ImageFont.truetype(str(font_dir / "MiSans-Bold.ttf"), 32)
        font_large = ImageFont.truetype(str(font_dir / "MiSans-Bold.ttf"), 24)
        font_normal = ImageFont.truetype(str(font_dir / "MiSans-Regular.ttf"), 20)
        font_small = ImageFont.truetype(str(font_dir / "MiSans-Light.ttf"), 16)
    except Exception:
        # 降级到默认字体
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 计算高度
    header_height = 160
    game_item_height = 90
    total_height = header_height + len(games) * game_item_height + PADDING * 2

    # 创建图片
    img = Image.new('RGB', (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = PADDING

    # 下载头像
    avatar_url = player_info.get("avatarfull", "")
    avatar = None
    if avatar_url:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(avatar_url, timeout=5)
                if response.status_code == 200:
                    avatar = Image.open(BytesIO(response.content)).resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.warning(f"下载头像失败: {e}")

    # 绘制头部
    if avatar:
        img.paste(avatar, (PADDING, y))

    # 玩家信息
    info_x = PADDING + AVATAR_SIZE + 20
    personaname = player_info.get("personaname", "未知用户")
    draw.text((info_x, y), personaname, fill=TEXT_PRIMARY, font=font_large)
    y += 35

    if qq_user:
        draw.text((info_x, y), f"QQ: {qq_user}", fill=TEXT_SECONDARY, font=font_small)
        y += 25

    # 游戏数量
    draw.text((info_x, y), f"最近玩了 {len(games)} 款游戏", fill=GAME_HIGHLIGHT, font=font_normal)

    y = header_height

    # 绘制标题栏
    draw.text((PADDING, y), "📋 最近游戏", fill=ACCENT_COLOR, font=font_title)
    y += 50

    # 绘制游戏列表
    for i, game in enumerate(games):
        # 卡片背景
        card_y = y + i * game_item_height
        draw.rectangle(
            [(PADDING, card_y), (WIDTH - PADDING, card_y + game_item_height - 10)],
            fill=CARD_BG,
            outline=None
        )

        # 游戏名称
        game_name = game.get("name", "未知游戏")
        if len(game_name) > 35:
            game_name = game_name[:35] + "..."

        draw.text((PADDING + 15, card_y + 15), f"{i+1}. {game_name}", fill=TEXT_PRIMARY, font=font_normal)

        # 游戏时长
        playtime_2weeks = game.get("playtime_2weeks", 0)
        playtime_forever = game.get("playtime_forever", 0)

        time_y = card_y + 50
        draw.text(
            (PADDING + 30, time_y),
            f"最近2周: {format_playtime(playtime_2weeks)}",
            fill=GAME_HIGHLIGHT,
            font=font_small
        )

        draw.text(
            (PADDING + 250, time_y),
            f"总计: {format_playtime(playtime_forever)}",
            fill=TEXT_SECONDARY,
            font=font_small
        )

    return pil_image_to_base64(img)


async def generate_player_profile_image(player_info: Dict, recent_games: List[Dict] = None, qq_user: str = None) -> str:
    """
    生成Steam个人资料图片（使用新的美化样式）

    Args:
        player_info: Steam玩家信息
        recent_games: 最近玩的游戏列表（可选，显示前3个）
        qq_user: QQ用户昵称（可选）

    Returns:
        base64编码的图片字符串
    """
    from PIL import Image, ImageDraw, ImageFont

    # 颜色方案
    BG_COLOR = (26, 32, 44)
    CARD_BG = (45, 55, 72)
    ACCENT_COLOR = (102, 126, 234)
    TEXT_PRIMARY = (237, 242, 247)
    TEXT_SECONDARY = (160, 174, 192)
    STATUS_ONLINE = (72, 187, 120)
    STATUS_GAMING = (236, 201, 75)

    WIDTH = 800
    PADDING = 30
    AVATAR_SIZE = 120

    # 字体
    font_dir = Path(__file__).parent.parent.parent / "fonts"
    try:
        font_title = ImageFont.truetype(str(font_dir / "MiSans-Bold.ttf"), 36)
        font_large = ImageFont.truetype(str(font_dir / "MiSans-Bold.ttf"), 26)
        font_normal = ImageFont.truetype(str(font_dir / "MiSans-Regular.ttf"), 20)
        font_small = ImageFont.truetype(str(font_dir / "MiSans-Light.ttf"), 16)
    except Exception:
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 计算高度
    header_height = 200
    games_section_height = 0
    if recent_games:
        games_section_height = min(3, len(recent_games)) * 70 + 80

    total_height = header_height + games_section_height + PADDING * 2

    # 创建图片
    img = Image.new('RGB', (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = PADDING

    # 标题
    draw.text((PADDING, y), "🎮 Steam 个人资料", fill=ACCENT_COLOR, font=font_title)
    y += 60

    # 下载头像
    avatar_url = player_info.get("avatarfull", "")
    avatar = None
    if avatar_url:
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(avatar_url, timeout=5)
                if response.status_code == 200:
                    avatar = Image.open(BytesIO(response.content)).resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
        except Exception as e:
            logger.warning(f"下载头像失败: {e}")

    if avatar:
        img.paste(avatar, (PADDING, y))

    # 用户信息
    info_x = PADDING + AVATAR_SIZE + 25
    info_y = y

    # Steam昵称
    personaname = player_info.get("personaname", "未知用户")
    draw.text((info_x, info_y), personaname, fill=TEXT_PRIMARY, font=font_large)
    info_y += 38

    # 状态
    game_name = player_info.get("gameextrainfo", None)
    if game_name:
        draw.text((info_x, info_y), "状态: 游戏中", fill=STATUS_GAMING, font=font_normal)
        info_y += 30
        draw.text((info_x, info_y), f"正在玩: {game_name}", fill=STATUS_GAMING, font=font_small)
    else:
        state = get_player_state_text(player_info.get("personastate", 0))
        status_color = STATUS_ONLINE if player_info.get("personastate", 0) > 0 else TEXT_SECONDARY
        draw.text((info_x, info_y), f"状态: {state}", fill=status_color, font=font_normal)

    info_y += 35

    # QQ用户
    if qq_user:
        draw.text((info_x, info_y), f"QQ: {qq_user}", fill=TEXT_SECONDARY, font=font_small)

    y += AVATAR_SIZE + 30

    # 最近游戏
    if recent_games and len(recent_games) > 0:
        # 分隔线
        draw.line([(PADDING, y), (WIDTH - PADDING, y)], fill=TEXT_SECONDARY, width=2)
        y += 25

        draw.text((PADDING, y), "📋 最近游戏", fill=ACCENT_COLOR, font=font_large)
        y += 45

        for game in recent_games[:3]:  # 只显示前3个
            game_name = game.get("name", "未知游戏")
            if len(game_name) > 40:
                game_name = game_name[:40] + "..."

            playtime_2weeks = game.get("playtime_2weeks", 0)
            playtime_forever = game.get("playtime_forever", 0)

            # 游戏名
            draw.text((PADDING + 10, y), f"• {game_name}", fill=TEXT_PRIMARY, font=font_normal)
            y += 32

            # 时长
            draw.text(
                (PADDING + 25, y),
                f"最近: {format_playtime(playtime_2weeks)} | 总计: {format_playtime(playtime_forever)}",
                fill=TEXT_SECONDARY,
                font=font_small
            )
            y += 38

    return pil_image_to_base64(img)


async def generate_game_library_image(games: List[Dict], qq_user: str = None) -> str:
    """
    生成Steam游戏库图片（使用新的美化样式）

    Args:
        games: 游戏列表
        qq_user: QQ用户昵称（可选）

    Returns:
        base64编码的图片字符串
    """
    from PIL import Image, ImageDraw, ImageFont

    # 颜色方案
    BG_COLOR = (26, 32, 44)
    CARD_BG = (45, 55, 72)
    ACCENT_COLOR = (102, 126, 234)
    TEXT_PRIMARY = (237, 242, 247)
    TEXT_SECONDARY = (160, 174, 192)
    HIGHLIGHT_COLOR = (236, 201, 75)

    WIDTH = 800
    PADDING = 30

    # 字体
    font_dir = Path(__file__).parent.parent.parent / "fonts"
    try:
        font_title = ImageFont.truetype(str(font_dir / "MiSans-Bold.ttf"), 36)
        font_large = ImageFont.truetype(str(font_dir / "MiSans-Bold.ttf"), 24)
        font_normal = ImageFont.truetype(str(font_dir / "MiSans-Regular.ttf"), 18)
        font_small = ImageFont.truetype(str(font_dir / "MiSans-Light.ttf"), 16)
    except Exception:
        font_title = ImageFont.load_default()
        font_large = ImageFont.load_default()
        font_normal = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # 统计数据
    total_games = len(games)
    total_playtime = sum(game.get("playtime_forever", 0) for game in games)
    games_sorted = sorted(games, key=lambda x: x.get("playtime_forever", 0), reverse=True)

    # 显示前15个游戏
    display_count = min(15, len(games_sorted))

    # 计算高度
    header_height = 240
    game_item_height = 55
    total_height = header_height + display_count * game_item_height + PADDING * 2

    # 创建图片
    img = Image.new('RGB', (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    y = PADDING

    # 标题
    draw.text((PADDING, y), "📚 Steam 游戏库", fill=ACCENT_COLOR, font=font_title)
    y += 60

    # QQ用户
    if qq_user:
        draw.text((PADDING, y), f"QQ用户: {qq_user}", fill=TEXT_SECONDARY, font=font_small)
        y += 30

    # 统计信息
    draw.text((PADDING, y), f"游戏总数: {total_games} 款", fill=HIGHLIGHT_COLOR, font=font_large)
    y += 40

    draw.text((PADDING, y), f"总游戏时长: {format_playtime(total_playtime)}", fill=TEXT_PRIMARY, font=font_normal)
    y += 45

    # 分隔线
    draw.line([(PADDING, y), (WIDTH - PADDING, y)], fill=TEXT_SECONDARY, width=2)
    y += 25

    # TOP游戏标题
    draw.text((PADDING, y), "🏆 游戏时长排行", fill=ACCENT_COLOR, font=font_large)
    y += 45

    # 游戏列表
    for i, game in enumerate(games_sorted[:display_count], 1):
        game_name = game.get("name", "未知游戏")
        playtime = game.get("playtime_forever", 0)

        # 限制名称长度
        if len(game_name) > 45:
            game_name = game_name[:45] + "..."

        # 背景卡片（仅用于前3名）
        if i <= 3:
            draw.rectangle(
                [(PADDING, y - 5), (WIDTH - PADDING, y + game_item_height - 15)],
                fill=CARD_BG,
                outline=None
            )

        # 排名和游戏名
        rank_color = HIGHLIGHT_COLOR if i <= 3 else TEXT_PRIMARY
        text = f"{i}. {game_name}"
        draw.text((PADDING + 15, y), text, fill=rank_color, font=font_normal)

        # 时长（右对齐）
        time_text = format_playtime(playtime)
        try:
            bbox = draw.textbbox((0, 0), time_text, font=font_normal)
            time_width = bbox[2] - bbox[0]
        except Exception:
            time_width = len(time_text) * 10  # 估算宽度

        draw.text((WIDTH - PADDING - time_width - 15, y), time_text, fill=TEXT_SECONDARY, font=font_normal)

        y += game_item_height

    return pil_image_to_base64(img)


# ==================== 命令处理器 ====================

# 绑定Steam账号
bind_steam = on_command("绑定steam", aliases={"bindsteam"}, priority=5, block=True)


@bind_steam.handle()
async def handle_bind_steam(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """绑定Steam账号"""
    if not steam_api:
        await bind_steam.finish("❌ Steam功能未配置，请联系管理员设置STEAM_API_KEY")

    steam_input = args.extract_plain_text().strip()
    if not steam_input:
        await bind_steam.finish(
            "用法：/绑定steam <Steam ID或个性化URL>\n\n"
            "示例：\n"
            "/绑定steam 76561198012345678 (Steam ID)\n"
            "/绑定steam gaben (个性化URL)\n\n"
            "💡 获取Steam ID方法：\n"
            "1. 访问 https://steamcommunity.com/my/\n"
            "2. 地址栏中的数字就是你的Steam ID\n"
            "3. 或者使用个性化URL（设置 > 编辑个人资料）"
        )

    user_id = str(event.user_id)

    # 获取群组ID (用于新数据结构)
    if isinstance(event, GroupMessageEvent):
        parent_id = str(event.group_id)
    else:
        parent_id = user_id  # 私聊使用用户ID作为parent_id

    # 尝试解析Steam ID
    steam_id = steam_input

    # 如果不是纯数字，尝试作为个性化URL解析
    if not steam_input.isdigit():
        resolved_id = await steam_api.resolve_vanity_url(steam_input)
        if resolved_id:
            steam_id = resolved_id
        else:
            await bind_steam.finish("❌ 无法解析该Steam ID或个性化URL，请检查后重试")

    # 验证Steam ID并获取用户信息
    player_info = await steam_api.get_player_summaries(steam_id)
    if not player_info:
        await bind_steam.finish("❌ 无法获取Steam账号信息，请检查Steam ID是否正确")

    steam_name = player_info.get("personaname", "")

    # 绑定到旧数据库 (保持兼容性)
    await SteamDB.bind_steam(user_id, steam_id, steam_name)

    # 绑定到新数据结构
    bind_info = {
        "user_id": user_id,
        "steam_id": steam_id,
        "nickname": None,  # 默认无昵称
    }

    if bind_data.add(parent_id, bind_info):
        bind_data.save()

    await bind_steam.finish(
        f"✅ 绑定成功！\n\n"
        f"Steam昵称：{steam_name}\n"
        f"Steam ID：{steam_id}\n\n"
        f"现在可以使用以下命令：\n"
        f"/steam资料 - 查看Steam个人资料\n"
        f"/steam游戏 - 查看最近在玩的游戏\n"
        f"/steam游戏库 - 查看游戏库\n"
        f"/steam视奸 - 查看所有好友状态\n"
        f"/steam昵称 <昵称> - 设置显示昵称"
    )


# 解绑Steam账号
unbind_steam = on_command("解绑steam", aliases={"unbindsteam"}, priority=5, block=True)


@unbind_steam.handle()
async def handle_unbind_steam(event: MessageEvent):
    """解绑Steam账号"""
    user_id = str(event.user_id)

    # 获取群组ID
    if isinstance(event, GroupMessageEvent):
        parent_id = str(event.group_id)
    else:
        parent_id = user_id

    # 检查是否已绑定 (检查旧数据库)
    binding = await SteamDB.get_steam_binding(user_id)
    if not binding:
        await unbind_steam.finish("❌ 你还没有绑定Steam账号")

    # 从旧数据库解绑
    await SteamDB.unbind_steam(user_id)

    # 从新数据结构解绑
    bind_data.remove(parent_id, user_id)
    bind_data.save()

    await unbind_steam.finish("✅ 已解绑Steam账号")


# Steam资料查询
steam_profile = on_command("steam资料", aliases={"steam信息", "steamprofile"}, priority=5, block=True)


@steam_profile.handle()
async def handle_steam_profile(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """查询Steam资料"""
    if not steam_api:
        await steam_profile.finish("❌ Steam功能未配置")

    # 获取目标用户
    target_qq = None
    for seg in args:
        if seg.type == "at":
            target_qq = seg.data["qq"]
            break

    if not target_qq:
        target_qq = str(event.user_id)
    else:
        target_qq = str(target_qq)

    # 获取绑定信息
    binding = await SteamDB.get_steam_binding(target_qq)
    if not binding:
        if target_qq == str(event.user_id):
            await steam_profile.finish("❌ 你还没有绑定Steam账号，使用 /绑定steam 进行绑定")
        else:
            await steam_profile.finish("❌ 该用户还没有绑定Steam账号")

    steam_id = binding["steam_id"]

    # 获取QQ用户信息
    qq_user_name = None
    try:
        if isinstance(event, GroupMessageEvent):
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(target_qq))
            qq_user_name = user_info.get("card") or user_info.get("nickname", f"QQ{target_qq}")
        else:
            user_info = await bot.get_stranger_info(user_id=int(target_qq))
            qq_user_name = user_info.get("nickname", f"QQ{target_qq}")
    except Exception:
        qq_user_name = f"QQ{target_qq}"

    # 获取Steam资料
    player_info = await steam_api.get_player_summaries(steam_id)
    if not player_info:
        await steam_profile.finish("❌ 获取Steam资料失败")

    # 获取最近玩的游戏
    recent_games = await steam_api.get_recently_played_games(steam_id, 3)

    # 生成图片（使用新的美化样式）
    try:
        img_base64 = await generate_player_profile_image(player_info, recent_games, qq_user_name)
        await steam_profile.finish(MessageSegment.image(img_base64))
    except FinishedException:
        raise  # 重新抛出FinishedException，这是正常的控制流
    except Exception as e:
        logger.error(f"生成Steam资料图片失败: {e}", exc_info=True)
        # 降级为文本格式
        nickname = player_info.get("personaname", "未知")
        state = get_player_state_text(player_info.get("personastate", 0))
        profile_url = player_info.get("profileurl", "")

        msg = f"🎮 Steam资料\n\nQQ用户: {qq_user_name}\nSteam昵称：{nickname}\n状态：{state}\n主页：{profile_url}"
        await steam_profile.finish(msg)


# Steam最近游戏
steam_recent = on_command("steam游戏", aliases={"最近在玩"}, priority=5, block=True)


@steam_recent.handle()
async def handle_steam_recent(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """查询最近玩的游戏"""
    if not steam_api:
        await steam_recent.finish("❌ Steam功能未配置")

    # 获取目标用户
    target_qq = None
    for seg in args:
        if seg.type == "at":
            target_qq = seg.data["qq"]
            break

    if not target_qq:
        target_qq = str(event.user_id)
    else:
        target_qq = str(target_qq)

    # 获取绑定信息
    binding = await SteamDB.get_steam_binding(target_qq)
    if not binding:
        if target_qq == str(event.user_id):
            await steam_recent.finish("❌ 你还没有绑定Steam账号，使用 /绑定steam 进行绑定")
        else:
            await steam_recent.finish("❌ 该用户还没有绑定Steam账号")

    steam_id = binding["steam_id"]

    # 获取QQ用户信息
    qq_user_name = None
    try:
        if isinstance(event, GroupMessageEvent):
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(target_qq))
            qq_user_name = user_info.get("card") or user_info.get("nickname", f"QQ{target_qq}")
        else:
            user_info = await bot.get_stranger_info(user_id=int(target_qq))
            qq_user_name = user_info.get("nickname", f"QQ{target_qq}")
    except Exception:
        qq_user_name = f"QQ{target_qq}"

    # 获取Steam资料和最近玩的游戏
    player_info = await steam_api.get_player_summaries(steam_id)
    games = await steam_api.get_recently_played_games(steam_id, 10)

    if not games:
        await steam_recent.finish("❌ 该用户最近没有玩游戏或游戏库未公开")

    if not player_info:
        await steam_recent.finish("❌ 获取玩家资料失败")

    # 使用新的游戏列表图片生成器
    try:
        img_base64 = await generate_recent_games_image(player_info, games, qq_user_name)
        await steam_recent.finish(MessageSegment.image(img_base64))
    except FinishedException:
        raise  # 重新抛出FinishedException，这是正常的控制流
    except Exception as e:
        logger.error(f"生成最近游戏图片失败: {e}", exc_info=True)
        # 降级为文本格式
        msg = f"🎮 最近玩的游戏\n\nQQ用户: {qq_user_name}\n\n"
        for i, game in enumerate(games, 1):
            name = game.get("name", "未知游戏")
            playtime_2weeks = game.get("playtime_2weeks", 0)
            playtime_forever = game.get("playtime_forever", 0)
            msg += f"{i}. {name}\n   最近：{format_playtime(playtime_2weeks)} | 总计：{format_playtime(playtime_forever)}\n"

        await steam_recent.finish(msg.strip())


# Steam游戏库
steam_games = on_command("steam游戏库", aliases={"steam库存", "steamgames"}, priority=5, block=True)


@steam_games.handle()
async def handle_steam_games(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """查询游戏库"""
    if not steam_api:
        await steam_games.finish("❌ Steam功能未配置")

    # 获取目标用户
    target_qq = None
    for seg in args:
        if seg.type == "at":
            target_qq = seg.data["qq"]
            break

    if not target_qq:
        target_qq = str(event.user_id)
    else:
        target_qq = str(target_qq)

    # 获取绑定信息
    binding = await SteamDB.get_steam_binding(target_qq)
    if not binding:
        if target_qq == str(event.user_id):
            await steam_games.finish("❌ 你还没有绑定Steam账号，使用 /绑定steam 进行绑定")
        else:
            await steam_games.finish("❌ 该用户还没有绑定Steam账号")

    steam_id = binding["steam_id"]

    # 获取QQ用户信息
    qq_user_name = None
    try:
        if isinstance(event, GroupMessageEvent):
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(target_qq))
            qq_user_name = user_info.get("card") or user_info.get("nickname", f"QQ{target_qq}")
        else:
            user_info = await bot.get_stranger_info(user_id=int(target_qq))
            qq_user_name = user_info.get("nickname", f"QQ{target_qq}")
    except Exception:
        qq_user_name = f"QQ{target_qq}"

    # 获取游戏库
    games = await steam_api.get_owned_games(steam_id, include_appinfo=True)
    if not games:
        await steam_games.finish("❌ 该用户游戏库未公开或为空")

    # 生成图片（使用新的美化样式）
    try:
        img_base64 = await generate_game_library_image(games, qq_user_name)
        await steam_games.finish(MessageSegment.image(img_base64))
    except FinishedException:
        raise  # 重新抛出FinishedException，这是正常的控制流
    except Exception as e:
        logger.error(f"生成游戏库图片失败: {e}", exc_info=True)
        # 降级为文本格式
        total_games = len(games)
        total_playtime = sum(game.get("playtime_forever", 0) for game in games)
        games_sorted = sorted(games, key=lambda x: x.get("playtime_forever", 0), reverse=True)

        msg = f"📚 Steam游戏库\n\nQQ用户: {qq_user_name}\n游戏总数：{total_games} 款\n总游戏时长：{format_playtime(total_playtime)}\n\n🏆 TOP 10:\n"
        for i, game in enumerate(games_sorted[:10], 1):
            name = game.get("name", "未知游戏")
            playtime = game.get("playtime_forever", 0)
            msg += f"{i}. {name} - {format_playtime(playtime)}\n"

        await steam_games.finish(msg.strip())


# Steam视奸 (使用新的draw_friends_status)
steam_spy = on_command("steam视奸", aliases={"视奸", "steam好友", "查看在线"}, priority=5, block=True)


@steam_spy.handle()
async def handle_steam_spy(bot: Bot, event: MessageEvent):
    """查看所有绑定用户的Steam状态"""
    if not steam_api:
        await steam_spy.finish("❌ Steam功能未配置")

    # 获取群组ID
    if isinstance(event, GroupMessageEvent):
        parent_id = str(event.group_id)
    else:
        parent_id = str(event.user_id)

    # 获取现有绑定信息
    parent_bindings = bind_data.content.get(parent_id, [])
    steam_ids: List[str] = []
    steam_id_set = set()
    nickname_map: Dict[str, Optional[str]] = {}
    for record in parent_bindings:
        steam_id = record.get("steam_id")
        if not steam_id:
            continue
        steam_ids.append(steam_id)
        steam_id_set.add(steam_id)
        if record.get("nickname"):
            nickname_map[steam_id] = record.get("nickname")

    # 需要同步的QQ用户列表（当前群成员 or 私聊对象）
    user_ids_to_sync: List[str] = []
    if isinstance(event, GroupMessageEvent):
        try:
            members = await bot.get_group_member_list(group_id=event.group_id)
            user_ids_to_sync = [str(m["user_id"]) for m in members]
        except Exception as exc:
            logger.warning(f"获取群成员列表失败: {exc}")
            user_ids_to_sync = []
    else:
        user_ids_to_sync = [str(event.user_id)]

    # 始终确保触发指令的用户也在同步列表中
    trigger_user = str(event.user_id)
    if trigger_user not in user_ids_to_sync:
        user_ids_to_sync.append(trigger_user)

    unique_user_ids = list(dict.fromkeys(user_ids_to_sync))

    # 从数据库补齐绑定信息，避免旧数据缺失
    bind_changed = False
    bindings_map = await SteamDB.get_bindings_by_users(unique_user_ids)
    for user_id, binding in bindings_map.items():
        steam_id = binding.get("steam_id")
        if not steam_id:
            continue
        if steam_id not in steam_id_set:
            steam_ids.append(steam_id)
            steam_id_set.add(steam_id)

        existing = bind_data.get(parent_id, user_id)
        nickname = existing.get("nickname") if existing else None
        if nickname:
            nickname_map[steam_id] = nickname

        if bind_data.add(
            parent_id,
            {
                "user_id": user_id,
                "steam_id": steam_id,
                "nickname": nickname,
            },
        ):
            bind_changed = True

    if bind_changed:
        bind_data.save()

    if not steam_ids:
        await steam_spy.finish("❌ 还没有人绑定Steam账号")

    # 批量获取玩家信息
    players_info = await steam_api.get_multiple_player_summaries(steam_ids)

    if not players_info:
        await steam_spy.finish("❌ 获取Steam状态失败，请稍后重试")

    # 按状态排序：游戏中 > 在线 > 离线
    def get_sort_key(player):
        if player.get("gameextrainfo"):
            return 0  # 游戏中
        elif player.get("personastate", 0) > 0:
            return 1  # 在线
        else:
            return 2  # 离线

    players_info_sorted = sorted(players_info, key=get_sort_key)

    # 转换数据为 Steam 风格函数所需格式
    steam_data = []
    for player in players_info_sorted:
        steam_id = player.get("steamid", "")
        try:
            avatar = await fetch_avatar(player, avatar_cache_dir)
        except Exception as e:
            logger.error(f"获取头像失败 {steam_id}: {e}")
            avatar = Image.new("RGB", (50, 50), (100, 100, 100))

        # 确定状态文本
        personastate = player.get("personastate", 0)
        game_info = player.get("gameextrainfo")
        if personastate == 0:
            lastlogoff = player.get("lastlogoff", 0)
            if lastlogoff > 0:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc).timestamp()
                offline_seconds = int(now - lastlogoff)
                if offline_seconds < 3600:
                    status = f"上次在线 {offline_seconds // 60} 分钟前"
                elif offline_seconds < 86400:
                    status = f"上次在线 {offline_seconds // 3600} 小时前"
                else:
                    status = f"上次在线 {offline_seconds // 86400} 天前"
            else:
                status = "离线"
        elif game_info:
            status = game_info
        elif personastate == 3:
            status = "离开"
        else:
            status = "在线"

        steam_data.append(
            {
                "avatar": avatar,
                "name": player.get("personaname", "Unknown"),
                "status": status,
                "personastate": personastate,
                "nickname": nickname_map.get(steam_id),
            }
        )

    # 获取群头像作为 "parent"（头部显示）
    if isinstance(event, GroupMessageEvent):
        try:
            parent_avatar = await fetch_qq_group_avatar(str(event.group_id), 640)
            parent_name = f"Steam 好友 ({len(steam_data)}人)"
        except Exception as e:
            logger.warning(f"获取群头像失败: {e}")
            parent_avatar = Image.new("RGB", (72, 72), (100, 100, 100))
            parent_name = f"Steam 好友 ({len(steam_data)}人)"
    else:
        # 私聊场景，使用默认头像或第一个用户头像
        if steam_data:
            parent_avatar = steam_data[0]["avatar"]
        else:
            parent_avatar = Image.new("RGB", (72, 72), (100, 100, 100))
        parent_name = f"Steam 好友 ({len(steam_data)}人)"

    # 使用 Steam 风格函数生成图片
    try:
        friends_image = draw_friends_status_steam(parent_avatar, parent_name, steam_data)
        img_base64 = pil_image_to_base64(friends_image)
        await steam_spy.finish(MessageSegment.image(img_base64))
    except FinishedException:
        raise  # 重新抛出FinishedException，这是正常的控制流
    except Exception as e:
        logger.error(f"生成Steam好友列表图片失败: {e}")
        # 降级为文本格式
        msg = f"🎮 Steam在线状态 ({len(players_info)}人)\n\n"
        for player in players_info_sorted:
            name = player.get("personaname", "未知")
            state = player.get("personastate", 0)
            game = player.get("gameextrainfo", None)

            if game:
                msg += f"🎮 {name}\n   游戏中: {game}\n\n"
            elif state > 0:
                msg += f"🟢 {name}\n   在线\n\n"
            else:
                msg += f"⚫ {name}\n   离线\n\n"

        await steam_spy.finish(msg.strip())


# 设置Steam昵称
steam_nickname = on_command("steam昵称", priority=5, block=True)


@steam_nickname.handle()
async def handle_steam_nickname(event: MessageEvent, args: Message = CommandArg()):
    """设置Steam显示昵称"""
    nickname = args.extract_plain_text().strip()

    if not nickname:
        await steam_nickname.finish("用法：/steam昵称 <昵称>\n\n设置后，在群内Steam相关功能中将显示该昵称而非Steam昵称")

    user_id = str(event.user_id)

    # 获取群组ID
    if isinstance(event, GroupMessageEvent):
        parent_id = str(event.group_id)
    else:
        parent_id = user_id

    # 检查是否已绑定
    bind_info = bind_data.get(parent_id, user_id)
    if not bind_info:
        await steam_nickname.finish("❌ 你还没有绑定Steam账号，请先使用 /绑定steam 进行绑定")

    # 更新昵称
    bind_info["nickname"] = nickname
    if bind_data.add(parent_id, bind_info):
        bind_data.save()

    await steam_nickname.finish(f"✅ 已设置Steam显示昵称为：{nickname}")


# 启用播报
steam_enable_broadcast = on_command("steam启用播报", priority=5, block=True)


@steam_enable_broadcast.handle()
async def handle_enable_broadcast(event: MessageEvent):
    """在当前群启用游戏状态播报"""
    if not isinstance(event, GroupMessageEvent):
        await steam_enable_broadcast.finish("❌ 该命令只能在群聊中使用")

    if not HAS_APSCHEDULER:
        await steam_enable_broadcast.finish(
            "❌ 自动播报功能未启用\n\n"
            "原因：未安装 nonebot-plugin-apscheduler\n"
            "安装方法：pip install nonebot-plugin-apscheduler"
        )

    parent_id = str(event.group_id)

    # 检查是否已禁用
    if not disable_parent_data.is_disabled(parent_id):
        await steam_enable_broadcast.finish("✅ 当前群已启用播报")

    # 从禁用列表中移除
    disable_parent_data.remove(parent_id)
    disable_parent_data.save()

    await steam_enable_broadcast.finish("✅ 已启用Steam游戏状态播报\n\n当群内好友开始/切换/停止游戏时，将自动发送通知")


# 禁用播报
steam_disable_broadcast = on_command("steam禁用播报", priority=5, block=True)


@steam_disable_broadcast.handle()
async def handle_disable_broadcast(event: MessageEvent):
    """在当前群禁用游戏状态播报"""
    if not HAS_APSCHEDULER:
        await steam_disable_broadcast.finish(
            "❌ 自动播报功能未启用\n\n"
            "原因：未安装 nonebot-plugin-apscheduler\n"
            "（该功能当前不可用）"
        )
    if not isinstance(event, GroupMessageEvent):
        await steam_disable_broadcast.finish("❌ 该命令只能在群聊中使用")

    parent_id = str(event.group_id)

    # 检查是否已禁用
    if disable_parent_data.is_disabled(parent_id):
        await steam_disable_broadcast.finish("✅ 当前群已禁用播报")

    # 添加到禁用列表
    disable_parent_data.add(parent_id)
    disable_parent_data.save()

    await steam_disable_broadcast.finish("✅ 已禁用Steam游戏状态播报")


# Steam价格查询
steam_price_query = on_command(
    "steam价格", aliases={"steam价", "游戏价格", "steam查价"}, priority=5, block=True
)

# 喜加一与订阅
steam_freebie = on_command("steam喜加一", aliases={"喜加一"}, priority=5, block=True)
steam_freebie_subscribe = on_command("steam喜加一订阅", aliases={"喜加一订阅"}, priority=5, block=True)
steam_freebie_unsubscribe = on_command("steam喜加一退订", aliases={"喜加一取消订阅"}, priority=5, block=True)
steam_discount_subscribe = on_command("steam折扣订阅", aliases={"折扣订阅"}, priority=5, block=True)
steam_discount_unsubscribe = on_command("steam折扣退订", aliases={"折扣取消订阅"}, priority=5, block=True)


def _format_price_with_currency(value: float, currency: str) -> str:
    symbols = {
        "CNY": "¥",
        "USD": "$",
        "EUR": "€",
        "JPY": "¥",
        "UAH": "₴",
    }
    symbol = symbols.get(currency.upper(), f"{currency} ")
    return f"{symbol}{value:.2f}"


@steam_price_query.handle()
async def handle_steam_price(args: Message = CommandArg()):
    """查询Steam游戏价格、史低、折扣等信息"""
    if not steam_store_api:
        await steam_price_query.finish("❌ Steam商店功能未初始化")

    raw_text = args.extract_plain_text().strip()
    if not raw_text:
        await steam_price_query.finish("❌ 请提供要查询的游戏名称")

    game_name = raw_text
    regions = STEAM_PRICE_COMPARE_REGIONS

    if "|" in raw_text:
        name_part, region_part = raw_text.split("|", 1)
        game_name = name_part.strip()
        custom_regions = [r.strip() for r in re.split(r"[,\s]+", region_part) if r.strip()]
        if custom_regions:
            regions = custom_regions

    # 搜索游戏
    search_result = await steam_store_api.search_game(game_name)
    if not search_result:
        await steam_price_query.finish("❌ 未找到相关游戏，请检查名称后重试")

    appid = search_result.get("appid")
    english_name = search_result.get("english_name") or search_result.get("name")

    # 获取价格信息
    price_info = await steam_store_api.get_game_price_info(
        appid, regions=regions, exchange_rates=STEAM_PRICE_EXCHANGE_RATES, english_name=english_name
    )

    if not price_info:
        await steam_price_query.finish("❌ 未能获取该游戏的价格信息")

    # 准备渲染数据
    game_name_cn = price_info.get("name") or english_name or game_name
    game_name_en = price_info.get("english_name") or english_name
    image_url = price_info.get("image") or search_result.get("image")

    # 下载游戏头图
    header_image_bytes = None
    if image_url:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                header_image_bytes = await fetch_image_bytes(image_url, client)
        except Exception as e:
            logger.warning(f"下载游戏头图失败: {e}")

    # 渲染价格信息图片
    try:
        img = draw_game_price_info(
            game_name=game_name_cn,
            english_name=game_name_en,
            appid=appid,
            header_image=header_image_bytes,
            prices=price_info.get("prices", []),
            historical_low=price_info.get("historical_low"),
            historical_low_currency=price_info.get("historical_low_currency", "CNY"),
            historical_low_date=price_info.get("historical_low_date")
        )
        await steam_price_query.finish(MessageSegment.image(pil_image_to_base64(img)))
    except FinishedException:
        # finish异常直接向上传播
        raise
    except Exception as e:
        logger.error(f"渲染价格图片失败: {e}", exc_info=True)
        # 降级到文本模式
        message_lines = [f"🎮 {game_name_cn}", f"🔗 https://store.steampowered.com/app/{appid}"]
        if game_name_en and game_name_en != game_name_cn:
            message_lines.append(f"英文名: {game_name_en}")
        message_lines.append("\n当前价格：")
        for price in price_info.get("prices", []):
            line = f"- {price['region'].upper()}: "
            line += _format_price_with_currency(price["price"], price["currency"])
            if price.get("discount", 0):
                line += f" (-{price['discount']}%)"
            if price.get("converted_price") is not None and price["currency"].upper() != "CNY":
                line += f" ≈ ¥{price['converted_price']:.2f}"
            if price.get("original_price") and price.get("discount", 0):
                line += f" (原价 {_format_price_with_currency(price['original_price'], price['currency'])})"
            message_lines.append(line)

        historical_low = price_info.get("historical_low")
        if historical_low is not None:
            low_currency = price_info.get("historical_low_currency", "CNY").upper()
            low_date = price_info.get("historical_low_date")
            low_text = _format_price_with_currency(float(historical_low), low_currency)
            if low_currency != "CNY" and low_currency in STEAM_PRICE_EXCHANGE_RATES:
                low_text += f" (约¥{float(historical_low) * float(STEAM_PRICE_EXCHANGE_RATES[low_currency]):.2f})"
            if low_date:
                low_text += f"，记录时间 {low_date}"
            message_lines.append(f"\n📉 史低价：{low_text}")
        await steam_price_query.finish("\n".join(message_lines))


@steam_freebie.handle()
async def handle_steam_freebie():
    """查询当前喜加一"""
    if not steam_store_api:
        await steam_freebie.finish("❌ Steam商店功能未初始化")

    await steam_freebie.send("🔍 正在查询限时免费游戏，请稍候...")

    try:
        games = await steam_store_api.get_free_games(limit=6)
        if not games:
            await steam_freebie.finish("暂时没有可以白嫖的游戏~")

        render_games: List[Dict] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for game in games:
                image_bytes = await fetch_image_bytes(game.get("image"), client)
                render_games.append(
                    {
                        "name": game.get("name", "未知游戏"),
                        "image": image_bytes,
                        "tags": ["限时免费"],
                        "info": "￥0.00",
                        "extra": f"折扣 -{game.get('discount_percent', 0)}%",
                        "badge": "FREE",
                    }
                )

        title = "🎁 Steam 喜加一"
        img = draw_game_list_with_tags(title, render_games, subtitle="限时领取，记得入库！")
        await steam_freebie.finish(MessageSegment.image(pil_image_to_base64(img)))
    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"查询喜加一失败: {e}", exc_info=True)
        await steam_freebie.finish("❌ 查询失败，请稍后再试")


def _ensure_group(event: MessageEvent) -> Optional[str]:
    if isinstance(event, GroupMessageEvent):
        return str(event.group_id)
    return None


@steam_freebie_subscribe.handle()
async def handle_freebie_subscribe(event: MessageEvent):
    parent_id = _ensure_group(event)
    if not parent_id:
        await steam_freebie_subscribe.finish("❌ 该命令只能在群聊中使用")

    subscription_data.add(parent_id, "freebie")
    await steam_freebie_subscribe.finish("✅ 已订阅喜加一推送")


@steam_freebie_unsubscribe.handle()
async def handle_freebie_unsubscribe(event: MessageEvent):
    parent_id = _ensure_group(event)
    if not parent_id:
        await steam_freebie_unsubscribe.finish("❌ 该命令只能在群聊中使用")

    subscription_data.remove(parent_id, "freebie")
    await steam_freebie_unsubscribe.finish("✅ 已取消喜加一推送")


@steam_discount_subscribe.handle()
async def handle_discount_subscribe(event: MessageEvent):
    parent_id = _ensure_group(event)
    if not parent_id:
        await steam_discount_subscribe.finish("❌ 该命令只能在群聊中使用")

    subscription_data.add(parent_id, "discount")
    await steam_discount_subscribe.finish("✅ 已订阅高折扣推送")


@steam_discount_unsubscribe.handle()
async def handle_discount_unsubscribe(event: MessageEvent):
    parent_id = _ensure_group(event)
    if not parent_id:
        await steam_discount_unsubscribe.finish("❌ 该命令只能在群聊中使用")

    subscription_data.remove(parent_id, "discount")
    await steam_discount_unsubscribe.finish("✅ 已取消高折扣推送")


# Steam史低游戏查询
steam_historical_low = on_command("steam史低", aliases={"史低游戏", "史低"}, priority=5, block=True)


@steam_historical_low.handle()
async def handle_steam_historical_low(event: MessageEvent, args: Message = CommandArg()):
    """查询史低游戏"""
    if not steam_store_api:
        await steam_historical_low.finish("❌ Steam商店功能未初始化")

    tag = args.extract_plain_text().strip()

    # 发送提示
    if tag:
        await steam_historical_low.send(f"🔍 正在查询 '{tag}' 类型的史低游戏，请稍候...")
    else:
        await steam_historical_low.send("🔍 正在查询热门史低游戏，请稍候...")

    try:
        # 查询史低游戏
        games = await steam_store_api.find_historical_low_deals(
            limit=10,
            tags=tag if tag else None
        )

        if not games:
            if tag:
                await steam_historical_low.finish(f"❌ 未找到 '{tag}' 类型的史低游戏")
            else:
                await steam_historical_low.finish("❌ 未找到史低游戏，请稍后再试")

        subtitle = ""
        sale_info = await steam_store_api.get_steam_specials_info()
        if sale_info and sale_info.get("is_active"):
            subtitle = f"{sale_info['name']}进行中，剩余 {sale_info['days_left']} 天"

        render_games: List[Dict] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for game in games:
                image_bytes = await fetch_image_bytes(game.get("image"), client)
                info_text = f"¥{game['current_price']:.2f} (-{game['discount_percent']}%)"
                extra_text = ""
                if game.get("original_price"):
                    extra_text = f"原价 ¥{game['original_price']:.2f}"
                render_games.append(
                    {
                        "name": game.get("name", "未知游戏"),
                        "image": image_bytes,
                        "tags": game.get("tags", []) or [],
                        "info": info_text,
                        "extra": extra_text,
                        "badge": "史低" if game.get("is_historical_low") else None,
                    }
                )

        title = "💰 Steam 史低游戏推荐" if not tag else f"💰 {tag} 类史低游戏推荐"
        img = draw_game_list_with_tags(title, render_games, subtitle=subtitle)
        await steam_historical_low.finish(MessageSegment.image(pil_image_to_base64(img)))

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"查询史低游戏失败: {e}", exc_info=True)
        await steam_historical_low.finish("❌ 查询失败，请稍后再试")


# Steam榜单
steam_charts = on_command("steam榜单", aliases={"steam排行", "热销榜"}, priority=5, block=True)


@steam_charts.handle()
async def handle_steam_charts():
    """查询Steam热销榜"""
    if not steam_store_api:
        await steam_charts.finish("❌ Steam商店功能未初始化")

    await steam_charts.send("🔍 正在获取Steam热销榜，请稍候...")

    try:
        # 获取热销榜
        games = await steam_store_api.get_top_sellers(limit=15)

        if not games:
            await steam_charts.finish("❌ 获取热销榜失败，请稍后再试")

        sale_info = await steam_store_api.get_steam_specials_info()
        subtitle = ""
        if sale_info:
            if sale_info.get("is_active"):
                subtitle = f"{sale_info['name']}进行中，剩余 {sale_info['days_left']} 天"
            elif sale_info.get("days_until"):
                subtitle = f"{sale_info['name']}将在 {sale_info['days_until']} 天后开始"

        render_games: List[Dict] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for rank, game in enumerate(games, 1):
                image_bytes = await fetch_image_bytes(game.get("image"), client)
                price = game.get("price", 0)
                discount = game.get("discount", 0)
                if discount > 0:
                    info_text = f"¥{price:.2f} (-{discount}%)"
                elif price > 0:
                    info_text = f"¥{price:.2f}"
                else:
                    info_text = "免费游戏"

                render_games.append(
                    {
                        "name": game.get("name", "未知游戏"),
                        "image": image_bytes,
                        "tags": game.get("tags", []) or [],
                        "info": info_text,
                        "extra": f"appid: {game.get('appid', '')}",
                        "badge": "TOP" if rank <= 3 else None,
                    }
                )

        title = "🏆 Steam 全球热销榜 TOP 15"
        img = draw_game_list_with_tags(title, render_games, subtitle=subtitle)
        await steam_charts.finish(MessageSegment.image(pil_image_to_base64(img)))

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"获取热销榜失败: {e}", exc_info=True)
        await steam_charts.finish("❌ 获取失败，请稍后再试")


# Steam促销信息
steam_sales = on_command("steam促销", aliases={"steam特卖", "steam折扣"}, priority=5, block=True)


@steam_sales.handle()
async def handle_steam_sales():
    """查询当前Steam促销信息"""
    if not steam_store_api:
        await steam_sales.finish("❌ Steam商店功能未初始化")

    try:
        sale_info = await steam_store_api.get_steam_specials_info()

        if not sale_info:
            msg = "📢 当前没有进行中的Steam大型促销活动\n\n"
            msg += "Steam主要促销活动时间参考：\n"
            msg += "🌸 春季特卖：3月中下旬\n"
            msg += "☀️ 夏季特卖：6月下旬\n"
            msg += "🍂 秋季特卖：10月底-11月初\n"
            msg += "❄️ 冬季特卖：12月下旬-1月初"
            await steam_sales.finish(msg)

        if sale_info.get("is_active"):
            msg = f"🎉 {sale_info['name']}正在进行中！\n\n"
            msg += f"📅 活动时间：{sale_info['start_date']} 至 {sale_info['end_date']}\n"
            msg += f"⏰ 还剩 {sale_info['days_left']} 天\n\n"
            msg += "💡 使用 /steam史低 查看史低游戏推荐\n"
            msg += "💡 使用 /steam榜单 查看热销榜单"
        else:
            msg = f"📅 {sale_info['name']}即将开始！\n\n"
            msg += f"📅 活动时间：{sale_info['start_date']} 至 {sale_info['end_date']}\n"
            msg += f"⏰ 还有 {sale_info['days_until']} 天开始"

        await steam_sales.finish(msg)

    except FinishedException:
        raise
    except Exception as e:
        logger.error(f"查询促销信息失败: {e}", exc_info=True)
        await steam_sales.finish("❌ 查询失败，请稍后再试")


# Steam帮助
steam_help = on_command("steam帮助", aliases={"steamhelp"}, priority=5, block=True)


@steam_help.handle()
async def handle_steam_help(bot: Bot, event: MessageEvent):
    """显示Steam插件帮助（群聊使用聊天记录格式）"""
    help_text = """🎮 Steam插件帮助

【账号管理】
/绑定steam <ID> - 绑定Steam账号（支持Steam ID或个性化URL）
/解绑steam - 解绑Steam账号
/steam昵称 <昵称> - 设置显示昵称

【查询功能】
/steam资料 [@用户] - 查看Steam资料
/steam游戏 [@用户] - 查看最近游戏
/steam游戏库 [@用户] - 查看完整游戏库
/steam视奸 - 查看所有好友在线状态

【商店功能】
/steam价格 <游戏名> [| 对比区列表] - 查询国区价格、各区折扣&史低，自动翻译英文名
  示例：/steam价格 艾尔登法环 | us jp
/steam史低 - 查看热门史低游戏
/steam史低 <类型> - 查看特定类型的史低游戏
  示例：/steam史低 类银河恶魔城
/steam榜单 - 查看Steam全球热销榜
/steam促销 - 查看当前促销活动信息
/steam喜加一 - 查看限时免费游戏
/steam喜加一订阅 / steam喜加一退订 - 管理喜加一推送
/steam折扣订阅 / steam折扣退订 - 管理高折扣推送

【播报功能】
/steam启用播报 - 启用游戏状态播报
/steam禁用播报 - 禁用游戏状态播报

启用播报后：
- 好友开始玩游戏时会自动通知
- Steam大型促销活动时会自动推送

💡 提示：
1. 绑定前需确保Steam资料为公开
2. 游戏库需设置为公开才能查看
3. 播报功能仅在群聊中生效
4. 史低功能需要ITAD API密钥支持"""

    # 群聊/私聊统一使用合并转发格式（聊天记录）
    bot_id = event.self_id
    bot_info = await bot.get_stranger_info(user_id=bot_id)
    bot_name = bot_info.get("nickname", "SteamBot")

    sections = [
        ("🎮 Steam插件帮助", "欢迎使用 Steam 功能！以下是所有可用命令："),
        (
            "【账号管理】",
            "/绑定steam <ID> - 绑定Steam账号（支持Steam ID或个性化URL)\n"
            "/解绑steam - 解绑Steam账号\n"
            "/steam昵称 <昵称> - 设置显示昵称",
        ),
        (
            "【查询功能】",
            "/steam资料 [@用户] - 查看Steam资料\n"
            "/steam游戏 [@用户] - 查看最近游戏\n"
            "/steam游戏库 [@用户] - 查看完整游戏库\n"
            "/steam视奸 - 查看所有好友在线状态",
        ),
        (
            "【商店功能】",
            "/steam价格 <游戏名> [| 对比区列表] - 查询国区价格、各区折扣&史低，自动翻译英文名\n"
            "  示例：/steam价格 艾尔登法环 | us jp\n"
            "/steam史低 - 查看热门史低游戏\n"
            "/steam史低 <类型> - 查看特定类型的史低游戏\n"
            "  示例：/steam史低 类银河恶魔城\n"
            "/steam榜单 - 查看Steam全球热销榜\n"
            "/steam促销 - 查看当前促销活动信息\n"
            "/steam喜加一 - 查看限时免费游戏\n"
            "/steam喜加一订阅 / steam喜加一退订 - 管理喜加一推送\n"
            "/steam折扣订阅 / steam折扣退订 - 管理高折扣推送",
        ),
        (
            "【播报功能】",
            "/steam启用播报 - 启用游戏状态播报\n"
            "/steam禁用播报 - 禁用游戏状态播报\n\n"
            "启用播报后：\n- 好友开始玩游戏时会自动通知\n- Steam大型促销活动时会自动推送",
        ),
        (
            "💡 提示",
            "1. 绑定前需确保Steam资料为公开\n"
            "2. 游戏库需设置为公开才能查看\n"
            "3. 播报功能仅在群聊中生效\n"
            "4. 史低功能需要ITAD API密钥支持",
        ),
    ]

    nodes = [
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content=f"{title}\n{content}",
        )
        for title, content in sections
    ]

    try:
        if isinstance(event, GroupMessageEvent):
            await bot.send_group_forward_msg(group_id=event.group_id, messages=nodes)
        else:
            await bot.send_private_forward_msg(user_id=event.user_id, messages=nodes)
        await steam_help.finish()
    except Exception:
        # 兼容性兜底：若转发失败则发送纯文本帮助
        await steam_help.finish(help_text)


# ==================== 自动播报系统 ====================

async def check_steam_status():
    """定期检查Steam状态变化并播报"""
    if not steam_api or not STEAM_BROADCAST_ENABLED:
        return

    try:
        # 获取所有Steam ID
        all_steam_ids = bind_data.get_all_steam_id()

        if not all_steam_ids:
            return

        # 获取最新玩家信息
        new_players = await steam_api.get_multiple_player_summaries(all_steam_ids)

        if not new_players:
            return

        # 获取旧的玩家信息
        old_players = steam_info_data.content

        # 比较状态变化
        changes = steam_info_data.compare(old_players, new_players)

        # 更新缓存
        steam_info_data.update_by_players(new_players)
        steam_info_data.save()

        # 处理每个变化
        for change in changes:
            change_type = change["type"]
            player = change["player"]

            if change_type == "start":
                # 用户开始游戏
                await broadcast_start_gaming(player)
            # 可以添加更多类型的通知
            # elif change_type == "stop":
            #     await broadcast_stop_gaming(player)
            # elif change_type == "change":
            #     await broadcast_change_game(player, change["old_player"])

    except Exception as e:
        logger.error(f"检查Steam状态失败: {e}")

# Steam促销检测
_last_sale_notification = None  # 记录上次通知的促销活动
_last_freebie_ids: set[str] = set()
_last_discount_ids: set[str] = set()


async def check_steam_sales():
    """定期检查Steam促销活动并推送"""
    global _last_sale_notification

    if not steam_store_api:
        return

    try:
        sale_info = await steam_store_api.get_steam_specials_info()

        if not sale_info:
            return

        # 生成通知标识符
        sale_id = f"{sale_info.get('name')}_{sale_info.get('start_date')}"

        # 检查是否已经通知过
        if _last_sale_notification == sale_id:
            return

        # 获取Bot实例
        from nonebot import get_bot
        try:
            bot = get_bot()
        except Exception:
            logger.warning("无法获取Bot实例，跳过促销推送")
            return

        # 构建消息
        if sale_info.get("is_active"):
            msg = f"🎉 【Steam促销通知】\n\n"
            msg += f"{sale_info['name']}正在进行中！\n"
            msg += f"📅 活动时间：{sale_info['start_date']} 至 {sale_info['end_date']}\n"
            msg += f"⏰ 还剩 {sale_info['days_left']} 天\n\n"
            msg += "💡 使用 /steam史低 查看史低游戏推荐\n"
            msg += "💡 使用 /steam榜单 查看热销榜单"
        else:
            # 即将开始的促销（7天内）
            msg = f"📢 【Steam促销预告】\n\n"
            msg += f"{sale_info['name']}即将开始！\n"
            msg += f"📅 活动时间：{sale_info['start_date']} 至 {sale_info['end_date']}\n"
            msg += f"⏰ 还有 {sale_info['days_until']} 天开始\n\n"
            msg += "记得提前准备好你的愿望单哦！"

        # 推送到所有启用播报的群组
        for parent_id in bind_data.content.keys():
            # 只推送到群组
            if not parent_id.isdigit() or len(parent_id) < 6:
                continue

            # 检查群是否禁用播报
            if disable_parent_data.is_disabled(parent_id):
                continue

            try:
                await bot.send_group_msg(group_id=int(parent_id), message=msg)
                logger.info(f"已向群组 {parent_id} 推送Steam促销信息")
            except Exception as e:
                logger.warning(f"向群组 {parent_id} 推送促销信息失败: {e}")

        # 更新最后通知记录
        _last_sale_notification = sale_id
        logger.info(f"Steam促销通知已推送: {sale_id}")

    except Exception as e:
        logger.error(f"检查Steam促销失败: {e}")


async def check_steam_freebies():
    """定期推送喜加一"""
    global _last_freebie_ids

    if not steam_store_api:
        return

    groups = subscription_data.get("freebie")
    if not groups:
        return

    try:
        games = await steam_store_api.get_free_games(limit=6)
        if not games:
            return

        new_ids = {str(g.get("id")) for g in games if g.get("id")}
        if new_ids and new_ids == _last_freebie_ids:
            return

        render_games: List[Dict] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for game in games:
                image_bytes = await fetch_image_bytes(game.get("image"), client)
                render_games.append(
                    {
                        "name": game.get("name", "未知游戏"),
                        "image": image_bytes,
                        "tags": ["限时免费"],
                        "info": "￥0.00",
                        "extra": f"折扣 -{game.get('discount_percent', 0)}%",
                        "badge": "FREE",
                    }
                )

        img = draw_game_list_with_tags("🎁 Steam 喜加一", render_games, subtitle="本期免费领取列表")
        image_msg = MessageSegment.image(pil_image_to_base64(img))

        from nonebot import get_bot
        bot = get_bot()

        for gid in groups:
            if not gid.isdigit() or disable_parent_data.is_disabled(gid):
                continue
            try:
                await bot.send_group_msg(group_id=int(gid), message=image_msg)
            except Exception:
                logger.debug("发送喜加一推送失败", exc_info=True)

        _last_freebie_ids = new_ids
    except Exception as e:
        logger.error(f"推送喜加一失败: {e}", exc_info=True)


async def check_steam_discounts():
    """定期推送高折扣游戏"""
    global _last_discount_ids

    if not steam_store_api:
        return

    groups = subscription_data.get("discount")
    if not groups:
        return

    try:
        games = await steam_store_api.get_discount_recommendations(limit=6, min_discount=60)
        if not games:
            return

        new_ids = {str(g.get("appid")) for g in games if g.get("appid")}
        if new_ids and new_ids == _last_discount_ids:
            return

        render_games: List[Dict] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for game in games:
                image_bytes = await fetch_image_bytes(game.get("image"), client)
                price_text = f"¥{game.get('price', 0):.2f}" if game.get("price") else "免费"
                if game.get("discount", 0):
                    price_text += f" (-{game.get('discount')}%)"
                extra = ""
                if game.get("original_price"):
                    extra = f"原价 ¥{game['original_price']:.2f}"
                render_games.append(
                    {
                        "name": game.get("name", "未知游戏"),
                        "image": image_bytes,
                        "tags": game.get("tags", []) or [],
                        "info": price_text,
                        "extra": extra,
                        "badge": "折扣",
                    }
                )

        img = draw_game_list_with_tags("💰 Steam 高折扣推荐", render_games, subtitle="每日精选折扣")
        image_msg = MessageSegment.image(pil_image_to_base64(img))

        from nonebot import get_bot
        bot = get_bot()

        for gid in groups:
            if not gid.isdigit() or disable_parent_data.is_disabled(gid):
                continue
            try:
                await bot.send_group_msg(group_id=int(gid), message=image_msg)
            except Exception:
                logger.debug("发送折扣推送失败", exc_info=True)

        _last_discount_ids = new_ids
    except Exception as e:
        logger.error(f"推送折扣推荐失败: {e}", exc_info=True)


# 只在apscheduler可用时注册定时任务
if HAS_APSCHEDULER and scheduler:
    scheduler.scheduled_job("interval", seconds=STEAM_BROADCAST_INTERVAL, id="steam_status_check")(check_steam_status)
    logger.info(f"Steam状态检查任务已注册，间隔: {STEAM_BROADCAST_INTERVAL}秒")

    # 每天上午10点检查Steam促销
    scheduler.scheduled_job("cron", hour=10, minute=0, id="steam_sales_check")(check_steam_sales)
    logger.info("Steam促销检查任务已注册，每天10:00执行")

    # 喜加一与折扣推送
    scheduler.scheduled_job("cron", hour=12, minute=0, id="steam_freebie_check")(check_steam_freebies)
    scheduler.scheduled_job("cron", hour=18, minute=0, id="steam_discount_check")(check_steam_discounts)
    logger.info("喜加一与折扣推送任务已注册，分别在每日12:00与18:00执行")


async def broadcast_start_gaming(player: Dict):
    """
    播报用户开始游戏

    Args:
        player: 玩家信息
    """
    try:
        steam_id = player.get("steamid", "")
        game_name = player.get("gameextrainfo", "")
        player_name = player.get("personaname", "Unknown")

        if not game_name:
            return

        # 获取头像
        avatar = await fetch_avatar(player, avatar_cache_dir)

        # 生成通知图片
        notification_image = draw_start_gaming(player_name, game_name, avatar)
        img_base64 = pil_image_to_base64(notification_image)

        # 获取Bot实例
        from nonebot import get_bot
        bot = get_bot()

        # 遍历所有群组，检查该用户是否在群内绑定，且群未禁用播报
        for parent_id in bind_data.content.keys():
            # 跳过私聊
            if not parent_id.isdigit() or len(parent_id) < 6:
                continue

            # 检查群是否禁用播报
            if disable_parent_data.is_disabled(parent_id):
                continue

            # 检查该Steam ID是否在该群绑定
            bind_info = bind_data.get_by_steam_id(parent_id, steam_id)
            if not bind_info:
                continue

            # 获取显示名称
            display_name = bind_info.get("nickname") or player_name

            # 发送通知
            try:
                message = f"{display_name} 开始游戏啦！\n" + MessageSegment.image(img_base64)
                await bot.send_group_msg(group_id=int(parent_id), message=message)
                logger.info(f"已向群 {parent_id} 播报 {display_name} 开始游戏 {game_name}")
            except Exception as e:
                logger.error(f"向群 {parent_id} 发送播报失败: {e}")

    except Exception as e:
        logger.error(f"播报开始游戏失败: {e}")


# ==================== 初始化 ====================

@driver.on_startup
async def startup():
    """启动时初始化"""
    logger.info("Steam插件已加载")
    if steam_api:
        logger.info(f"Steam API已配置，播报间隔：{STEAM_BROADCAST_INTERVAL}秒")
    else:
        logger.warning("Steam API未配置，部分功能将无法使用")


@driver.on_shutdown
async def shutdown():
    """关闭时保存数据"""
    try:
        bind_data.save()
        steam_info_data.save()
        parent_data.save()
        disable_parent_data.save()
        subscription_data.save()
        logger.info("Steam插件数据已保存")
    except Exception as e:
        logger.error(f"保存Steam插件数据失败: {e}")
