"""
21点游戏插件
包含签到系统和积分系统
"""
import re
from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.log import logger

from .points_manager import points_manager
from .game import game_manager
from .loan_manager import loan_manager
from .sell_manager import sell_manager
from ..common import require_fun_group

# 读取配置
driver = get_driver()
config = driver.config

# 最大同时游戏数量（0表示不限制）
MAX_CONCURRENT_GAMES = int(getattr(config, "blackjack_max_concurrent_games", 3))


async def handle_player_timeout(group_id: str, user_id: str):
    """
    处理玩家操作超时

    Args:
        group_id: 群号
        user_id: 用户QQ号
    """
    # 获取游戏
    game = game_manager.get_player_game(group_id, user_id)
    if not game or game.finished:
        return

    # 执行自动投降
    msg = game.auto_surrender(user_id)

    if msg:
        # 结算积分（如果游戏结束）
        if game.finished:
            msg += game.settle()

        # 发送消息到群
        try:
            bot = get_driver().bots.get(list(get_driver().bots.keys())[0])
            if bot:
                await bot.send_group_msg(group_id=int(group_id), message=parse_at_message(msg))
        except Exception as e:
            logger.error(f"发送超时消息失败: {e}")


def parse_at_message(msg: str) -> Message:
    """
    解析消息中的 [AT:user_id] 标记并转换为@消息段

    Args:
        msg: 原始消息文本

    Returns:
        Message对象
    """
    result = Message()
    last_end = 0

    # 查找所有 [AT:user_id] 标记
    pattern = r'\[AT:(\d+)\]'
    for match in re.finditer(pattern, msg):
        # 添加标记之前的文本
        if match.start() > last_end:
            result.append(MessageSegment.text(msg[last_end:match.start()]))

        # 添加@消息段
        user_id = match.group(1)
        result.append(MessageSegment.at(user_id))

        last_end = match.end()

    # 添加剩余文本
    if last_end < len(msg):
        result.append(MessageSegment.text(msg[last_end:]))

    return result

# ============== 签到功能 ==============
sign_cmd = on_command("签到", aliases={"打卡", "qiandao"}, priority=5, block=True)


@sign_cmd.handle()
@require_fun_group()
async def handle_sign(event: GroupMessageEvent):
    """签到功能"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    success, points, msg = points_manager.sign_in(group_id, user_id)
    await sign_cmd.finish(msg)


# ============== 查询积分 ==============
points_query = on_command("积分", aliases={"我的积分", "查询积分"}, priority=5, block=True)


@require_fun_group()
@points_query.handle()
@require_fun_group()
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


@require_fun_group()
@rank_cmd.handle()
@require_fun_group()
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


# ============== 积分倒数排行榜 ==============
bottom_rank_cmd = on_command("积分倒数", aliases={"倒数排行", "poorest"}, priority=5, block=True)


@require_fun_group()
@bottom_rank_cmd.handle()
@require_fun_group()
async def handle_bottom_rank(bot: Bot, event: GroupMessageEvent):
    """积分倒数排行榜"""
    group_id = str(event.group_id)

    rank_list = points_manager.get_bottom_rank(group_id, limit=10)

    if not rank_list:
        await bottom_rank_cmd.finish("暂无积分记录！")

    msg = "💸 积分倒数排行榜 BOTTOM 10\n"
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

        # 倒数排行用不同的图标
        if i == 1:
            medal = "😭"  # 倒数第一
        elif i == 2:
            medal = "😢"  # 倒数第二
        elif i == 3:
            medal = "😥"  # 倒数第三
        else:
            medal = f"{i}."

        msg += f"{medal} {user_name}：{points} 分\n"

    await bottom_rank_cmd.finish(msg.strip())


# ============== 创建21点游戏 ==============
create_game_cmd = on_command("21点", aliases={"二十一点", "blackjack"}, priority=5, block=True)


@create_game_cmd.handle()
@require_fun_group()
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

    # 检查积分是否低于-500（破产线）
    current_points = points_manager.get_points(group_id, user_id)
    if current_points < -500:
        await create_game_cmd.finish(
            f"❌ 你已破产，无法参与游戏！\n"
            f"当前积分：{current_points}\n"
            f"💡 积分低于-500时无法参赛\n"
            f"💡 可以尝试向其他玩家借贷或卖身"
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
    success, game_id, error_msg = game_manager.create_game(
        group_id, user_id, user_name, bet, max_players, MAX_CONCURRENT_GAMES
    )

    if not success:
        await create_game_cmd.finish(error_msg)

    # 设置超时回调
    game = game_manager.get_game(group_id, game_id)
    if game:
        game.timeout_callback = handle_player_timeout

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
@require_fun_group()
async def handle_join_game(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """接受游戏"""
    group_id = str(event.group_id)
@require_fun_group()
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

    # 检查积分是否低于-500（破产线）
    current_points = points_manager.get_points(group_id, user_id)
    if current_points < -500:
        await join_game_cmd.finish(
            f"❌ 你已破产，无法参与游戏！\n"
            f"当前积分：{current_points}\n"
            f"💡 积分低于-500时无法参赛\n"
            f"💡 可以尝试向其他玩家借贷或卖身"
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

    # 解析并发送消息（处理@标记）
    await join_game_cmd.finish(parse_at_message(msg))


# ============== 叫牌 ==============
hit_cmd = on_command("叫牌", aliases={"要牌", "hit"}, priority=5, block=True)


@hit_cmd.handle()
@require_fun_group()
async def handle_hit(event: GroupMessageEvent):
    """叫牌"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户正在进行的游戏
