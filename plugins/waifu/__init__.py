"""
群老婆插件
功能：
- 抽老婆：每日随机抽取一位群友作为老婆
- 查老婆：查看今日老婆
- 每日0点重置
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
import sys
from pathlib import Path
import random

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))
from common.database import WaifuDB, init_db

# 初始化数据库
import asyncio
asyncio.create_task(init_db())


# 抽老婆
draw_waifu = on_command("抽老婆", aliases={"娶老婆", "今日老婆"}, priority=5)

@draw_waifu.handle()
async def handle_draw_waifu(bot: Bot, event: GroupMessageEvent):
    """抽老婆"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 检查今天是否已经抽过
    existing = await WaifuDB.get_waifu(group_id, user_id)
    if existing:
        msg = f"你今天的老婆是：{MessageSegment.at(existing['waifu_id'])}\n"
        msg += "💕 今天已经抽过了哦，明天再来吧！"
        await draw_waifu.finish(msg)
        return

    # 获取群成员列表
    try:
        member_list = await bot.get_group_member_list(group_id=event.group_id)
    except Exception as e:
        await draw_waifu.finish(f"获取群成员列表失败：{e}")
        return

    if not member_list:
        await draw_waifu.finish("获取群成员列表为空")
        return

    # 过滤掉自己和机器人
    bot_id = str(event.self_id)
    available_members = [
        m for m in member_list
        if str(m["user_id"]) != user_id and str(m["user_id"]) != bot_id
    ]

    if not available_members:
        await draw_waifu.finish("群里没有其他人了...")
        return

    # 随机抽取
    waifu = random.choice(available_members)
    waifu_id = str(waifu["user_id"])
    waifu_name = waifu.get("card") or waifu.get("nickname", waifu_id)

    # 检查是否已被其他人抽走
    taken_by = await WaifuDB.check_waifu_taken(group_id, waifu_id)
    attempts = 0
    max_attempts = 10

    while taken_by and taken_by != user_id and attempts < max_attempts:
        # 重新抽取
        waifu = random.choice(available_members)
        waifu_id = str(waifu["user_id"])
        waifu_name = waifu.get("card") or waifu.get("nickname", waifu_id)
        taken_by = await WaifuDB.check_waifu_taken(group_id, waifu_id)
        attempts += 1

    # 保存到数据库
    await WaifuDB.set_waifu(group_id, user_id, waifu_id, waifu_name)

    # 构建消息
    messages = [
        "💝 恭喜你抽到了今天的老婆！",
        "🎉 抽老婆成功！",
        "💕 今天的缘分是...",
        "✨ 命运的红线牵引着你们...",
    ]

    msg = random.choice(messages)
    msg += f"\n\n{MessageSegment.at(waifu_id)}\n"
    msg += f"💖 {waifu_name} 💖\n"
    msg += "记得好好对待你的老婆哦～"

    await draw_waifu.finish(msg)


# 查看老婆
check_waifu = on_command("查老婆", aliases={"我的老婆", "老婆是谁"}, priority=5)

@check_waifu.handle()
async def handle_check_waifu(event: GroupMessageEvent):
    """查看今日老婆"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    waifu = await WaifuDB.get_waifu(group_id, user_id)

    if waifu:
        msg = f"你今天的老婆是：\n{MessageSegment.at(waifu['waifu_id'])}\n"
        msg += f"💖 {waifu['waifu_name']} 💖"
        await check_waifu.finish(msg)
    else:
        await check_waifu.finish("你还没有抽老婆哦，快发送 /抽老婆 来抽一位吧！")
