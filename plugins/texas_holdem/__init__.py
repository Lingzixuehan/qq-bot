"""
德州扑克游戏插件
"""
import re
from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.log import logger
from nonebot.exception import FinishedException

from .game import game_manager
from ..blackjack.points_manager import points_manager
from ..common import require_fun_group

# 读取配置
driver = get_driver()
config = driver.config

# 配置项
MAX_CONCURRENT_GAMES = int(getattr(config, "texas_holdem_max_games", 3))
MIN_BUY_IN = int(getattr(config, "texas_holdem_min_buy_in", 100))
MAX_BUY_IN = int(getattr(config, "texas_holdem_max_buy_in", 10000))
TIMEOUT_DURATION = int(getattr(config, "texas_holdem_timeout", 30))


async def handle_player_timeout(group_id: str, user_id: str):
    """
    处理玩家操作超时

    Args:
        group_id: 群号
        user_id: 用户QQ号
    """
    game = game_manager.get_player_game(group_id, user_id)
    if not game or game.finished:
        return

    # 执行自动弃牌
    msg = game.auto_fold(user_id)

    if msg:
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


# ============== 创建游戏 ==============
texas_create = on_command("德扑", aliases={"德州扑克", "texasholdem"}, priority=5, block=True)


@texas_create.handle()
@require_fun_group()
async def handle_texas_create(event: GroupMessageEvent, args: Message = CommandArg()):
    """创建德州扑克游戏"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户昵称
    try:
        user_info = await event.bot.get_group_member_info(
            group_id=event.group_id,
            user_id=event.user_id
        )
        user_name = user_info.get("card") or user_info.get("nickname", f"用户{user_id}")
    except:
        user_name = f"用户{user_id}"

    # 检查是否已经在游戏中
    existing_game = game_manager.get_player_game(group_id, user_id)
    if existing_game:
        await texas_create.finish("你已经在一个游戏中了！")

    # 解析参数：买入 小盲 大盲 [最大人数]
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await texas_create.finish(
            "用法：/德扑 <买入> <小盲> <大盲> [最大人数]\n"
            f"示例：/德扑 1000 50 100 6\n"
            f"买入范围：{MIN_BUY_IN}-{MAX_BUY_IN}\n"
            f"最大人数：2-9"
        )

    parts = arg_text.split()
    if len(parts) < 3:
        await texas_create.finish(
            "参数不足！\n"
            "用法：/德扑 <买入> <小盲> <大盲> [最大人数]\n"
            f"示例：/德扑 1000 50 100 6"
        )

    try:
        buy_in = int(parts[0])
        small_blind = int(parts[1])
        big_blind = int(parts[2])
        max_players = int(parts[3]) if len(parts) > 3 else 6
    except ValueError:
        await texas_create.finish("参数必须是数字！")

    # 验证参数
    if buy_in < MIN_BUY_IN or buy_in > MAX_BUY_IN:
        await texas_create.finish(f"买入金额必须在 {MIN_BUY_IN}-{MAX_BUY_IN} 之间！")

    if small_blind <= 0 or big_blind <= 0:
        await texas_create.finish("盲注必须大于0！")

    if big_blind <= small_blind:
        await texas_create.finish("大盲注必须大于小盲注！")

    if max_players < 2 or max_players > 9:
        await texas_create.finish("最大人数必须在 2-9 之间！")

    # 检查积分
    points = points_manager.get_points(group_id, user_id)
    if points < buy_in:
        await texas_create.finish(f"积分不足！需要 {buy_in} 积分，当前只有 {points} 积分。")

    # 检查并发游戏数
    if MAX_CONCURRENT_GAMES > 0:
        active_games_count = game_manager.get_active_games_count(group_id)
        if active_games_count >= MAX_CONCURRENT_GAMES:
            await texas_create.finish(f"当前游戏数量已达上限({MAX_CONCURRENT_GAMES})！请等待游戏结束后再创建。")

    # 创建游戏
    success, game_id, msg = game_manager.create_game(
        group_id, user_id, user_name, buy_in, small_blind, big_blind, max_players
    )

    if success:
        # 设置超时回调
        game = game_manager.get_game(group_id, game_id)
        if game:
            game.timeout_callback = handle_player_timeout
            game.timeout_duration = TIMEOUT_DURATION

    await texas_create.finish(msg)


# ============== 加入游戏 ==============
texas_join = on_command("加入德扑", aliases={"加入德州扑克", "jointexas"}, priority=5, block=True)


@texas_join.handle()
@require_fun_group()
async def handle_texas_join(event: GroupMessageEvent, args: Message = CommandArg()):
    """加入德州扑克游戏"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 获取用户昵称
    try:
        user_info = await event.bot.get_group_member_info(
            group_id=event.group_id,
            user_id=event.user_id
        )
        user_name = user_info.get("card") or user_info.get("nickname", f"用户{user_id}")
    except:
        user_name = f"用户{user_id}"

    # 检查是否已经在游戏中
    existing_game = game_manager.get_player_game(group_id, user_id)
    if existing_game:
        await texas_join.finish("你已经在一个游戏中了！")

    # 解析游戏ID
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await texas_join.finish("用法：/加入德扑 <游戏ID>")

    try:
        game_id = int(arg_text)
    except ValueError:
        await texas_join.finish("游戏ID必须是数字！")

    # 获取游戏
    game = game_manager.get_game(group_id, game_id)
    if not game:
        await texas_join.finish(f"游戏 {game_id} 不存在！")

    # 加入游戏
    success, msg = game.add_player(user_id, user_name)
    await texas_join.finish(msg)