@require_fun_group()
    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await hit_cmd.finish("❌ 你没有正在进行的游戏！")

    # 叫牌
    msg = game.hit(user_id)

    # 如果游戏结束，结算积分
    if game.finished:
        msg += game.settle()

    # 解析并发送消息（处理@标记）
    await hit_cmd.finish(parse_at_message(msg))


# ============== 停牌 ==============
stand_cmd = on_command("停牌", aliases={"不要了", "stand"}, priority=5, block=True)


@stand_cmd.handle()
@require_fun_group()
async def handle_stand(event: GroupMessageEvent):
    """停牌"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户正在进行的游戏
    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await stand_cmd.finish("❌ 你没有正在进行的游戏！")
@require_fun_group()

    # 停牌
    msg = game.stand(user_id)

    # 结算积分
    if game.finished:
        msg += game.settle()

    # 解析并发送消息（处理@标记）
    await stand_cmd.finish(parse_at_message(msg))


# ============== 投降 ==============
surrender_cmd = on_command("投降", aliases={"认输"}, priority=5, block=True)


@surrender_cmd.handle()
@require_fun_group()
async def handle_surrender(event: GroupMessageEvent):
    """投降"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户正在进行的游戏
    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await surrender_cmd.finish("❌ 你没有正在进行的游戏！")

    # 投降
    msg = game.surrender(user_id)
@require_fun_group()

    # 结算积分
    if game.finished:
        msg += game.settle()

    # 解析并发送消息（处理@标记）
    await surrender_cmd.finish(parse_at_message(msg))


# ============== 加倍 ==============
double_cmd = on_command("加倍", aliases={"双倍", "加注"}, priority=5, block=True)


