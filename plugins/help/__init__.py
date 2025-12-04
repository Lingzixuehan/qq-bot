"""
帮助插件
显示机器人所有功能的帮助信息
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment, GroupMessageEvent

help_cmd = on_command("help", aliases={"帮助", "菜单", "功能"}, priority=1)

@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    """显示帮助信息（合并转发格式）"""

    # 如果是私聊，使用普通文本格式
    if not isinstance(event, GroupMessageEvent):
        help_text = """
🤖 QQ Bot 功能菜单
==================

📝 群友语录
  /添加语录 - 回复消息后使用，记录群友名言
  /语录 - 随机展示一条语录
  /语录 @某人 - 查看某人的随机语录
  /删除语录 - 回复语录消息删除（仅本人/管理员）
  /我的语录 - 查看自己的语录数量

💕 群老婆
  /抽老婆 - 每日抽取一位群友作为老婆
  /查老婆 - 查看今日老婆
  （每天0点重置）

✅ 签到
  /签到 - 每日签到
  /签到信息 - 查看自己的签到记录
  /签到排行 - 查看今日签到排行榜

🔔 防撤回
  自动功能 - 有人撤回消息时自动提醒
  会显示撤回的内容（文字、图片等）

🎲 投骰子
  /roll - 投一个6面骰子
  /roll 20 - 投一个20面骰子
  /roll 3d6 - 投3个6面骰子
  /d6 /d20 /d100 - 快捷投骰子命令
  /猜大小 大/小 - 猜大小游戏

🎮 Steam功能
  /绑定steam <Steam ID> - 绑定Steam账号
  /解绑steam - 解除Steam账号绑定
  /steam资料 [@某人] - 查看Steam个人资料
  /steam游戏 [@某人] - 查看最近在玩的游戏
  /steam游戏库 [@某人] - 查看游戏库和游戏时长
  /steam视奸 - 查看所有人的Steam在线状态

🎨 二次元美图
  /美图 - 随机获取一张二次元图片
  /搜图 - 随机获取一张二次元图片
  /来点图 [数量] - 获取多张图片（最多3张）

📖 其他
  /help - 显示本帮助信息

==================
💡 提示：所有命令都需要使用 / 前缀
        """.strip()
        await help_cmd.finish(help_text)
        return

    # 群聊使用合并转发格式
    bot_id = event.self_id
    bot_info = await bot.get_stranger_info(user_id=bot_id)
    bot_name = bot_info.get("nickname", "Bot")

    # 构建转发消息节点
    messages = [
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🤖 QQ Bot 功能菜单\n==================\n欢迎使用！以下是所有可用功能："
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="📝 群友语录\n\n/添加语录 - 回复消息后使用，记录群友名言\n/语录 - 随机展示一条语录\n/语录 @某人 - 查看某人的随机语录\n/删除语录 - 回复语录消息删除（仅本人/管理员）\n/我的语录 - 查看自己的语录数量"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="💕 群老婆\n\n/抽老婆 - 每日抽取一位群友作为老婆\n/查老婆 - 查看今日老婆\n\n（每天0点重置）"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="✅ 签到\n\n/签到 - 每日签到\n/签到信息 - 查看自己的签到记录\n/签到排行 - 查看今日签到排行榜"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🔔 防撤回\n\n自动功能 - 有人撤回消息时自动提醒\n会显示撤回的内容（文字、图片等）"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎲 投骰子\n\n/roll - 投一个6面骰子\n/roll 20 - 投一个20面骰子\n/roll 3d6 - 投3个6面骰子\n/d6 /d20 /d100 - 快捷投骰子命令\n/猜大小 大/小 - 猜大小游戏"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎮 Steam功能\n\n/绑定steam <Steam ID> - 绑定Steam账号\n/解绑steam - 解除Steam账号绑定\n/steam资料 [@某人] - 查看Steam个人资料\n/steam游戏 [@某人] - 查看最近在玩的游戏\n/steam游戏库 [@某人] - 查看游戏库和游戏时长\n/steam视奸 - 查看所有人的Steam在线状态\n\n💡 首次使用需要绑定Steam账号"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎨 二次元美图\n\n/美图 - 随机获取一张二次元图片\n/搜图 - 随机获取一张二次元图片\n/来点图 [数量] - 获取多张图片（最多3张）\n\n💡 图片来源于多个API，全年龄向"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="📖 其他说明\n\n💡 所有命令都需要使用 / 前缀\n💡 例如：/help\n💡 大部分命令支持群聊和私聊"
        ),
    ]

    # 发送合并转发消息
    await bot.send_group_forward_msg(
        group_id=event.group_id,
        messages=messages
    )
    await help_cmd.finish()
