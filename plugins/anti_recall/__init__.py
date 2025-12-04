"""
防撤回插件
功能：
- 监听群消息撤回事件
- 将被撤回的消息重新发送到群里
- 支持文本、图片、表情等多种消息类型
"""
from nonebot import on_notice, on_message
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupRecallNoticeEvent,
    Message,
    MessageSegment,
)
from collections import OrderedDict
from datetime import datetime
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))

# 消息缓存：存储最近的消息
# 格式：{message_id: {"user_id": xx, "user_name": xx, "message": xx, "time": xx, "group_id": xx}}
message_cache = OrderedDict()
MAX_CACHE_SIZE = 1000  # 最多缓存1000条消息


# 监听所有群消息，缓存起来
cache_msg = on_message(priority=1, block=False)

@cache_msg.handle()
async def handle_cache_message(bot: Bot, event: GroupMessageEvent):
    """缓存群消息"""
    message_id = event.message_id
    user_id = str(event.user_id)
    user_name = event.sender.card or event.sender.nickname or str(user_id)
    group_id = str(event.group_id)

    # 缓存消息内容
    message_cache[message_id] = {
        "user_id": user_id,
        "user_name": user_name,
        "message": event.message,
        "time": datetime.now(),
        "group_id": group_id,
    }

    # 限制缓存大小
    if len(message_cache) > MAX_CACHE_SIZE:
        message_cache.popitem(last=False)  # 删除最旧的消息


# 监听撤回事件
recall_notice = on_notice(priority=5)

@recall_notice.handle()
async def handle_recall(bot: Bot, event: GroupRecallNoticeEvent):
    """处理撤回事件"""
    # 检查是否是群消息撤回事件
    if event.notice_type != "group_recall":
        return

    message_id = event.message_id
    operator_id = event.operator_id
    user_id = event.user_id
    group_id = str(event.group_id)

    # 从缓存中查找被撤回的消息
    if message_id not in message_cache:
        # 消息不在缓存中（可能是机器人启动前的消息）
        await recall_notice.finish()
        return

    msg_data = message_cache[message_id]

    # 检查是否是同一个群的消息
    if msg_data["group_id"] != group_id:
        await recall_notice.finish()
        return

    # 获取撤回者信息
    if operator_id == user_id:
        operator_info = "自己"
    else:
        try:
            operator_member = await bot.get_group_member_info(
                group_id=int(group_id),
                user_id=operator_id
            )
            operator_name = operator_member.get("card") or operator_member.get("nickname", str(operator_id))
            operator_info = f"{operator_name}(管理员)"
        except:
            operator_info = f"{operator_id}(管理员)"

    # 构建提示消息
    recall_time = datetime.now()
    time_diff = (recall_time - msg_data["time"]).total_seconds()

    hint = f"🔔 {msg_data['user_name']} 撤回了一条消息\n"
    hint += f"撤回者：{operator_info}\n"
    hint += f"撤回时间：{time_diff:.1f}秒后\n"
    hint += f"{'='*30}\n"
    hint += "撤回的内容：\n"

    # 构建完整消息
    result_msg = Message(hint)

    # 添加原消息内容
    original_msg = msg_data["message"]

    # 处理消息内容
    if not original_msg:
        result_msg += "[空消息]"
    else:
        # 检查消息类型并处理
        has_content = False
        for seg in original_msg:
            if seg.type == "text":
                result_msg += seg
                has_content = True
            elif seg.type == "image":
                result_msg += seg
                has_content = True
            elif seg.type == "face":
                result_msg += seg
                has_content = True
            elif seg.type == "at":
                result_msg += seg
                has_content = True
            elif seg.type == "reply":
                # 跳过回复类型，不显示
                continue
            else:
                # 其他类型消息
                result_msg += MessageSegment.text(f"[{seg.type}消息]")
                has_content = True

        if not has_content:
            result_msg += "[不支持的消息类型]"

    # 发送消息
    try:
        await bot.send_group_msg(
            group_id=int(group_id),
            message=result_msg
        )
    except Exception as e:
        print(f"发送防撤回消息失败: {e}")

    # 从缓存中删除该消息
    del message_cache[message_id]

    await recall_notice.finish()
