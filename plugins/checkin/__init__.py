"""
签到插件
功能：
- 每日签到
- 查看签到信息
- 签到排行榜
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))
from common.database import CheckinDB, init_db

# 初始化数据库
import asyncio
asyncio.create_task(init_db())


# 签到
checkin = on_command("签到", aliases={"打卡", "每日签到"}, priority=5)

@checkin.handle()
async def handle_checkin(event: GroupMessageEvent):
    """签到"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)
    user_name = event.sender.card or event.sender.nickname or str(user_id)

    success, days = await CheckinDB.checkin(group_id, user_id, user_name)

    if success:
        # 根据连续天数给予不同的回复
        if days == 1:
            msg = "✅ 签到成功！\n🎉 这是你的第 1 天签到"
        elif days < 7:
            msg = f"✅ 签到成功！\n🔥 已连续签到 {days} 天"
        elif days < 30:
            msg = f"✅ 签到成功！\n⭐ 已连续签到 {days} 天，坚持得不错！"
        elif days < 100:
            msg = f"✅ 签到成功！\n💎 已连续签到 {days} 天，你真是太厉害了！"
        else:
            msg = f"✅ 签到成功！\n👑 已连续签到 {days} 天，签到王者非你莫属！"

        await checkin.finish(msg)
    else:
        await checkin.finish("⚠️ 你今天已经签到过了哦，明天再来吧！")


# 查看签到信息
checkin_info = on_command("签到信息", aliases={"我的签到", "签到记录"}, priority=5)

@checkin_info.handle()
async def handle_checkin_info(event: GroupMessageEvent):
    """查看签到信息"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    info = await CheckinDB.get_user_checkin_info(group_id, user_id)

    if info:
        if info["is_today"]:
            msg = f"📊 你的签到信息：\n"
            msg += f"✅ 今日已签到\n"
            msg += f"🔥 连续签到：{info['continuous_days']} 天"
        else:
            msg = f"📊 你的签到信息：\n"
            msg += f"❌ 今日未签到\n"
            msg += f"📅 上次连续签到：{info['continuous_days']} 天\n"
            msg += f"（签到已中断，重新签到将从第1天开始计算）"
        await checkin_info.finish(msg)
    else:
        await checkin_info.finish("你还没有签到记录哦，快发送 /签到 来签到吧！")


# 签到排行榜
checkin_rank = on_command("签到排行", aliases={"签到榜", "签到排行榜"}, priority=5)

@checkin_rank.handle()
async def handle_checkin_rank(bot: Bot, event: GroupMessageEvent):
    """签到排行榜"""
    group_id = str(event.group_id)

    ranks = await CheckinDB.get_group_checkin_rank(group_id, limit=10)

    if not ranks:
        await checkin_rank.finish("今天还没有人签到哦")
        return

    msg = "📊 今日签到排行榜 TOP10\n" + "=" * 25 + "\n\n"

    medals = ["🥇", "🥈", "🥉"]
    for idx, rank in enumerate(ranks):
        medal = medals[idx] if idx < 3 else f"{idx + 1}."
        msg += f"{medal} {rank['user_name']}\n"
        msg += f"   连续签到：{rank['days']} 天\n\n"

    await checkin_rank.finish(msg.strip())
