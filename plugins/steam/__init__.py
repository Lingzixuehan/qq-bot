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
from common.steam_friends_image import generate_steam_friends_list_base64
from common.steam_profile_image import generate_steam_profile_image_base64, generate_steam_games_image_base64

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
            "用法：/绑定steam <Steam ID/个性化URL/好友码>\n\n"
            "示例：\n"
            "/绑定steam 76561198012345678 (Steam ID)\n"
            "/绑定steam gaben (个性化URL)\n"
            "/绑定steam 123-456-789 (好友码)\n\n"
            "💡 获取Steam ID方法：\n"
            "1. 访问 https://steamcommunity.com/my/\n"
            "2. 地址栏中的数字就是你的Steam ID\n"
            "3. 或使用个性化URL/好友码"
        )
        return

    qq_id = str(event.user_id)

    # 尝试解析Steam ID
    steam_id = steam_input

    # 如果输入看起来是17位Steam ID，直接使用
    if steam_input.isdigit() and len(steam_input) == 17:
        steam_id = steam_input
    # 如果包含连字符，可能是好友码
    elif "-" in steam_input:
        resolved_id = await steam_api.resolve_friend_code(steam_input)
        if not resolved_id:
            await bind_steam.finish("❌ 无法解析该好友码，请检查后重试")
            return
        steam_id = resolved_id
    # 否则尝试作为个性化URL解析
    else:
        resolved_id = await steam_api.resolve_vanity_url(steam_input)
        if not resolved_id:
            await bind_steam.finish("❌ 无法解析该个性化URL，请检查输入是否正确")
            return
        steam_id = resolved_id

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

    # 获取QQ用户信息
    qq_user_name = None
    try:
        if isinstance(event, GroupMessageEvent):
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(target_qq))
            qq_user_name = user_info.get("card") or user_info.get("nickname", f"QQ{target_qq}")
        else:
            user_info = await bot.get_stranger_info(user_id=int(target_qq))
            qq_user_name = user_info.get("nickname", f"QQ{target_qq}")
    except:
        qq_user_name = f"QQ{target_qq}"

    # 获取Steam资料
    player_info = await steam_api.get_player_summaries(steam_id)
    if not player_info:
        await steam_profile.finish("❌ 获取Steam资料失败")
        return

    # 获取最近玩的游戏
    recent_games = await steam_api.get_recently_played_games(steam_id, 5)

    # 生成图片
    try:
        img_base64 = generate_steam_profile_image_base64(player_info, recent_games, qq_user_name)
        await steam_profile.finish(MessageSegment.image(img_base64))
    except Exception as e:
        print(f"生成Steam资料图片失败: {e}")
        # 降级为文本格式
        nickname = player_info.get("personaname", "未知")
        state = get_player_state_text(player_info.get("personastateflags", 0))
        profile_url = player_info.get("profileurl", "")

        msg = f"🎮 Steam资料\n\nQQ用户: {qq_user_name}\nSteam昵称：{nickname}\n状态：{state}\n主页：{profile_url}"
        await steam_profile.finish(msg)


# Steam最近游戏
steam_recent = on_command("steam游戏", aliases={"最近在玩"}, priority=5)


@steam_recent.handle()
async def handle_steam_recent(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
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

    # 获取QQ用户信息
    qq_user_name = None
    try:
        if isinstance(event, GroupMessageEvent):
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(target_qq))
            qq_user_name = user_info.get("card") or user_info.get("nickname", f"QQ{target_qq}")
        else:
            user_info = await bot.get_stranger_info(user_id=int(target_qq))
            qq_user_name = user_info.get("nickname", f"QQ{target_qq}")
    except:
        qq_user_name = f"QQ{target_qq}"

    # 获取Steam资料和最近玩的游戏
    player_info = await steam_api.get_player_summaries(steam_id)
    games = await steam_api.get_recently_played_games(steam_id, 10)

    if not games:
        await steam_recent.finish("❌ 该用户最近没有玩游戏或游戏库未公开")
        return

    # 使用资料图片生成器（只显示游戏部分）
    try:
        if player_info:
            img_base64 = generate_steam_profile_image_base64(player_info, games, qq_user_name)
        else:
            # 如果获取不到资料，使用文本格式
            raise Exception("无法获取玩家资料")
        await steam_recent.finish(MessageSegment.image(img_base64))
    except Exception as e:
        print(f"生成最近游戏图片失败: {e}")
        # 降级为文本格式
        msg = f"🎮 最近玩的游戏\n\nQQ用户: {qq_user_name}\n\n"
        for i, game in enumerate(games, 1):
            name = game.get("name", "未知游戏")
            playtime_2weeks = game.get("playtime_2weeks", 0)
            playtime_forever = game.get("playtime_forever", 0)
            msg += f"{i}. {name}\n   最近：{format_playtime(playtime_2weeks)} | 总计：{format_playtime(playtime_forever)}\n"

        await steam_recent.finish(msg.strip())


# Steam游戏库
steam_games = on_command("steam游戏库", aliases={"steam库存", "steamgames"}, priority=5)


@steam_games.handle()
async def handle_steam_games(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
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

    # 获取QQ用户信息
    qq_user_name = None
    try:
        if isinstance(event, GroupMessageEvent):
            user_info = await bot.get_group_member_info(group_id=event.group_id, user_id=int(target_qq))
            qq_user_name = user_info.get("card") or user_info.get("nickname", f"QQ{target_qq}")
        else:
            user_info = await bot.get_stranger_info(user_id=int(target_qq))
            qq_user_name = user_info.get("nickname", f"QQ{target_qq}")
    except:
        qq_user_name = f"QQ{target_qq}"

    # 获取游戏库
    games = await steam_api.get_owned_games(steam_id, include_appinfo=True)
    if not games:
        await steam_games.finish("❌ 该用户游戏库未公开或为空")
        return

    # 生成图片
    try:
        img_base64 = generate_steam_games_image_base64(games, qq_user_name)
        await steam_games.finish(MessageSegment.image(img_base64))
    except Exception as e:
        print(f"生成游戏库图片失败: {e}")
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


# Steam视奸
steam_spy = on_command("steam视奸", aliases={"视奸", "steam好友", "查看在线"}, priority=5)


@steam_spy.handle()
async def handle_steam_spy(event: MessageEvent):
    """查看所有绑定用户的Steam状态"""
    if not steam_api:
        await steam_spy.finish("❌ Steam功能未配置")
        return

    # 获取所有绑定的用户
    bindings = await SteamDB.get_all_bindings()

    if not bindings:
        await steam_spy.finish("❌ 还没有人绑定Steam账号")
        return

    # 提取所有Steam ID
    steam_ids = [binding["steam_id"] for binding in bindings]

    # 批量获取玩家信息
    players_info = await steam_api.get_multiple_player_summaries(steam_ids)

    if not players_info:
        await steam_spy.finish("❌ 获取Steam状态失败，请稍后重试")
        return

    # 按状态排序：游戏中 > 在线 > 离线
    def get_sort_key(player):
        if player.get("gameextrainfo"):
            return 0  # 游戏中
        elif player.get("personastate", 0) > 0:
            return 1  # 在线
        else:
            return 2  # 离线

    players_info_sorted = sorted(players_info, key=get_sort_key)

    # 生成好友列表图片
    try:
        img_base64 = generate_steam_friends_list_base64(players_info_sorted)
        await steam_spy.finish(MessageSegment.image(img_base64))
    except Exception as e:
        print(f"生成Steam好友列表图片失败: {e}")
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
