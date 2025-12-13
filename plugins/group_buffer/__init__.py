"""
群聊输出缓冲插件

在配置的群聊中拦截机器人发送的消息，不立即发送，
而是每隔一定时间将缓冲消息汇总成聊天记录发出。
"""
from __future__ import annotations

import asyncio
import base64
import tempfile
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union

from nonebot import get_driver, get_bot
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.log import logger
from nonebot.internal.matcher import current_event

driver = get_driver()
config = driver.config

GROUP_BUFFER_GROUPS = {
    gid.strip()
    for gid in str(getattr(config, "group_buffer_groups", "") or "").split(",")
    if gid.strip()
}
BUFFER_INTERVAL = int(getattr(config, "group_buffer_interval", 30))

# 消息过滤关键词配置
IMMEDIATE_KEYWORDS = {
    kw.strip()
    for kw in str(getattr(config, "group_buffer_immediate_keywords", "") or "").split(",")
    if kw.strip()
}
ONLY_BUFFER_KEYWORDS = {
    kw.strip()
    for kw in str(getattr(config, "group_buffer_only_keywords", "") or "").split(",")
    if kw.strip()
}

# 临时文件目录
TEMP_IMAGE_DIR = Path(tempfile.gettempdir()) / "qq_bot_buffer_images"
TEMP_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def _convert_base64_images_to_files(message: Message) -> Message:
    """
    将消息中的 base64 图片转换为本地文件路径
    这样在合并转发时 NapCat 可以正确读取图片
    """
    new_segments = []
    for seg in message:
        if seg.type == "image":
            file_data = seg.data.get("file", "")
            # 处理 base64:// 格式的图片
            if isinstance(file_data, str) and file_data.startswith("base64://"):
                try:
                    # 解码 base64 数据
                    b64_data = file_data[9:]  # 去掉 "base64://" 前缀
                    image_bytes = base64.b64decode(b64_data)

                    # 生成唯一文件名
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    temp_file = TEMP_IMAGE_DIR / f"buffer_img_{timestamp}.png"

                    # 保存到临时文件
                    with open(temp_file, "wb") as f:
                        f.write(image_bytes)

                    # 使用绝对路径（转换为正斜杠格式，兼容Windows和NapCat）
                    # NapCat 支持直接使用绝对路径
                    abs_path = str(temp_file.resolve()).replace("\\", "/")
                    new_seg = MessageSegment.image(f"file:///{abs_path}")
                    new_segments.append(new_seg)
                    logger.debug(f"已将 base64 图片转换为临时文件: {abs_path}")
                    continue
                except Exception as e:
                    logger.warning(f"转换 base64 图片失败: {e}")
        new_segments.append(seg)
    return Message(new_segments)


def _cleanup_old_temp_images():
    """清理超过1小时的临时图片文件"""
    try:
        import time
        now = time.time()
        for f in TEMP_IMAGE_DIR.iterdir():
            if f.is_file() and (now - f.stat().st_mtime) > 3600:
                f.unlink()
    except Exception as e:
        logger.debug(f"清理临时图片失败: {e}")


def _should_buffer_message(message: Union[str, Message, MessageSegment]) -> bool:
    """
    判断消息是否应该被缓冲

    过滤规则：
    1. 如果配置了 ONLY_BUFFER_KEYWORDS，只有包含这些关键词的消息才缓冲
    2. 否则，如果配置了 IMMEDIATE_KEYWORDS，包含这些关键词的消息不缓冲（立即发送）
    3. 如果都没配置，所有消息都缓冲

    返回 True 表示应该缓冲，False 表示立即发送
    """
    # 将消息转换为字符串以便检查关键词
    msg_text = str(Message(message))

    # 优先检查"只缓冲关键词"
    if ONLY_BUFFER_KEYWORDS:
        # 如果配置了只缓冲关键词，检查消息是否包含任一关键词
        for keyword in ONLY_BUFFER_KEYWORDS:
            if keyword in msg_text:
                return True  # 包含关键词，应该缓冲
        return False  # 不包含任何关键词，不缓冲（立即发送）

    # 检查"立即发送关键词"
    if IMMEDIATE_KEYWORDS:
        # 如果消息包含任一立即发送关键词，不缓冲
        for keyword in IMMEDIATE_KEYWORDS:
            if keyword in msg_text:
                return False  # 包含立即发送关键词，不缓冲

    # 默认缓冲所有消息
    return True


