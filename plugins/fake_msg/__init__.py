"""
伪造发言插件
发送伪造的聊天记录
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, MessageSegment, Message
from nonebot.params import CommandArg
from nonebot.log import logger

fake_msg = on_command("伪造发言", aliases={"假消息", "伪造消息"}, priority=5, block=True)


@fake_msg.handle()
async def handle_fake_msg(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """
    伪造发言功能
    命令格式：/伪造发言 @用户1 文本1 @用户2 文本2 ...
    """
    # 解析消息：提取 @用户 和对应的文本
    segments = args
    if not segments:
        await fake_msg.finish(
            "用法：/伪造发言 @用户1 文本1 @用户2 文本2 ...\n"
            "示例：/伪造发言 @张三 你好啊 @李四 好的没问题"
        )

    # 存储解析后的消息列表: [(user_id, user_name, text), ...]
    messages = []
    current_user_id = None
    current_user_name = None
    current_text = []

    for seg in segments:
        if seg.type == "at":
            # 遇到 @用户，先保存上一个用户的消息
            if current_user_id is not None and current_text:
                messages.append((current_user_id, current_user_name, "".join(current_text).strip()))

            # 开始新的用户
            current_user_id = str(seg.data.get("qq"))
            # 尝试获取用户昵称
            try:
                user_info = await bot.get_group_member_info(
                    group_id=event.group_id,
                    user_id=int(current_user_id)
                )
                current_user_name = user_info.get("card") or user_info.get("nickname", f"用户{current_user_id}")
            except:
                current_user_name = f"用户{current_user_id}"

            current_text = []
        elif seg.type == "text":
            # 累积文本
            current_text.append(seg.data.get("text", ""))
        else:
            # 其他类型的消息段（图片、表情等）也添加到文本中
            current_text.append(str(seg))

    # 保存最后一个用户的消息
    if current_user_id is not None and current_text:
        messages.append((current_user_id, current_user_name, "".join(current_text).strip()))

    if not messages:
        await fake_msg.finish("请至少指定一个用户和对应的文本！")

    # 构建合并转发消息节点
    nodes = []
    for user_id, user_name, text in messages:
        if not text:
            continue

        nodes.append({
            "type": "node",
            "data": {
                "name": user_name,
                "uin": user_id,
                "content": text,
            }
        })

    if not nodes:
        await fake_msg.finish("没有有效的消息内容！")

    # 发送合并转发消息
    try:
        await bot.send_group_forward_msg(
            group_id=event.group_id,
            messages=nodes
        )
    except Exception as e:
        logger.error(f"发送伪造消息失败: {e}")
        await fake_msg.finish(f"❌ 发送失败：{e}")
