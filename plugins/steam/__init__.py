"""
Steam功能插件
支持Steam账号绑定、资料查询、游戏库查询等
"""
from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
import sys
from pathlib import Path
import os

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))
from common.database import SteamDB
from common.steam_api import SteamAPI, format_playtime, get_player_state_text

# 获取Steam API Key
driver = get_driver()
config = driver.config
STEAM_API_KEY = getattr(config, "steam_api_key", None)

# 初始化Steam API
steam_api = None
if STEAM_API_KEY:
    steam_api = SteamAPI(STEAM_API_KEY)


# 绑定Steam账号
bind_steam = on_command("绑定steam", aliases={"bindsteam"}, priority=5)


@bind_steam.handle()
async def handle_bind_steam(event: MessageEvent, args: Message = CommandArg()):
    """绑定Steam账号"""
    if not steam_api:
        await bind_steam.finish("❌ Steam功能未配置，请联系管理员设置STEAM_API_KEY")
        return

    steam_input = args.extract_plain_text().strip()
    if not steam_input:
        await bind_steam.finish(
            "用法：/绑定steam <Steam ID或个性化URL>\n\n"
            "示例：\n"
            "/绑定steam 76561198012345678\n"
            "/绑定steam gaben\n\n"
            "💡 获取Steam ID方法：\n"
            "1. 访问 https://steamcommunity.com/my/\n"
            "2. 地址栏中的数字就是你的Steam ID\n"
            "3. 或者使用个性化URL（设置 > 编辑个人资料）"
        )
        return

    qq_id = str(event.user_id)

    # 尝试解析Steam ID
    steam_id = steam_input

    # 如果不是纯数字，尝试作为个性化URL解析
    if not steam_input.isdigit():
        resolved_id = await steam_api.resolve_vanity_url(steam_input)
        if resolved_id:
            steam_id = resolved_id
        else:
            await bind_steam.finish("❌ 无法解析该Steam ID或个性化URL，请检查后重试")
            return

    # 验证Steam ID并获取用户信息
    player_info = await steam_api.get_player_summaries(steam_id)
    if not player_info:
        await bind_steam.finish("❌ 无法获取Steam账号信息，请检查Steam ID是否正确")
        return

    steam_name = player_info.get("personaname", "")

    # 绑定到数据库
    success = await SteamDB.bind_steam(qq_id, steam_id, steam_name)

    if success:
        await bind_steam.finish(
            f"✅ 绑定成功！\n\n"
            f"Steam昵称：{steam_name}\n"
            f"Steam ID：{steam_id}\n\n"
            f"现在可以使用以下命令：\n"
            f"/steam资料 - 查看Steam个人资料\n"
            f"/steam游戏 - 查看最近在玩的游戏\n"
            f"/steam游戏库 - 查看游戏库"
        )
    else:
        await bind_steam.finish("❌ 绑定失败，请稍后重试")


# 解绑Steam账号
unbind_steam = on_command("解绑steam", aliases={"unbindsteam"}, priority=5)


@unbind_steam.handle()
async def handle_unbind_steam(event: MessageEvent):
    """解绑Steam账号"""
    qq_id = str(event.user_id)

    # 检查是否已绑定
    binding = await SteamDB.get_steam_binding(qq_id)
    if not binding:
        await unbind_steam.finish("❌ 你还没有绑定Steam账号")
        return

    # 解绑
    success = await SteamDB.unbind_steam(qq_id)

    if success:
        await unbind_steam.finish("✅ 已解绑Steam账号")
    else:
        await unbind_steam.finish("❌ 解绑失败，请稍后重试")


# Steam资料查询
steam_profile = on_command("steam资料", aliases={"steam信息", "steamprofile"}, priority=5)


