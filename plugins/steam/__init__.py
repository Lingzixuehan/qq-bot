"""
Steam功能插件 - 完整版
支持Steam账号绑定、资料查询、游戏库查询、好友状态监控、自动播报等功能
"""
import base64
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

from nonebot import on_command, get_driver, require
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

# 导入调度器
require("nonebot_plugin_apscheduler")
from nonebot_plugin_apscheduler import scheduler

# 导入本地存储
require("nonebot_plugin_localstore")
import nonebot_plugin_localstore as store

# 导入公共模块
import sys
sys.path.append(str(Path(__file__).parent.parent))
from common.database import SteamDB
from common.steam_api import SteamAPI, format_playtime, get_player_state_text

# 导入新模块
from .data_source import BindData, SteamInfoData, ParentData, DisableParentData
from .draw import draw_friends_status, draw_start_gaming
from .utils import fetch_avatar, convert_player_name_to_nickname
from .models import Player, ProcessedPlayer

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
        "/steam帮助 - 显示Steam插件帮助"
    )
)

# 获取配置
driver = get_driver()
config = driver.config
STEAM_API_KEY = getattr(config, "steam_api_key", None)
STEAM_BROADCAST_INTERVAL = getattr(config, "steam_broadcast_interval", 300)  # 默认5分钟
STEAM_BROADCAST_ENABLED = getattr(config, "steam_broadcast_enabled", True)

# 初始化Steam API
steam_api: Optional[SteamAPI] = None
if STEAM_API_KEY:
    steam_api = SteamAPI(STEAM_API_KEY)
else:
    logger.warning("Steam API Key未配置，Steam功能将无法使用")

# 获取数据目录
plugin_data_dir = store.get_plugin_data_dir()
plugin_cache_dir = store.get_plugin_cache_dir()

# 初始化数据管理类
bind_data = BindData(plugin_data_dir / "bind_data.json")
steam_info_data = SteamInfoData(plugin_cache_dir / "steam_info.json")
parent_data = ParentData(plugin_data_dir / "parent_data.json")
disable_parent_data = DisableParentData(plugin_data_dir / "disabled_parents.json")

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
        "nickname": None  # 默认无昵称
    }

    # 检查是否已存在绑定
    existing = bind_data.get(parent_id, user_id)
    if existing:
        bind_data.remove(parent_id, user_id)

    bind_data.add(parent_id, bind_info)
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
    recent_games = await steam_api.get_recently_played_games(steam_id, 5)

    # 生成图片 (使用旧的图片生成方法，保持兼容性)
    try:
        from common.steam_profile_image import generate_steam_profile_image_base64
        img_base64 = generate_steam_profile_image_base64(player_info, recent_games, qq_user_name)
        await steam_profile.finish(MessageSegment.image(img_base64))
    except Exception as e:
        logger.error(f"生成Steam资料图片失败: {e}")
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

    # 使用资料图片生成器
    try:
        from common.steam_profile_image import generate_steam_profile_image_base64
        if player_info:
            img_base64 = generate_steam_profile_image_base64(player_info, games, qq_user_name)
        else:
            raise Exception("无法获取玩家资料")
        await steam_recent.finish(MessageSegment.image(img_base64))
    except Exception as e:
        logger.error(f"生成最近游戏图片失败: {e}")
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

    # 生成图片
    try:
        from common.steam_profile_image import generate_steam_games_image_base64
        img_base64 = generate_steam_games_image_base64(games, qq_user_name)
        await steam_games.finish(MessageSegment.image(img_base64))
    except Exception as e:
        logger.error(f"生成游戏库图片失败: {e}")
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
async def handle_steam_spy(event: MessageEvent):
    """查看所有绑定用户的Steam状态"""
    if not steam_api:
        await steam_spy.finish("❌ Steam功能未配置")

    # 获取群组ID
    if isinstance(event, GroupMessageEvent):
        parent_id = str(event.group_id)
    else:
        parent_id = str(event.user_id)

    # 获取该群组的所有绑定Steam ID
    steam_ids = bind_data.get_all(parent_id)

    # 如果新数据结构为空，尝试从旧数据库获取
    if not steam_ids:
        bindings = await SteamDB.get_all_bindings()
        steam_ids = [binding["steam_id"] for binding in bindings]

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

    # 获取头像字典
    avatars: Dict[str, any] = {}
    for player in players_info_sorted:
        steam_id = player.get("steamid", "")
        try:
            avatar = await fetch_avatar(player, avatar_cache_dir)
            avatars[steam_id] = avatar
        except Exception as e:
            logger.error(f"获取头像失败 {steam_id}: {e}")

    # 使用新的draw_friends_status生成图片
    try:
        friends_image = draw_friends_status(players_info_sorted, avatars, show_title=True)
        img_base64 = pil_image_to_base64(friends_image)
        await steam_spy.finish(MessageSegment.image(img_base64))
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
    bind_data.remove(parent_id, user_id)
    bind_data.add(parent_id, bind_info)
    bind_data.save()

    await steam_nickname.finish(f"✅ 已设置Steam显示昵称为：{nickname}")


# 启用播报
steam_enable_broadcast = on_command("steam启用播报", priority=5, block=True)


@steam_enable_broadcast.handle()
async def handle_enable_broadcast(event: MessageEvent):
    """在当前群启用游戏状态播报"""
    if not isinstance(event, GroupMessageEvent):
        await steam_enable_broadcast.finish("❌ 该命令只能在群聊中使用")

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


# Steam帮助
steam_help = on_command("steam帮助", aliases={"steamhelp"}, priority=5, block=True)


@steam_help.handle()
async def handle_steam_help():
    """显示Steam插件帮助"""
    help_text = """🎮 Steam插件帮助

【账号管理】
/绑定steam <ID> - 绑定Steam账号
  支持Steam ID (76561198...)或个性化URL
/解绑steam - 解绑Steam账号
/steam昵称 <昵称> - 设置显示昵称

【查询功能】
/steam资料 [@用户] - 查看Steam资料
/steam游戏 [@用户] - 查看最近游戏
/steam游戏库 [@用户] - 查看完整游戏库
/steam视奸 - 查看所有好友在线状态

【播报功能】
/steam启用播报 - 启用游戏状态播报
/steam禁用播报 - 禁用游戏状态播报

启用播报后，当好友开始玩游戏时会自动通知

💡 提示：
1. 绑定前需确保Steam资料为公开
2. 游戏库需设置为公开才能查看
3. 播报功能仅在群聊中生效"""

    await steam_help.finish(help_text)


# ==================== 自动播报系统 ====================

@scheduler.scheduled_job("interval", seconds=STEAM_BROADCAST_INTERVAL, id="steam_status_check")
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
        logger.info("Steam插件数据已保存")
    except Exception as e:
        logger.error(f"保存Steam插件数据失败: {e}")
