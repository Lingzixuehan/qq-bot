"""
@回复插件
功能：被@但没有有效输入时回复
"""
from nonebot import on_message
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.rule import to_me
import random

# 使用 to_me() 规则来检测是否被@
# priority=99 确保这个处理器在其他命令处理器之后执行
# block=False 不阻断其他处理器
at_me = on_message(rule=to_me(), priority=99, block=False)

@at_me.handle()
async def handle_at_me(event: GroupMessageEvent):
    """处理被@但没有有效输入的情况"""
    # 获取纯文本内容
    text = event.get_plaintext().strip()

    # 如果没有文本内容，或者只有空格，就回复
    if not text:
        responses = [
            "干嘛......",
            "嗯？",
            "有事吗？",
            "叫我干嘛~",
            "？",
            "怎么了？",
        ]
        await at_me.finish(random.choice(responses))
