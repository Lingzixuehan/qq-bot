"""
戳一戳插件
功能：被戳时戳回去
"""
from nonebot import on_notice
from nonebot.adapters.onebot.v11 import Bot, PokeNotifyEvent
import random

poke = on_notice(priority=5)

@poke.handle()
async def handle_poke(bot: Bot, event: PokeNotifyEvent):
    """处理戳一戳事件"""
    # 检查是否是戳一戳事件
    if event.notice_type != "notify" or event.sub_type != "poke":
        return

    # 检查是否是戳的机器人
    if event.target_id != event.self_id:
        return

    # 随机回复消息
    responses = [
        "戳什么戳！",
        "别戳了别戳了~",
        "戳回去！",
        "你再戳！",
        "🙄",
        "哼~",
    ]

    # 发送文字回复
    await bot.send_group_msg(
        group_id=event.group_id,
        message=random.choice(responses)
    )

    # 戳回去
    try:
        await bot.send_group_msg(
            group_id=event.group_id,
            message=f"[CQ:poke,qq={event.user_id}]"
        )
    except:
        # 如果戳回去失败，就不管了
        pass