if GROUP_BUFFER_GROUPS:
    original_call_api = Bot.call_api

    message_buffers: Dict[str, List[Dict[str, str]]] = {}
    flush_tasks: Dict[str, asyncio.Task] = {}
    buffer_lock = asyncio.Lock()

    async def _flush_group_buffer(group_id: str, bot_id: str):
        await asyncio.sleep(max(BUFFER_INTERVAL, 1))
        async with buffer_lock:
            entries = message_buffers.get(group_id, [])
            if not entries:
                flush_tasks.pop(group_id, None)
                return
            message_buffers[group_id] = []
            flush_tasks.pop(group_id, None)

        try:
            bot = get_bot(bot_id)
            nodes = []
            for entry in entries:
                # 构建消息：时间 + @用户 + 内容
                content = Message(MessageSegment.text(f"[{entry['time']}] "))
                # 如果有用户ID，添加 @
                if entry.get("user_id"):
                    content += MessageSegment.at(entry["user_id"])
                    content += MessageSegment.text(" ")
                content += entry["message"]
                nodes.append(
                    {
                        "type": "node",
                        "data": {
                            "name": "Bot缓冲",
                            "uin": bot_id,
                            "content": content,
                        },
                    }
                )
            await original_call_api(
                bot,
                "send_group_forward_msg",
                group_id=int(group_id),
                messages=nodes,
            )
            # 发送成功后清理旧的临时文件
            _cleanup_old_temp_images()
        except Exception as err:
            logger.warning(f"发送缓冲消息失败: group={group_id}, err={err}")
            # fallback: 逐条发送消息（包括图片）
            try:
                bot = get_bot(bot_id)
                # 先发送汇总提示
                await original_call_api(
                    bot,
                    "send_group_msg",
                    group_id=int(group_id),
                    message=f"🗒️ 过去{BUFFER_INTERVAL}秒 Bot 回复汇总（共{len(entries)}条，转发失败，逐条发送）",
                )
                # 逐条发送原始消息
                for entry in entries:
                    try:
                        # 构建消息：时间 + @用户 + 内容
                        msg = Message(MessageSegment.text(f"[{entry['time']}] "))
                        if entry.get("user_id"):
                            msg += MessageSegment.at(entry["user_id"])
                            msg += MessageSegment.text(" ")
                        msg += entry["message"]
                        await original_call_api(
                            bot,
                            "send_group_msg",
                            group_id=int(group_id),
                            message=msg,
                        )
                        await asyncio.sleep(0.5)  # 避免发送过快
                    except Exception as send_err:
                        logger.debug(f"发送单条消息失败: {send_err}")
                # fallback 发送成功后也清理临时文件
                _cleanup_old_temp_images()
            except Exception as err2:
                logger.error(f"发送缓冲文本汇总仍失败: group={group_id}, err={err2}")
                # 只有 fallback 也失败时才把消息放回缓冲
                async with buffer_lock:
                    message_buffers.setdefault(group_id, []).extend(entries)

    async def _buffer_message(
        bot: Bot, group_id: str, message: Union[str, Message, MessageSegment],
        user_id: str | None = None
    ):
        # 将 base64 图片转换为本地文件，避免合并转发时下载失败
        converted_message = _convert_base64_images_to_files(Message(message))

        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": converted_message,
            "user_id": user_id,  # 保存请求用户ID，用于 @
        }
        async with buffer_lock:
            message_buffers.setdefault(group_id, []).append(entry)
            if group_id not in flush_tasks:
                flush_tasks[group_id] = asyncio.create_task(
                    _flush_group_buffer(group_id, bot.self_id)
                )

    async def buffered_call_api(self: Bot, api: str, **data):
        target_group: str | None = None
        if api == "send_group_msg":
            target_group = str(data.get("group_id"))
        elif api == "send_msg" and data.get("message_type") == "group":
            target_group = str(data.get("group_id"))

        if target_group and target_group in GROUP_BUFFER_GROUPS:
            message = data.get("message", "")

            # 检查消息是否应该被缓冲
            if not _should_buffer_message(message):
                # 不应该缓冲，立即发送
                logger.debug(f"消息包含立即发送关键词或不在只缓冲关键词列表中，立即发送: {str(message)[:50]}...")
                return await original_call_api(self, api, **data)

            # 尝试获取当前事件的用户ID
            user_id: str | None = None
            try:
                event = current_event.get()
                if event and hasattr(event, "user_id"):
                    user_id = str(event.user_id)
            except LookupError:
                # 没有当前事件上下文（比如定时任务触发的消息）
                pass

            await _buffer_message(
                self,
                target_group,
                message,
                user_id=user_id,
            )
            return {"status": "buffered"}
        return await original_call_api(self, api, **data)

    Bot.call_api = buffered_call_api  # type: ignore