# ============== 开始游戏 ==============
texas_start = on_command("开始德扑", aliases={"开始德州扑克", "starttexas"}, priority=5, block=True)


@texas_start.handle()
@require_fun_group()
async def handle_texas_start(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """开始德州扑克游戏"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 解析游戏ID
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await texas_start.finish("用法：/开始德扑 <游戏ID>")

    try:
        game_id = int(arg_text)
    except ValueError:
        await texas_start.finish("游戏ID必须是数字！")

    # 获取游戏
    game = game_manager.get_game(group_id, game_id)
    if not game:
        await texas_start.finish(f"游戏 {game_id} 不存在！")

    # 检查是否是创建者
    if game.creator_id != user_id:
        await texas_start.finish("只有创建者才能开始游戏！")

    # 开始游戏
    msg = game.start_game()
    await texas_start.send(parse_at_message(msg))

    # 自动给所有玩家发送手牌
    for player in game.players:
        if player.hole_cards:
            hole_str = " ".join(str(card) for card in player.hole_cards)
            hand_msg = f"🎮 德州扑克游戏开始！\n🃏 你的手牌：{hole_str}"

            try:
                await bot.send_private_msg(
                    user_id=int(player.user_id),
                    group_id=event.group_id,
                    message=hand_msg
                )
            except Exception as e:
                logger.error(f"发送手牌给玩家 {player.user_id} 失败: {e}")


# ============== 游戏列表 ==============
texas_list = on_command("德扑列表", aliases={"德州扑克列表", "texaslist"}, priority=5, block=True)


@texas_list.handle()
@require_fun_group()
async def handle_texas_list(bot: Bot, event: GroupMessageEvent):
    """查看等待中的德州扑克游戏"""
    group_id = str(event.group_id)

    waiting_games = game_manager.get_waiting_games(group_id)

    if not waiting_games:
        await texas_list.finish("当前没有等待中的游戏！\n使用 /德扑 创建新游戏")

    msg = "🎮 等待中的德州扑克游戏：\n"
    msg += "━━━━━━━━━━━━━━\n"

    for game_id, game in waiting_games:
        msg += f"游戏 {game_id}:\n"
        msg += f"  买入: {game.buy_in} | 盲注: {game.small_blind}/{game.big_blind}\n"
        msg += f"  人数: {len(game.players)}/{game.max_players}\n"
        msg += f"  创建者: {game.creator_name}\n"
        msg += f"  加入命令: /加入德扑 {game_id}\n"
        msg += "━━━━━━━━━━━━━━\n"

    await texas_list.finish(msg)


# ============== 取消游戏 ==============
texas_cancel = on_command("取消德扑", aliases={"取消德州扑克", "canceltexas"}, priority=5, block=True)


@texas_cancel.handle()
@require_fun_group()
async def handle_texas_cancel(event: GroupMessageEvent, args: Message = CommandArg()):
    """取消德州扑克游戏"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 解析游戏ID
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await texas_cancel.finish("用法：/取消德扑 <游戏ID>")

    try:
        game_id = int(arg_text)
    except ValueError:
        await texas_cancel.finish("游戏ID必须是数字！")

    # 获取游戏
    game = game_manager.get_game(group_id, game_id)
    if not game:
        await texas_cancel.finish(f"游戏 {game_id} 不存在！")

    # 检查是否是创建者
    if game.creator_id != user_id:
        await texas_cancel.finish("只有创建者才能取消游戏！")

    # 检查游戏是否已开始
    if game.started:
        await texas_cancel.finish("游戏已经开始，无法取消！")

    # 返还所有玩家的积分
    for player in game.players:
        points_manager.add_points(group_id, player.user_id, game.buy_in)

    # 移除游戏
    game_manager.remove_game(group_id, game_id)

    await texas_cancel.finish(f"游戏 {game_id} 已取消，积分已返还。")


# ============== 弃牌 ==============
fold_cmd = on_command("弃牌", aliases={"fold"}, priority=5, block=True)


@fold_cmd.handle()
@require_fun_group()
async def handle_fold(event: GroupMessageEvent):
    """弃牌"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await fold_cmd.finish("你不在任何游戏中！")

    msg = game.fold(user_id)
    await fold_cmd.send(parse_at_message(msg))


# ============== 过牌 ==============
check_cmd = on_command("过牌", aliases={"check"}, priority=5, block=True)


@check_cmd.handle()
@require_fun_group()
async def handle_check(event: GroupMessageEvent):
    """过牌"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await check_cmd.finish("你不在任何游戏中！")

    msg = game.check(user_id)
    await check_cmd.send(parse_at_message(msg))


# ============== 跟注 ==============
call_cmd = on_command("跟注", aliases={"call"}, priority=5, block=True)


@call_cmd.handle()
@require_fun_group()
async def handle_call(event: GroupMessageEvent):
    """跟注"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await call_cmd.finish("你不在任何游戏中！")

    msg = game.call(user_id)
    await call_cmd.send(parse_at_message(msg))


# ============== 加注 ==============
raise_cmd = on_command("加注", aliases={"raise", "bet"}, priority=5, block=True)


@raise_cmd.handle()
@require_fun_group()
async def handle_raise(event: GroupMessageEvent, args: Message = CommandArg()):
    """加注"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await raise_cmd.finish("你不在任何游戏中！")

    # 解析加注金额
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await raise_cmd.finish("用法：/加注 <金额>\n示例：/加注 200")

    try:
        amount = int(arg_text)
    except ValueError:
        await raise_cmd.finish("金额必须是数字！")

    if amount <= 0:
        await raise_cmd.finish("金额必须大于0！")

    msg = game.raise_bet(user_id, amount)
    await raise_cmd.send(parse_at_message(msg))


# ============== 全下 ==============
allin_cmd = on_command("allin", aliases={"全押", "梭哈"}, priority=5, block=True)


@allin_cmd.handle()
@require_fun_group()
async def handle_allin(event: GroupMessageEvent):
    """全下"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await allin_cmd.finish("你不在任何游戏中！")

    msg = game.all_in(user_id)
    await allin_cmd.send(parse_at_message(msg))


# ============== 查看手牌（私聊） ==============
show_hand = on_command("查看手牌", aliases={"showhand", "手牌"}, priority=5, block=True)


@show_hand.handle()
async def handle_show_hand(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    """查看手牌（私聊发送）"""
    user_id = str(event.user_id)

    # 确定群ID
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        game = game_manager.get_player_game(group_id, user_id)
        if not game:
            await show_hand.finish("你不在任何游戏中！")
    else:
        # 私聊消息，需要遍历查找玩家所在的游戏
        game = None
        for gid in game_manager.games:
            temp_game = game_manager.get_player_game(gid, user_id)
            if temp_game:
                game = temp_game
                group_id = gid
                break

        if not game:
            await show_hand.finish("你不在任何游戏中！")

    # 查找玩家
    player = None
    for p in game.players:
        if p.user_id == user_id:
            player = p
            break

    if not player:
        await show_hand.finish("你不在任何游戏中！")

    if not player.hole_cards:
        await show_hand.finish("还没有发牌！")

    # 构建手牌消息
    hole_str = " ".join(str(card) for card in player.hole_cards)
    msg = f"🃏 你的手牌：{hole_str}"

    # 如果有公共牌，显示当前最佳牌型
    if len(game.community_cards) >= 3:
        from .hand_evaluator import HandEvaluator
        rank, values, best_cards = HandEvaluator.evaluate_best_hand(
            player.hole_cards,
            game.community_cards.get_cards()
        )
        hand_desc = HandEvaluator.get_hand_description(rank, values, best_cards)
        msg += f"\n📊 当前牌型：{hand_desc}"

    # 私聊或临时会话发送
    try:
        if isinstance(event, GroupMessageEvent):
            # 从群聊触发，发送临时会话
            await bot.send_private_msg(user_id=int(user_id), group_id=event.group_id, message=msg)
            await show_hand.finish("手牌已通过临时会话发送！")
        else:
            # 从私聊/临时会话触发，直接回复
            await show_hand.finish(msg)
    except FinishedException:
        # finish 异常正常向上传播
        raise
    except Exception as e:
        logger.error(f"发送消息失败: {e}")
        if isinstance(event, GroupMessageEvent):
            await show_hand.finish("发送临时会话失败！请确保允许机器人发送临时会话。")
        else:
            await show_hand.finish("发送消息失败！")


# ============== 底池 ==============
pot_cmd = on_command("底池", aliases={"pot", "状态"}, priority=5, block=True)


@pot_cmd.handle()
@require_fun_group()
async def handle_pot(event: GroupMessageEvent):
    """查看底池和游戏状态"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    game = game_manager.get_player_game(group_id, user_id)
    if not game:
        await pot_cmd.finish("你不在任何游戏中！")

    msg = game.get_game_status()
    await pot_cmd.finish(msg)


# ============== 德扑规则 ==============
texas_rules = on_command("德扑规则", aliases={"德州扑克规则", "texasrules"}, priority=5, block=True)


@texas_rules.handle()
async def handle_texas_rules():
    """德州扑克规则说明"""
    msg = """🎮 德州扑克游戏规则

━━━━━━━━━━━━━━
📋 基本流程：
1. 创建游戏并设置买入和盲注
2. 玩家加入游戏
3. 发2张手牌给每位玩家
4. 进行4轮下注：
   - 翻牌前（Pre-flop）
   - 翻牌（Flop，3张公共牌）
   - 转牌（Turn，1张公共牌）
   - 河牌（River，1张公共牌）
5. 摊牌比大小，最大牌型获胜

━━━━━━━━━━━━━━
🎴 牌型大小（从大到小）：
1. 皇家同花顺 - A K Q J T 同花色
2. 同花顺 - 5张连续同花色
3. 四条 - 4张相同点数
4. 葫芦 - 3张+2张相同点数
5. 同花 - 5张同花色
6. 顺子 - 5张连续点数
7. 三条 - 3张相同点数
8. 两对 - 2对相同点数
9. 一对 - 1对相同点数
10. 高牌 - 单张最大

━━━━━━━━━━━━━━
💡 游戏操作：
/弃牌 - 放弃本局
/过牌 - 不下注继续（需跟注为0）
/跟注 - 跟上当前下注
/加注 [金额] - 增加下注
/allin - 全部筹码押上

━━━━━━━━━━━━━━
⚙️ 其他命令：
/德扑列表 - 查看等待中的游戏
/查看手牌 - 私聊查看自己的牌
/底池 - 查看当前状态
"""
    await texas_rules.finish(msg)
