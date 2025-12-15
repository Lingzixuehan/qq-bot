"""
俄罗斯轮盘插件
一个刺激的群聊游戏
"""
import random
from typing import Dict, Optional

from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message
from nonebot.params import CommandArg
from nonebot.log import logger

# ============== 配置 ==============
driver = get_driver()
config = driver.config

# 中弹后的禁言时长（秒）
ROULETTE_BAN_DURATION = int(getattr(config, "russian_roulette_ban_duration", 60))

# 允许强制停止游戏的QQ号列表
STOP_USERS = {
    uid.strip()
    for uid in str(getattr(config, "russian_roulette_stop_users", "") or "").split(",")
    if uid.strip()
}

# ============== 游戏数据 ==============
# 游戏状态: {group_id: {"capacity": m, "bullets": n, "chambers": [bool...], "current": 0}}
active_games: Dict[str, dict] = {}


# ============== 创建游戏 ==============
start_game = on_command("俄罗斯轮盘", priority=5, block=True)


@start_game.handle()
async def handle_start_game(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """
    创建俄罗斯轮盘游戏
    命令格式：/俄罗斯轮盘 m n
    m: 弹匣容量，n: 子弹数量
    """
    group_id = str(event.group_id)

    # 检查是否已有游戏
    if group_id in active_games:
        game = active_games[group_id]
        remaining = game["bullets"]
        total = game["capacity"]
        await start_game.finish(
            f"⚠️ 当前已有进行中的游戏！\n"
            f"🔫 弹匣容量：{total}\n"
            f"💥 剩余子弹：{remaining}/{game['bullets']}\n"
            f"使用 /开枪 参与游戏"
        )

    # 解析参数
    arg_text = args.extract_plain_text().strip()
    if not arg_text:
        await start_game.finish(
            "用法：/俄罗斯轮盘 <弹匣容量> <子弹数量>\n"
            "示例：/俄罗斯轮盘 6 1\n"
            "创建一个6发弹匣装1发子弹的游戏"
        )

    try:
        parts = arg_text.split()
        if len(parts) != 2:
            raise ValueError("参数数量错误")

        capacity = int(parts[0])
        bullets = int(parts[1])

        # 验证参数
        if capacity < 1 or capacity > 20:
            await start_game.finish("❌ 弹匣容量必须在 1-20 之间！")
        if bullets < 1 or bullets > capacity:
            await start_game.finish("❌ 子弹数量必须在 1 到弹匣容量之间！")

    except (ValueError, IndexError):
        await start_game.finish(
            "❌ 参数格式错误！\n"
            "用法：/俄罗斯轮盘 <弹匣容量> <子弹数量>\n"
            "示例：/俄罗斯轮盘 6 1"
        )

    # 创建弹匣：随机放置子弹
    chambers = [False] * capacity
    bullet_positions = random.sample(range(capacity), bullets)
    for pos in bullet_positions:
        chambers[pos] = True

    # 保存游戏状态
    active_games[group_id] = {
        "capacity": capacity,
        "bullets": bullets,
        "chambers": chambers,
        "current": 0,  # 当前弹匣位置
        "total_bullets": bullets,  # 总子弹数
        "fired_positions": set(),  # 已经打过的位置
    }

    await start_game.finish(
        f"🎲 俄罗斯轮盘游戏开始！\n"
        f"━━━━━━━━━━━━━━\n"
        f"🔫 弹匣容量：{capacity}\n"
        f"💥 子弹数量：{bullets}\n"
        f"⏱️ 中弹禁言：{ROULETTE_BAN_DURATION}秒\n"
        f"━━━━━━━━━━━━━━\n"
        f"使用 /开枪 来试试运气吧！"
    )


# ============== 开枪 ==============
shoot = on_command("开枪", aliases={"bang", "shoot"}, priority=5, block=True)


@shoot.handle()
async def handle_shoot(bot: Bot, event: GroupMessageEvent):
    """开枪判定"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 检查游戏是否存在
    if group_id not in active_games:
        await shoot.finish("当前没有进行中的游戏！\n使用 /俄罗斯轮盘 <容量> <子弹> 来创建游戏")

    game = active_games[group_id]
    current_pos = game["current"]
    is_bullet = game["chambers"][current_pos]

    # 记录这个位置已经打过
    game["fired_positions"].add(current_pos)

    # 移动到下一个位置
    game["current"] = (current_pos + 1) % game["capacity"]

    # 检查剩余弹匣是否全是子弹
    def check_all_bullets_remaining():
        """检查剩余未打过的位置是否全是子弹"""
        fired = game["fired_positions"]
        remaining_bullets = 0
        remaining_total = 0

        # 统计未打过的位置中有多少子弹
        for i in range(game["capacity"]):
            if i not in fired:  # 这个位置还没打过
                remaining_total += 1
                if game["chambers"][i]:  # 这个位置有子弹
                    remaining_bullets += 1

        # 如果剩余位置数 > 0 且全是子弹，返回 True
        return remaining_total > 0 and remaining_bullets == remaining_total and remaining_bullets == game["bullets"]

    if is_bullet:
        # 中弹！
        game["bullets"] -= 1
        remaining_bullets = game["bullets"]

        # 构建消息
        result_msg = (
            f"💥 BANG! \n"
            f"━━━━━━━━━━━━━━\n"
            f"💀 中弹了！\n"
            f"🔇 禁言 {ROULETTE_BAN_DURATION} 秒\n"
        )

        if remaining_bullets > 0:
            result_msg += f"💥 剩余子弹：{remaining_bullets}/{game['total_bullets']}\n游戏继续..."
        else:
            result_msg += f"🎉 所有子弹已打完，游戏结束！"
            # 游戏结束，清理状态
            active_games.pop(group_id, None)

        await bot.send_group_msg(group_id=event.group_id, message=result_msg)

        # 执行禁言
        try:
            await bot.set_group_ban(
                group_id=event.group_id,
                user_id=int(user_id),
                duration=ROULETTE_BAN_DURATION
            )
        except Exception as e:
            logger.error(f"禁言失败: {e}")
            # 幽默的异常处理
            error_msg = str(e).lower()
            if "owner" in error_msg or "群主" in error_msg or "权限" in error_msg:
                funny_responses = [
                    "⚠️ 对方是老资历，哎我服了真的是老六",
                    "⚠️ 群主大人中弹了...可惜我禁言不了大佬",
                    "⚠️ 想禁言群主？我可不敢，怕被踢出群",
                    "⚠️ 禁言失败！对方段位太高了",
                ]
            else:
                funny_responses = [
                    "⚠️ 禁言失败！可能是权限不足",
                    "⚠️ 想禁言但是失败了，尴尬...",
                    "⚠️ 禁言操作被拦截，对方有保护罩",
                ]
            await bot.send_group_msg(
                group_id=event.group_id,
                message=random.choice(funny_responses)
            )

    else:
        # 没中弹，安全
        remaining_bullets = game["bullets"]

        # 检查剩余弹匣是否全是子弹
        if remaining_bullets > 0 and check_all_bullets_remaining():
            # 剩下的全是子弹，直接结束游戏
            active_games.pop(group_id, None)
            await shoot.finish(
                f"✅ Click...\n"
                f"━━━━━━━━━━━━━━\n"
                f"😮‍💨 这次安全！\n"
                f"⚠️ 但是...剩余 {remaining_bullets} 发全是子弹！\n"
                f"🛑 游戏强制结束，没人想继续送死吧？"
            )

        await shoot.finish(
            f"✅ Click...\n"
            f"━━━━━━━━━━━━━━\n"
            f"😮‍💨 安全！这次逃过一劫\n"
            f"💥 剩余子弹：{remaining_bullets}/{game['total_bullets']}\n"
            f"下一位勇士请继续..."
        )


# ============== 查看游戏状态 ==============
game_status = on_command("轮盘状态", aliases={"游戏状态"}, priority=5, block=True)


@game_status.handle()
async def handle_game_status(event: GroupMessageEvent):
    """查看当前游戏状态"""
    group_id = str(event.group_id)

    if group_id not in active_games:
        await game_status.finish("当前没有进行中的游戏！")

    game = active_games[group_id]
    await game_status.finish(
        f"🎲 俄罗斯轮盘游戏状态\n"
        f"━━━━━━━━━━━━━━\n"
        f"🔫 弹匣容量：{game['capacity']}\n"
        f"💥 剩余子弹：{game['bullets']}/{game['total_bullets']}\n"
        f"📍 当前位置：{game['current'] + 1}/{game['capacity']}\n"
        f"⏱️ 中弹禁言：{ROULETTE_BAN_DURATION}秒"
    )


# ============== 结束游戏 ==============
end_game = on_command("结束轮盘", aliases={"终止游戏"}, priority=5, block=True)


@end_game.handle()
async def handle_end_game(bot: Bot, event: GroupMessageEvent):
    """结束当前游戏（管理员或授权用户）"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    if group_id not in active_games:
        await end_game.finish("当前没有进行中的游戏！")

    # 检查权限：特定QQ号或群主/管理员
    has_permission = False

    # 1. 检查是否在授权用户列表中
    if user_id in STOP_USERS:
        has_permission = True
        logger.info(f"用户 {user_id} 作为授权用户终止了游戏")
    else:
        # 2. 检查是否是群主或管理员
        try:
            member_info = await bot.get_group_member_info(
                group_id=event.group_id,
                user_id=int(user_id)
            )
            role = member_info.get("role", "member")
            if role in ["owner", "admin"]:
                has_permission = True
                logger.info(f"管理员 {user_id} 终止了游戏")
        except Exception as e:
            logger.error(f"获取权限信息失败: {e}")

    if not has_permission:
        await end_game.finish("❌ 只有管理员或授权用户才能结束游戏！")

    # 结束游戏
    active_games.pop(group_id, None)
    await end_game.finish("🛑 游戏已被终止")
