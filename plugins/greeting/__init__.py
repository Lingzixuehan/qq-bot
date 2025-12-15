"""
早安晚安插件
根据时间段回复不同内容
"""
import random
from datetime import datetime

from nonebot import on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message
from nonebot.rule import to_me

# 使用 to_me() 规则检测是否被@
greeting = on_message(rule=to_me(), priority=10, block=False)


def get_time_period() -> str:
    """获取当前时间段"""
    hour = datetime.now().hour
    if 5 <= hour < 11:
        return "morning"  # 早上
    elif 11 <= hour < 13:
        return "noon"  # 中午
    elif 13 <= hour < 18:
        return "afternoon"  # 下午
    elif 18 <= hour < 23:
        return "evening"  # 晚上
    else:
        return "night"  # 深夜


@greeting.handle()
async def handle_greeting(event: GroupMessageEvent):
    """处理早安晚安消息"""
    text = event.get_plaintext().strip()

    # 检查是否包含早安或晚安
    is_good_morning = "早安" in text or "早上好" in text or "ohayo" in text.lower()
    is_good_night = "晚安" in text or "晚上好" in text or "oyasumi" in text.lower()

    if not is_good_morning and not is_good_night:
        return  # 不是早安或晚安，不处理

    time_period = get_time_period()

    # 早安回复逻辑
    if is_good_morning:
        if time_period == "morning":
            # 早上说早安 - 正常
            responses = [
                "早安！今天也要元气满满哦~",
                "早上好！新的一天开始啦！",
                "早安早安！祝你今天好心情！",
                "おはよう！（早安）",
            ]
        elif time_period == "noon":
            # 中午说早安 - 有点晚
            responses = [
                "这都中午了，起得有点晚哦~",
                "中午才起来吗？懒虫！",
                "虽然有点晚，但还是早安~",
                "都要吃午饭了才说早安...",
            ]
        elif time_period == "afternoon":
            # 下午说早安 - 太晚了
            responses = [
                "都下午了还早安？起太晚啦！",
                "这个点起床？！注意身体啊！",
                "下午好才对吧...起得也太晚了",
                "早安？太阳都要下山了！",
            ]
        elif time_period == "evening":
            # 晚上说早安 - 异常
            responses = [
                "晚上说早安？你是不是搞错了什么...",
                "应该说晚上好吧？",
                "这都晚上了，你刚起床吗？！",
                "早安？现在是晚上啦！",
            ]
        else:  # night
            # 深夜说早安 - 太早或太晚
            responses = [
                "深夜说早安...你是准备熬夜还是刚起床？",
                "现在这个点？去睡觉！",
                "半夜三更说早安，作息很乱啊",
                "太早了吧...还是太晚了？",
            ]

        await greeting.finish(random.choice(responses))

    # 晚安回复逻辑
    if is_good_night:
        if time_period == "evening" or time_period == "night":
            # 晚上/深夜说晚安 - 正常
            responses = [
                "晚安~做个好梦哦！",
                "晚安晚安，明天见~",
                "おやすみ~（晚安）",
                "晚安，好好休息！",
                "晚安~睡个好觉！",
            ]
        elif time_period == "morning":
            # 早上说晚安 - 异常
            responses = [
                "早上说晚安？你要睡回笼觉吗？",
                "现在是早上啊...该起床了！",
                "刚起床就要睡？",
                "早上说晚安是什么操作...",
            ]
        elif time_period == "noon":
            # 中午说晚安 - 午睡
            responses = [
                "中午睡个午觉也不错~",
                "要睡午觉吗？晚安~",
                "午安~睡个好觉",
                "中午说晚安，是要午休吗？",
            ]
        else:  # afternoon
            # 下午说晚安 - 太早
            responses = [
                "这才下午就要睡了？太早了吧！",
                "现在睡的话晚上会睡不着哦",
                "下午就晚安？你是有多困...",
                "还这么早，再坚持一下吧！",
            ]

        await greeting.finish(random.choice(responses))