@steam_profile.handle()
async def handle_steam_profile(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    """查询Steam资料"""
    if not steam_api:
        await steam_profile.finish("❌ Steam功能未配置")
        return

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
        return

    steam_id = binding["steam_id"]

    # 获取Steam资料
    player_info = await steam_api.get_player_summaries(steam_id)
    if not player_info:
        await steam_profile.finish("❌ 获取Steam资料失败")
        return

    # 构建资料信息
    nickname = player_info.get("personaname", "未知")
    state = get_player_state_text(player_info.get("personastateflags", 0))
    avatar_url = player_info.get("avatarfull", "")
    profile_url = player_info.get("profileurl", "")

    # 获取最近玩的游戏
    recent_games = await steam_api.get_recently_played_games(steam_id, 3)
    recent_text = ""
    if recent_games:
        recent_text = "\n\n📋 最近在玩："
        for game in recent_games[:3]:
            name = game.get("name", "未知游戏")
            playtime_2weeks = game.get("playtime_2weeks", 0)
            recent_text += f"\n  • {name} ({format_playtime(playtime_2weeks)})"

    # 构建消息
    msg = (
        f"🎮 Steam资料\n\n"
        f"昵称：{nickname}\n"
        f"状态：{state}\n"
        f"主页：{profile_url}"
        f"{recent_text}"
    )

    # 如果有头像URL，尝试发送图片
    if avatar_url:
        await steam_profile.finish(
            MessageSegment.image(avatar_url) + MessageSegment.text(f"\n{msg}")
        )
    else:
        await steam_profile.finish(msg)


# Steam最近游戏
steam_recent = on_command("steam游戏", aliases={"最近在玩"}, priority=5)


@steam_recent.handle()
async def handle_steam_recent(event: MessageEvent, args: Message = CommandArg()):
    """查询最近玩的游戏"""
    if not steam_api:
        await steam_recent.finish("❌ Steam功能未配置")
        return

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
        return

    steam_id = binding["steam_id"]

    # 获取最近玩的游戏
    games = await steam_api.get_recently_played_games(steam_id, 10)
    if not games:
        await steam_recent.finish("❌ 该用户最近没有玩游戏或游戏库未公开")
        return

    # 构建消息
    msg = f"🎮 最近玩的游戏（{len(games)}款）\n\n"

    for i, game in enumerate(games, 1):
        name = game.get("name", "未知游戏")
        playtime_2weeks = game.get("playtime_2weeks", 0)
        playtime_forever = game.get("playtime_forever", 0)

        msg += f"{i}. {name}\n"
        msg += f"   最近：{format_playtime(playtime_2weeks)} | 总计：{format_playtime(playtime_forever)}\n"

    await steam_recent.finish(msg.strip())


# Steam游戏库
steam_games = on_command("steam游戏库", aliases={"steam库存", "steamgames"}, priority=5)


@steam_games.handle()
async def handle_steam_games(event: MessageEvent, args: Message = CommandArg()):
    """查询游戏库"""
    if not steam_api:
        await steam_games.finish("❌ Steam功能未配置")
        return

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
        return

    steam_id = binding["steam_id"]

    # 获取游戏库
    games = await steam_api.get_owned_games(steam_id, include_appinfo=True)
    if not games:
        await steam_games.finish("❌ 该用户游戏库未公开或为空")
        return

    # 统计信息
    total_games = len(games)
    total_playtime = sum(game.get("playtime_forever", 0) for game in games)

    # 按游戏时长排序
    games_sorted = sorted(games, key=lambda x: x.get("playtime_forever", 0), reverse=True)

    # 构建消息
    msg = f"📚 Steam游戏库\n\n"
    msg += f"游戏总数：{total_games} 款\n"
    msg += f"总游戏时长：{format_playtime(total_playtime)}\n\n"
    msg += "🏆 游戏时长TOP 10：\n\n"

    for i, game in enumerate(games_sorted[:10], 1):
        name = game.get("name", "未知游戏")
        playtime = game.get("playtime_forever", 0)
        msg += f"{i}. {name}\n   {format_playtime(playtime)}\n"

    await steam_games.finish(msg.strip())
