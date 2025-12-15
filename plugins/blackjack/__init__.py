"""
21点游戏插件
包含签到系统和积分系统
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg
from nonebot.log import logger

from .points_manager import points_manager
from .game import game_manager

# ============== 签到功能 ==============
sign_cmd = on_command("签到", aliases={"打卡", "qiandao"}, priority=5, block=True)


@sign_cmd.handle()
async def handle_sign(event: GroupMessageEvent):
    """签到功能"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    success, points, msg = points_manager.sign_in(group_id, user_id)
    await sign_cmd.finish(msg)


# ============== 查询积分 ==============
points_query = on_command("积分", aliases={"我的积分", "查询积分"}, priority=5, block=True)


@points_query.handle()
async def handle_points_query(bot: Bot, event: GroupMessageEvent):
    """查询积分"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    points = points_manager.get_points(group_id, user_id)

    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=event.user_id
        )
        user_name = user_info.get("card") or user_info.get("nickname", f"用户{user_id}")
    except:
        user_name = f"用户{user_id}"

    await points_query.finish(f"💰 {user_name} 的积分：{points}")


# ============== 积分排行榜 ==============
rank_cmd = on_command("积分排行", aliases={"排行榜", "rank"}, priority=5, block=True)


@rank_cmd.handle()
async def handle_rank(bot: Bot, event: GroupMessageEvent):
    """积分排行榜"""
    group_id = str(event.group_id)

    rank_list = points_manager.get_rank(group_id, limit=10)

    if not rank_list:
        await rank_cmd.finish("暂无积分记录！")

    msg = "🏆 积分排行榜 TOP 10\n"
    msg += "━━━━━━━━━━━━━━\n"

    for i, (uid, points) in enumerate(rank_list, 1):
        try:
            user_info = await bot.get_group_member_info(
                group_id=event.group_id,
                user_id=int(uid)
            )
            user_name = user_info.get("card") or user_info.get("nickname", f"用户{uid}")
        except:
            user_name = f"用户{uid}"

        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
        msg += f"{medal} {user_name}：{points} 分\n"

    await rank_cmd.finish(msg.strip())


# ============== 创建21点游戏 ==============
create_game_cmd = on_command("21点", aliases={"二十一点", "blackjack"}, priority=5, block=True)


@create_game_cmd.handle()
async def handle_create_game(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """创建21点游戏"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 解析赌注和玩家数
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await create_game_cmd.finish(
            "用法：/21点 <赌注> [玩家数]\n"
            "示例：/21点 100\n"
            "示例：/21点 100 3\n"
            "创建一个赌注为100积分的游戏，可选最多3个玩家"
        )

    try:
        parts = arg_text.split()
        bet = int(parts[0])
        max_players = int(parts[1]) if len(parts) > 1 else 1

        if bet <= 0:
            await create_game_cmd.finish("❌ 赌注必须大于0！")
        if bet > 10000:
            await create_game_cmd.finish("❌ 赌注不能超过10000！")
        if max_players < 1 or max_players > 5:
            await create_game_cmd.finish("❌ 玩家数必须在1-5之间！")
    except (ValueError, IndexError):
        await create_game_cmd.finish("❌ 请输入有效的数字！")

    # 检查积分是否足够
    if not points_manager.has_enough_points(group_id, user_id, bet):
        current_points = points_manager.get_points(group_id, user_id)
        await create_game_cmd.finish(
            f"❌ 积分不足！\n"
            f"需要：{bet} 积分\n"
            f"当前：{current_points} 积分"
        )

    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=event.user_id
        )
        user_name = user_info.get("card") or user_info.get("nickname", f"用户{user_id}")
    except:
        user_name = f"用户{user_id}"

    # 创建游戏
    game_id = game_manager.create_game(group_id, user_id, user_name, bet, max_players)

    await create_game_cmd.finish(
        f"🎮 21点游戏已创建！\n"
        f"━━━━━━━━━━━━━━\n"
        f"游戏ID：{game_id}\n"
        f"庄家：{user_name}\n"
        f"赌注：{bet} 积分\n"
        f"玩家数：{max_players}\n"
        f"━━━━━━━━━━━━━━\n"
        f"💡 使用 /接受游戏 {game_id} 来参与游戏"
    )


# ============== 接受游戏 ==============
join_game_cmd = on_command("接受游戏", aliases={"加入游戏", "join"}, priority=5, block=True)