@double_cmd.handle()
@require_fun_group()
async def handle_double(event: GroupMessageEvent):
    """加倍下注"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户正在进行的游戏
    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await double_cmd.finish("❌ 你没有正在进行的游戏！")

    # 加倍
    msg = game.double_down(user_id)

    # 结算积分
    if game.finished:
@require_fun_group()
        msg += game.settle()

    # 解析并发送消息（处理@标记）
    await double_cmd.finish(parse_at_message(msg))


# ============== 游戏列表 ==============
game_list_cmd = on_command("游戏列表", aliases={"21点列表"}, priority=5, block=True)


@game_list_cmd.handle()
@require_fun_group()
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

@require_fun_group()
    await game_list_cmd.finish(msg)


# ============== 发放积分（管理员功能）==============
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
            "用法：\n"
            "1. 给单个用户发放：/发放积分 <@用户或QQ号> <积分数>\n"
            "   示例：/发放积分 @张三 1000\n"
            "   示例：/发放积分 123456789 1000\n\n"
            "2. 给全群发放：/发放积分 <积分数>\n"
            "   示例：/发放积分 500"
        )

    # 检查消息中是否有@
    at_segments = [seg for seg in args if seg.type == "at"]

    try:
        parts = arg_text.split()

        # 判断是给单个用户还是全群发放
        if at_segments:
            # 有@，给单个用户发放
            target_user_id = str(at_segments[0].data["qq"])
            points = int(parts[-1])
            is_group_distribution = False
        elif len(parts) == 2:
            # 两个参数，给单个用户发放
            target_user_id = parts[0]
            points = int(parts[1])
            is_group_distribution = False
        elif len(parts) == 1:
            # 一个参数，给全群发放
            points = int(parts[0])
            is_group_distribution = True
        else:
            raise ValueError("参数数量错误")

        if points <= 0:
            await distribute_points_cmd.finish("❌ 积分必须大于0！")
        if points > 1000000:
            await distribute_points_cmd.finish("❌ 单次发放积分不能超过1000000！")

    except (ValueError, IndexError):
        await distribute_points_cmd.finish(
            "❌ 参数格式错误！\n"
            "用法：\n"
            "• 给单个用户：/发放积分 @用户 积分数\n"
            "• 给全群：/发放积分 积分数"
        )

    # 给全群发放
    if is_group_distribution:
        try:
            # 获取群成员列表
            member_list = await bot.get_group_member_list(group_id=event.group_id)

            success_count = 0
            for member in member_list:
                member_user_id = str(member["user_id"])
                points_manager.add_points(group_id, member_user_id, points)
                success_count += 1

            await distribute_points_cmd.finish(
                f"✅ 全群积分发放成功！\n"
                f"━━━━━━━━━━━━━━\n"
                f"发放人数：{success_count} 人\n"
                f"每人获得：+{points} 积分"
            )
        except Exception as e:
            await distribute_points_cmd.finish(f"❌ 发放积分失败：{e}")

    # 给单个用户发放
    else:
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


# ============== 借积分 ==============
borrow_cmd = on_command("借积分", aliases={"借款", "borrow"}, priority=5, block=True)


@borrow_cmd.handle()
@require_fun_group()
async def handle_borrow(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """借积分"""
    group_id = str(event.group_id)
    borrower_id = str(event.user_id)

    # 解析参数
    arg_text = args.extract_plain_text().strip()
    at_segments = [seg for seg in args if seg.type == "at"]

    if not at_segments:
        await borrow_cmd.finish(
            "用法：/借积分 @用户 <金额>\n"
            "示例：/借积分 @张三 1000\n"
            "━━━━━━━━━━━━━━\n"
            "💡 固定利率10%\n"
            "💡 5局游戏后自动扣除本金+利息"
        )

    try:
        lender_id = str(at_segments[0].data["qq"])
        parts = arg_text.split()
        amount = int(parts[-1])

        if amount <= 0:
            await borrow_cmd.finish("❌ 借款金额必须大于0！")
        if amount > 100000:
            await borrow_cmd.finish("❌ 单次借款不能超过100000！")
    except (ValueError, IndexError):
        await borrow_cmd.finish("❌ 参数格式错误！\n用法：/借积分 @用户 <金额>")

    # 不能向自己借款
    if borrower_id == lender_id:
        await borrow_cmd.finish("❌ 不能向自己借款！")

    # 创建借贷请求
@require_fun_group()
    success, msg = loan_manager.create_request(group_id, borrower_id, lender_id, amount)

    await borrow_cmd.finish(msg)


# ============== 借贷信息 ==============
loan_info_cmd = on_command("借贷信息", aliases={"我的借贷", "loan"}, priority=5, block=True)


@loan_info_cmd.handle()
@require_fun_group()
async def handle_loan_info(event: GroupMessageEvent):
    """查看借贷信息"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    loan_info = loan_manager.get_loan_info(group_id, user_id)

    if not loan_info:
        await loan_info_cmd.finish("你当前没有未还清的贷款。")

    await loan_info_cmd.finish(loan_info)


# ============== 同意借贷 ==============
approve_loan_cmd = on_command("同意借贷", aliases={"同意借款", "approve_loan"}, priority=5, block=True)


