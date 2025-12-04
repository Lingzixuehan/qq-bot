"""
投骰子插件
功能：
- 基础投骰子：/roll 或 /投骰子 - 投一个6面骰子
- 指定面数：/roll 20 - 投一个20面骰子
- 多个骰子：/roll 3d6 - 投3个6面骰子并求和
- 详细模式：/roll 3d6 详细 - 显示每个骰子的点数
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.params import CommandArg
import random
import re


# 投骰子命令
roll_dice = on_command("roll", aliases={"投骰子", "掷骰子", "扔骰子"}, priority=5)


@roll_dice.handle()
async def handle_roll_dice(event: GroupMessageEvent, args: Message = CommandArg()):
    """投骰子"""
    arg_text = args.extract_plain_text().strip()
    user_name = event.sender.card or event.sender.nickname or str(event.user_id)

    # 默认投一个6面骰子
    if not arg_text:
        result = random.randint(1, 6)
        msg = f"🎲 {user_name} 投掷了一个骰子\n"
        msg += f"结果：{result} 点"
        await roll_dice.finish(msg)
        return

    # 检查是否要求详细模式
    verbose = "详细" in arg_text
    arg_text = arg_text.replace("详细", "").strip()

    # 匹配 XdY 格式 (如 3d6, 2d20)
    match = re.match(r'^(\d+)d(\d+)$', arg_text.lower())
    if match:
        count = int(match.group(1))
        sides = int(match.group(2))

        # 限制骰子数量和面数
        if count < 1 or count > 100:
            await roll_dice.finish("骰子数量必须在 1-100 之间")
            return

        if sides < 2 or sides > 10000:
            await roll_dice.finish("骰子面数必须在 2-10000 之间")
            return

        # 投掷骰子
        results = [random.randint(1, sides) for _ in range(count)]
        total = sum(results)

        msg = f"🎲 {user_name} 投掷了 {count} 个 {sides} 面骰子\n"

        if verbose or count <= 10:
            # 详细模式或骰子数量较少时显示每个结果
            dice_str = " + ".join(str(r) for r in results)
            msg += f"结果：{dice_str}\n"
            msg += f"总和：{total} 点"
        else:
            # 骰子太多只显示总和
            msg += f"总和：{total} 点"
            msg += f"\n（发送 /roll {count}d{sides} 详细 查看每个骰子的点数）"

        await roll_dice.finish(msg)
        return

    # 匹配单个数字 (如 20, 表示投一个20面骰子)
    try:
        sides = int(arg_text)
        if sides < 2 or sides > 10000:
            await roll_dice.finish("骰子面数必须在 2-10000 之间")
            return

        result = random.randint(1, sides)
        msg = f"🎲 {user_name} 投掷了一个 {sides} 面骰子\n"
        msg += f"结果：{result} 点"
        await roll_dice.finish(msg)
        return

    except ValueError:
        # 格式错误
        await roll_dice.finish(
            "使用方法：\n"
            "/roll - 投一个6面骰子\n"
            "/roll 20 - 投一个20面骰子\n"
            "/roll 3d6 - 投3个6面骰子\n"
            "/roll 3d6 详细 - 显示每个骰子的点数"
        )


# 快捷命令：常用骰子
d6 = on_command("d6", priority=5)
d20 = on_command("d20", priority=5)
d100 = on_command("d100", priority=5)


@d6.handle()
async def handle_d6(event: GroupMessageEvent):
    """投一个6面骰子（快捷命令）"""
    user_name = event.sender.card or event.sender.nickname or str(event.user_id)
    result = random.randint(1, 6)
    msg = f"🎲 {user_name} 投掷了一个6面骰子\n"
    msg += f"结果：{result} 点"
    await d6.finish(msg)


@d20.handle()
async def handle_d20(event: GroupMessageEvent):
    """投一个20面骰子（快捷命令）"""
    user_name = event.sender.card or event.sender.nickname or str(event.user_id)
    result = random.randint(1, 20)
    msg = f"🎲 {user_name} 投掷了一个20面骰子\n"
    msg += f"结果：{result} 点"

    # 大成功/大失败提示
    if result == 20:
        msg += " 🎉 大成功！"
    elif result == 1:
        msg += " 💀 大失败！"

    await d20.finish(msg)


@d100.handle()
async def handle_d100(event: GroupMessageEvent):
    """投一个百面骰子（快捷命令）"""
    user_name = event.sender.card or event.sender.nickname or str(event.user_id)
    result = random.randint(1, 100)
    msg = f"🎲 {user_name} 投掷了一个100面骰子\n"
    msg += f"结果：{result} 点"

    # 幸运提示
    if result >= 95:
        msg += " 🎉 非常幸运！"
    elif result <= 5:
        msg += " 💀 非常不幸！"

    await d100.finish(msg)


# 猜大小游戏
guess_dice = on_command("猜大小", aliases={"猜骰子"}, priority=5)


@guess_dice.handle()
async def handle_guess_dice(event: GroupMessageEvent, args: Message = CommandArg()):
    """猜大小游戏"""
    arg_text = args.extract_plain_text().strip().lower()
    user_name = event.sender.card or event.sender.nickname or str(event.user_id)

    if not arg_text or arg_text not in ["大", "小", "big", "small"]:
        await guess_dice.finish(
            "🎲 猜大小游戏\n"
            "使用方法：/猜大小 大 或 /猜大小 小\n"
            "投掷一个骰子，4-6为大，1-3为小"
        )
        return

    # 玩家选择
    player_choice = "大" if arg_text in ["大", "big"] else "小"

    # 投骰子
    result = random.randint(1, 6)
    is_big = result >= 4

    # 判断输赢
    win = (player_choice == "大" and is_big) or (player_choice == "小" and not is_big)

    msg = f"🎲 {user_name} 猜了【{player_choice}】\n"
    msg += f"骰子结果：{result} 点 {'(大)' if is_big else '(小)'}\n"

    if win:
        msg += "🎉 恭喜你猜对了！"
    else:
        msg += "💔 很遗憾，猜错了！"

    await guess_dice.finish(msg)
