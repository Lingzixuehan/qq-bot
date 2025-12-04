"""
群友语录插件
功能：
- 添加语录：记录群友的名言
- 随机语录：随机展示群友的发言
- 删除语录：删除指定语录
"""
from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
from nonebot.rule import to_me
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.append(str(Path(__file__).parent.parent))
from common.database import QuoteDB
from common.image_generator import generate_quote_image_base64

# 添加语录
add_quote = on_command("添加语录", aliases={"记录语录"}, priority=5)

@add_quote.handle()
async def handle_add_quote(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """添加语录"""
    # 检查是否有回复消息
    if event.reply:
        reply_msg = event.reply
        user_id = str(reply_msg.sender.user_id)
        user_name = reply_msg.sender.nickname or str(user_id)
        content = reply_msg.message.extract_plain_text()
    else:
        # 解析命令参数
        arg_text = args.extract_plain_text().strip()
        if not arg_text:
            await add_quote.finish("用法：回复一条消息后发送 /添加语录\n或：/添加语录 @用户 语录内容")
            return

        # 尝试从消息中提取@的用户
        at_seg = None
        for seg in args:
            if seg.type == "at":
                at_seg = seg
                break

        if not at_seg:
            await add_quote.finish("请@要添加语录的用户，或回复Ta的消息")
            return

        user_id = at_seg.data["qq"]
        # 获取用户信息
        user_info = await bot.get_group_member_info(
            group_id=event.group_id,
            user_id=int(user_id)
        )
        user_name = user_info.get("nickname", user_id)

        # 移除@后的内容作为语录
        content = args.extract_plain_text().strip()
        if not content:
            await add_quote.finish("语录内容不能为空")
            return

    group_id = str(event.group_id)

    # 添加到数据库
    success = await QuoteDB.add_quote(group_id, user_id, user_name, content)

    if success:
        await add_quote.finish(f"✅ 已记录 {user_name} 的语录：\n{content}")
    else:
        await add_quote.finish("❌ 添加语录失败")


# 随机语录
random_quote = on_command("语录", aliases={"随机语录", "来句语录"}, priority=5)

@random_quote.handle()
async def handle_random_quote(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """随机语录"""
    group_id = str(event.group_id)

    # 检查是否指定了用户
    user_id = None
    for seg in args:
        if seg.type == "at":
            user_id = seg.data["qq"]
            break

    quote = await QuoteDB.get_random_quote(group_id, user_id)

    if quote:
        # 生成聊天截图样式的图片
        try:
            img_base64 = generate_quote_image_base64(
                user_name=quote['user_name'],
                content=quote['content']
            )

            # 发送图片
            await random_quote.finish(
                MessageSegment.at(quote["user_id"]) +
                MessageSegment.text("\n📝 翻到一条语录：\n") +
                MessageSegment.image(img_base64)
            )
        except Exception as e:
            # 如果生成图片失败，使用文本格式
            print(f"生成语录图片失败: {e}")
            msg = f"📝 {quote['user_name']} 曾经说过：\n\n{quote['content']}"
            await random_quote.finish(MessageSegment.at(quote["user_id"]) + f"\n{msg}")
    else:
        if user_id:
            await random_quote.finish("该用户还没有语录哦")
        else:
            await random_quote.finish("本群还没有语录，快用 /添加语录 来记录群友的名言吧！")


# 删除语录
delete_quote = on_command("删除语录", priority=5)

@delete_quote.handle()
async def handle_delete_quote(bot: Bot, event: GroupMessageEvent):
    """删除语录（需要回复要删除的语录）"""
    if not event.reply:
        await delete_quote.finish("请回复要删除的语录消息")
        return

    reply_msg = event.reply
    user_id = str(reply_msg.sender.user_id)
    content = reply_msg.message.extract_plain_text()
    group_id = str(event.group_id)

    # 只允许本人或管理员删除
    sender_role = event.sender.role
    if str(event.user_id) != user_id and sender_role not in ["admin", "owner"]:
        await delete_quote.finish("只能删除自己的语录哦")
        return

    success = await QuoteDB.delete_quote(group_id, user_id, content)

    if success:
        await delete_quote.finish("✅ 已删除该语录")
    else:
        await delete_quote.finish("❌ 删除失败")


# 查询语录数量
quote_count = on_command("我的语录", aliases={"语录数量"}, priority=5)

@quote_count.handle()
async def handle_quote_count(event: GroupMessageEvent):
    """查询语录数量"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    count = await QuoteDB.get_user_quote_count(group_id, user_id)
    await quote_count.finish(f"你在本群共有 {count} 条语录")