@approve_loan_cmd.handle()
@require_fun_group()
async def handle_approve_loan(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """同意借贷请求"""
    group_id = str(event.group_id)
    lender_id = str(event.user_id)

    # 解析参数
    at_segments = [seg for seg in args if seg.type == "at"]

    if not at_segments:
        await approve_loan_cmd.finish(
            "用法：/同意借贷 @用户\n"
            "示例：/同意借贷 @张三\n"
            "━━━━━━━━━━━━━━\n"
            "💡 同意对方向你借款的请求"
        )

    borrower_id = str(at_segments[0].data["qq"])

    # 不能是自己
    if lender_id == borrower_id:
        await approve_loan_cmd.finish("❌ 无效的操作！")

    # 同意借贷
    success, msg = loan_manager.approve_request(group_id, lender_id, borrower_id)

    await approve_loan_cmd.finish(msg)


# ============== 取消借贷 ==============
cancel_loan_cmd = on_command("取消借贷", aliases={"取消借款", "cancel_loan"}, priority=5, block=True)
@require_fun_group()


@cancel_loan_cmd.handle()
@require_fun_group()
async def handle_cancel_loan(event: GroupMessageEvent):
    """取消借贷请求"""
    group_id = str(event.group_id)
    borrower_id = str(event.user_id)

    # 取消借贷请求
    success, msg = loan_manager.cancel_request(group_id, borrower_id)

    await cancel_loan_cmd.finish(msg)


# ============== 平账（管理员功能）==============
clear_loans_cmd = on_command("平账", aliases={"清除借贷", "clear_loans"}, priority=5, block=True)


@clear_loans_cmd.handle()
async def handle_clear_loans(event: GroupMessageEvent):
    """平账 - 强制清除所有借贷记录（仅管理员）"""
@require_fun_group()
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 检查权限
    if user_id not in ADMIN_USERS:
        await clear_loans_cmd.finish("❌ 只有授权用户才能使用平账功能！")

    # 清除所有借贷
    success, msg = loan_manager.clear_all_loans(group_id)

    await clear_loans_cmd.finish(msg)


# ============== 卖身 ==============
sell_cmd = on_command("卖身", aliases={"出售", "sell"}, priority=5, block=True)


@sell_cmd.handle()
@require_fun_group()
async def handle_sell(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """卖身申请"""
    group_id = str(event.group_id)
    seller_id = str(event.user_id)

    # 解析参数
    arg_text = args.extract_plain_text().strip()
    at_segments = [seg for seg in args if seg.type == "at"]

    if not at_segments:
        await sell_cmd.finish(
            "用法：/卖身 @用户 <金额> <称号>\n"
            "示例：/卖身 @张三 1000 小狗\n"
            "━━━━━━━━━━━━━━\n"
            "💡 只有积分低于-500才能卖身\n"
            "💡 买家同意后会修改你的群昵称为\"买家的称号\""
        )

@require_fun_group()
    try:
        buyer_id = str(at_segments[0].data["qq"])
        parts = arg_text.split()

        # 找到金额（第一个数字）和称号（剩余部分）
        amount = None
        title_parts = []
        for part in parts:
            if amount is None:
                try:
                    amount = int(part)
                    continue
                except ValueError:
                    pass
            title_parts.append(part)

        title = " ".join(title_parts).strip()

        if not amount or amount <= 0:
            await sell_cmd.finish("❌ 金额必须大于0！")
        if amount > 100000:
            await sell_cmd.finish("❌ 金额不能超过100000！")
        if not title:
            await sell_cmd.finish("❌ 请输入称号！")
        if len(title) > 10:
            await sell_cmd.finish("❌ 称号不能超过10个字符！")
    except (ValueError, IndexError):
        await sell_cmd.finish("❌ 参数格式错误！\n用法：/卖身 @用户 <金额> <称号>")

    # 不能向自己卖身
    if seller_id == buyer_id:
        await sell_cmd.finish("❌ 不能向自己卖身！")

    # 创建卖身申请
    success, msg = sell_manager.create_request(group_id, seller_id, buyer_id, amount, title)

    await sell_cmd.finish(msg)


# ============== 同意卖身 ==============
approve_sell_cmd = on_command("同意卖身", aliases={"接受卖身", "accept"}, priority=5, block=True)


@require_fun_group()
@approve_sell_cmd.handle()
@require_fun_group()
async def handle_approve_sell(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """同意卖身申请"""
    group_id = str(event.group_id)
    buyer_id = str(event.user_id)

    # 解析参数
    at_segments = [seg for seg in args if seg.type == "at"]

    if not at_segments:
        await approve_sell_cmd.finish(
            "用法：/同意卖身 @用户\n"
            "示例：/同意卖身 @张三\n"
            "━━━━━━━━━━━━━━\n"
            "💡 同意对方的卖身申请"
        )

    seller_id = str(at_segments[0].data["qq"])

    # 获取买家昵称
    try:
        buyer_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=int(buyer_id)
        )
        buyer_name = buyer_info.get("card") or buyer_info.get("nickname", f"用户{buyer_id}")
    except:
        buyer_name = f"用户{buyer_id}"

    # 同意申请
    success, msg, request = sell_manager.approve_request(group_id, buyer_id, seller_id)

    if not success:
        await approve_sell_cmd.finish(msg)

    # 修改卖身者的群昵称
    new_nickname = f"{buyer_name}的{request['title']}"
    try:
        await bot.set_group_card(
            group_id=event.group_id,
            user_id=int(seller_id),
            card=new_nickname
        )
        msg += f"\n✅ 已修改群昵称为：{new_nickname}"
    except Exception as e:
        msg += f"\n❌ 修改群昵称失败：{e}\n💡 可能是权限不足"

    await approve_sell_cmd.finish(msg)


# ============== 取消卖身 ==============
cancel_sell_cmd = on_command("取消卖身", aliases={"撤销卖身", "cancel"}, priority=5, block=True)


@cancel_sell_cmd.handle()
@require_fun_group()
async def handle_cancel_sell(event: GroupMessageEvent):
    """取消卖身申请"""
    group_id = str(event.group_id)
    seller_id = str(event.user_id)

    success, msg = sell_manager.cancel_request(group_id, seller_id)

    await cancel_sell_cmd.finish(msg)