@join_game_cmd.handle()
async def handle_join_game(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """接受游戏"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 解析游戏ID
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await join_game_cmd.finish("用法：/接受游戏 <游戏ID>")

    try:
        game_id = int(arg_text)
    except ValueError:
        await join_game_cmd.finish("❌ 请输入有效的游戏ID！")

    # 获取游戏
    game = game_manager.get_game(group_id, game_id)
    if not game:
        await join_game_cmd.finish("❌ 游戏不存在！")

    if game.started:
        await join_game_cmd.finish("❌ 游戏已经开始了！")

    if game.creator_id == user_id:
        await join_game_cmd.finish("❌ 不能参加自己创建的游戏！")

    # 检查积分是否足够
    if not points_manager.has_enough_points(group_id, user_id, game.bet):
        current_points = points_manager.get_points(group_id, user_id)
        await join_game_cmd.finish(
            f"❌ 积分不足！\n"
            f"需要：{game.bet} 积分\n"
            f"当前：{current_points} 积分"
        )

    # 获取用户昵称
    try:
        user_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=event.user_id
        )
        user_name = user_info.get("card") or user_info.get("nickname", f"用户{user_id}")
    except:
        user_name = f"用户{user_id}"

    # 加入游戏
    success, msg = game.add_player(user_id, user_name)

    if not success:
        await join_game_cmd.finish(msg)

    # 如果游戏直接结束（黑杰克），立即结算
    if game.finished:
        msg += game.settle()

    await join_game_cmd.finish(msg)


# ============== 叫牌 ==============
hit_cmd = on_command("叫牌", aliases={"要牌", "hit"}, priority=5, block=True)


@hit_cmd.handle()
async def handle_hit(event: GroupMessageEvent):
    """叫牌"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户正在进行的游戏
    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await hit_cmd.finish("❌ 你没有正在进行的游戏！")

    # 叫牌
    msg = game.hit(user_id)

    # 如果游戏结束，结算积分
    if game.finished:
        msg += game.settle()

    await hit_cmd.finish(msg)


# ============== 停牌 ==============
stand_cmd = on_command("停牌", aliases={"不要了", "stand"}, priority=5, block=True)


@stand_cmd.handle()
async def handle_stand(event: GroupMessageEvent):
    """停牌"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户正在进行的游戏
    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await stand_cmd.finish("❌ 你没有正在进行的游戏！")

    # 停牌
    msg = game.stand(user_id)

    # 结算积分
    if game.finished:
        msg += game.settle()

    await stand_cmd.finish(msg)


# ============== 游戏列表 ==============
game_list_cmd = on_command("游戏列表", aliases={"21点列表"}, priority=5, block=True)


@game_list_cmd.handle()
async def handle_game_list(event: GroupMessageEvent):
    """游戏列表"""
    group_id = str(event.group_id)

    waiting_games = game_manager.get_waiting_games(group_id)

    if not waiting_games:
        await game_list_cmd.finish("当前没有等待中的游戏！")

    msg = "🎮 等待中的游戏\n"
    msg += "━━━━━━━━━━━━━━\n"

    for game_id, game in waiting_games:
        msg += f"游戏 {game_id}：{game.creator_name}（{game.bet}积分）\n"

    msg += "━━━━━━━━━━━━━━\n"
    msg += "使用 /接受游戏 <ID> 来参与游戏"

    await game_list_cmd.finish(msg)


# ============== 发放积分（管理员功能）==============
from nonebot import get_driver

driver = get_driver()
config = driver.config

# 允许发放积分的QQ号列表
ADMIN_USERS = {
    uid.strip()
    for uid in str(getattr(config, "blackjack_admin_users", "") or "").split(",")
    if uid.strip()
}

distribute_points_cmd = on_command("发放积分", priority=5, block=True)


@distribute_points_cmd.handle()
async def handle_distribute_points(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """发放积分给用户（仅管理员）"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 检查权限
    if user_id not in ADMIN_USERS:
        await distribute_points_cmd.finish("❌ 只有授权用户才能发放积分！")

    # 解析参数
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await distribute_points_cmd.finish(
            "用法：/发放积分 <@用户或QQ号> <积分数>\n"
            "示例：/发放积分 @张三 1000\n"
            "示例：/发放积分 123456789 1000"
        )

    # 解析目标用户和积分
    # 检查消息中是否有@
    at_segments = [seg for seg in args if seg.type == "at"]

    try:
        if at_segments:
            # 如果有@，从at中获取QQ号
            target_user_id = str(at_segments[0].data["qq"])
            # 从文本中提取积分数
            parts = arg_text.split()
            points = int(parts[-1])  # 取最后一个数字作为积分
        else:
            # 没有@，从文本解析
            parts = arg_text.split()
            if len(parts) != 2:
                raise ValueError("参数数量错误")
            target_user_id = parts[0]
            points = int(parts[1])

        if points <= 0:
            await distribute_points_cmd.finish("❌ 积分必须大于0！")
        if points > 1000000:
            await distribute_points_cmd.finish("❌ 单次发放积分不能超过1000000！")

    except (ValueError, IndexError):
        await distribute_points_cmd.finish(
            "❌ 参数格式错误！\n"
            "用法：/发放积分 <@用户或QQ号> <积分数>\n"
            "示例：/发放积分 @张三 1000"
        )

    # 获取目标用户昵称
    try:
        user_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=int(target_user_id)
        )
        target_user_name = user_info.get("card") or user_info.get("nickname", f"用户{target_user_id}")
    except:
        target_user_name = f"用户{target_user_id}"

    # 发放积分
    points_manager.add_points(group_id, target_user_id, points)
    new_points = points_manager.get_points(group_id, target_user_id)

    await distribute_points_cmd.finish(
        f"✅ 积分发放成功！\n"
        f"━━━━━━━━━━━━━━\n"
        f"目标用户：{target_user_name}\n"
        f"发放积分：+{points}\n"
        f"当前积分：{new_points}"
    )
