"""
群聊输出缓冲插件

在配置的群聊中拦截机器人发送的消息，不立即发送，
而是每隔一定时间将缓冲消息汇总成聊天记录发出。
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Dict, List, Union

from nonebot import get_driver, get_bot
from nonebot.adapters.onebot.v11 import Bot, Message, MessageSegment
from nonebot.log import logger

driver = get_driver()
config = driver.config

GROUP_BUFFER_GROUPS = {
    gid.strip()
    for gid in str(getattr(config, "group_buffer_groups", "") or "").split(",")
    if gid.strip()
}
BUFFER_INTERVAL = int(getattr(config, "group_buffer_interval", 30))

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
                content = Message(
                    MessageSegment.text(f"[{entry['time']}] ")
                ) + entry["message"]
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
        except Exception as err:
            logger.warning(f"发送缓冲消息失败: group={group_id}, err={err}")
            # fallback to文本总结
            lines = [
                f"🗒️ 过去{BUFFER_INTERVAL}秒 Bot 回复汇总（共{len(entries)}条）"
            ]
            for entry in entries:
                text_content = "".join(
                    seg.data.get("text", "")
                    for seg in entry["message"]
                    if seg.type == "text"
                ).strip()
                if not text_content:
                    text_content = "[包含非文本内容]"
                lines.append(f"[{entry['time']}] {text_content}")
            summary = "\n".join(lines)
            try:
                bot = get_bot(bot_id)
                await original_call_api(
                    bot,
                    "send_group_msg",
                    group_id=int(group_id),
                    message=MessageSegment.text(summary),
                )
            except Exception as err2:
                logger.error(f"发送缓冲文本汇总仍失败: group={group_id}, err={err2}")
            async with buffer_lock:
                message_buffers.setdefault(group_id, []).extend(entries)

    async def _buffer_message(
        bot: Bot, group_id: str, message: Union[str, Message, MessageSegment]
    ):
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": Message(message),
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
            await _buffer_message(
                self,
                target_group,
                data.get("message", ""),
            )
            return {"status": "buffered"}
        return await original_call_api(self, api, **data)

    Bot.call_api = buffered_call_api  # type: ignore
