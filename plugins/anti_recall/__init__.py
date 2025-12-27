"""
防撤回插件
功能：
- 监听群消息撤回事件
- 缓存撤回的消息
- 通过命令查看撤回的消息：/防撤回 或 /防撤回 @某人
"""
from nonebot import on_notice, on_message, on_command, get_driver
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    GroupRecallNoticeEvent,
    Message,
    MessageSegment,
)
from nonebot.params import CommandArg
from collections import OrderedDict
from datetime import datetime
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))

# 读取配置
driver = get_driver()
config = driver.config

# 黑名单配置：禁用防撤回功能的群
ANTI_RECALL_BLACKLIST = set()
blacklist_str = getattr(config, "anti_recall_blacklist", "")
if blacklist_str:
    # 格式：群号,群号,群号
    blacklist_str = str(blacklist_str)
    ANTI_RECALL_BLACKLIST = set(gid.strip() for gid in blacklist_str.split(",") if gid.strip())

# 消息缓存：存储最近的消息
# 格式：{message_id: {"user_id": xx, "user_name": xx, "message": xx, "time": xx, "group_id": xx}}
message_cache = OrderedDict()
MAX_CACHE_SIZE = 1000  # 最多缓存1000条消息

# 撤回消息缓存：存储每个群最近的撤回消息
# 格式：{group_id: [{"user_id": xx, "user_name": xx, "message": xx, "time": xx, "recall_time": xx, "operator_info": xx}, ...]}
recalled_messages = {}
MAX_RECALLED_PER_GROUP = 20  # 每个群最多缓存20条撤回消息


# 监听所有群消息，缓存起来
cache_msg = on_message(priority=1, block=False)

@cache_msg.handle()
async def handle_cache_message(bot: Bot, event: GroupMessageEvent):
    """缓存群消息"""
    group_id = str(event.group_id)

    # 检查黑名单
    if group_id in ANTI_RECALL_BLACKLIST:
        return

    message_id = event.message_id
    user_id = str(event.user_id)
    user_name = event.sender.card or event.sender.nickname or str(user_id)

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
    """处理撤回事件，将撤回的消息存储起来"""
    # 检查是否是群消息撤回事件
    if event.notice_type != "group_recall":
        return

    group_id = str(event.group_id)

    # 检查黑名单
    if group_id in ANTI_RECALL_BLACKLIST:
        return

    message_id = event.message_id
    operator_id = event.operator_id
    user_id = event.user_id

    # 从缓存中查找被撤回的消息
    if message_id not in message_cache:
        # 消息不在缓存中（可能是机器人启动前的消息）
        return

    msg_data = message_cache[message_id]

    # 检查是否是同一个群的消息
    if msg_data["group_id"] != group_id:
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

    # 存储撤回消息信息
    if group_id not in recalled_messages:
        recalled_messages[group_id] = []

    recalled_info = {
        "user_id": msg_data["user_id"],
        "user_name": msg_data["user_name"],
        "message": msg_data["message"],
        "time": msg_data["time"],
        "recall_time": datetime.now(),
        "operator_info": operator_info,
    }

    # 添加到列表开头（最新的在前面）
    recalled_messages[group_id].insert(0, recalled_info)

    # 限制每个群的撤回消息数量
    if len(recalled_messages[group_id]) > MAX_RECALLED_PER_GROUP:
        recalled_messages[group_id] = recalled_messages[group_id][:MAX_RECALLED_PER_GROUP]

    # 从消息缓存中删除
    del message_cache[message_id]


# 查看撤回消息命令
view_recall = on_command("防撤回", priority=5)

@view_recall.handle()
async def handle_view_recall(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """查看撤回的消息"""
    group_id = str(event.group_id)

    # 检查黑名单
    if group_id in ANTI_RECALL_BLACKLIST:
        await view_recall.finish("❌ 本群已禁用防撤回功能")

    # 检查该群是否有撤回记录
    if group_id not in recalled_messages or not recalled_messages[group_id]:
        await view_recall.finish("❌ 暂无撤回记录")

    # 检查是否@了某人
    target_user_id = None
    for seg in args:
        if seg.type == "at":
            target_user_id = str(seg.data.get("qq", ""))
            break

    # 查找撤回消息
    if target_user_id:
        # 查找指定用户的撤回消息
        user_recalls = [r for r in recalled_messages[group_id] if r["user_id"] == target_user_id]
        if not user_recalls:
            await view_recall.finish(f"❌ 没有找到该用户的撤回记录")
        recall_info = user_recalls[0]  # 取最新的一条
    else:
        # 取最新的撤回消息
        recall_info = recalled_messages[group_id][0]

    # 构建消息
    time_diff = (recall_info["recall_time"] - recall_info["time"]).total_seconds()

    hint = f"🔍 撤回消息查询\n"
    hint += f"{'='*30}\n"
    hint += f"👤 撤回者：{recall_info['user_name']}({recall_info['user_id']})\n"
    hint += f"🔧 操作者：{recall_info['operator_info']}\n"
    hint += f"⏰ 发送时间：{recall_info['time'].strftime('%H:%M:%S')}\n"
    hint += f"⏱️ 撤回时间：{time_diff:.1f}秒后\n"
    hint += f"{'='*30}\n"
    hint += "📝 撤回的内容：\n"

    # 构建完整消息
    result_msg = Message(hint)

    # 添加原消息内容
    original_msg = recall_info["message"]

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
    await view_recall.finish(result_msg)
