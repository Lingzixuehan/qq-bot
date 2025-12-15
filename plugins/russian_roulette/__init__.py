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

    # 移动到下一个位置
    game["current"] = (current_pos + 1) % game["capacity"]

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
            await bot.send_group_msg(
                group_id=event.group_id,
                message=f"⚠️ 禁言执行失败：{str(e)[:50]}"
            )

    else:
        # 没中弹，安全
        remaining_bullets = game["bullets"]
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
    """结束当前游戏（仅管理员）"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    if group_id not in active_games:
        await end_game.finish("当前没有进行中的游戏！")

    # 检查权限：群主或管理员
    try:
        member_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=int(user_id)
        )
        role = member_info.get("role", "member")
        if role not in ["owner", "admin"]:
            await end_game.finish("❌ 只有管理员才能结束游戏！")
    except:
        await end_game.finish("❌ 获取权限信息失败")

    # 结束游戏
    active_games.pop(group_id, None)
    await end_game.finish("🛑 游戏已被管理员终止")
