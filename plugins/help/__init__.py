"""
帮助插件
显示机器人所有功能的帮助信息
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, MessageSegment, GroupMessageEvent
from nonebot.exception import FinishedException

help_cmd = on_command("help", aliases={"帮助", "菜单", "功能"}, priority=1, block=True)

@help_cmd.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    """显示帮助信息（使用合并转发格式）"""

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
            content="🔔 防撤回\n\n/防撤回 - 查看最近一条撤回的消息\n/防撤回 @某人 - 查看某人最近撤回的消息\n\n💡 支持文字、图片、表情等多种消息类型"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎲 投骰子\n\n/roll - 投一个6面骰子\n/roll 20 - 投一个20面骰子\n/roll 3d6 - 投3个6面骰子\n/d6 /d20 /d100 - 快捷投骰子命令\n/猜大小 大/小 - 猜大小游戏"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎮 Steam功能\n\n/绑定steam <Steam ID> - 绑定Steam账号\n/解绑steam - 解除Steam账号绑定\n/steam资料 [@某人] - 查看Steam个人资料\n/steam游戏 [@某人] - 查看最近在玩的游戏\n/steam游戏库 [@某人] - 查看游戏库和游戏时长\n/steam视奸 - 查看所有人的Steam在线状态（精美图片）\n/steam昵称 <昵称> - 设置Steam显示昵称\n/steam启用播报 - 启用游戏状态自动播报\n/steam禁用播报 - 禁用游戏状态自动播报\n\n⭐ 商店功能 ⭐\n/steam价格 <游戏名> [| 对比区列表] - 查询价格、折扣、史低，自动翻译官方英文名\n/steam喜加一 - 查看当前限免喜加一\n/steam喜加一订阅 - 订阅喜加一推送\n/steam喜加一退订 - 退订喜加一推送\n/steam折扣订阅 - 订阅高折扣推送\n/steam折扣退订 - 退订高折扣推送\n/steam史低 - 查看热门史低游戏\n/steam史低 <类型> - 查看特定类型史低游戏\n/steam榜单 - 查看Steam全球热销榜\n/steam促销 - 查看当前促销活动信息\n\n💡 支持自动播报好友游戏状态变化和Steam促销活动"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎨 二次元美图\n\n/美图 [API源] - 随机获取一张二次元图片\n/搜图 <标签> [API源] - 按标签搜索图片\n/来点图 [数量] [API源] - 获取多张图片（最多5张）\n\n📝 示例：\n• /美图 - 默认API（lolicon）\n• /美图 safebooru - 指定Safebooru\n• /搜图 touhou danbooru - 用Danbooru搜索\n• /来点图 3 lolicon - 用Lolicon获取3张\n\n💡 支持4个API源：\n• loli - LoliAPI，简单稳定\n• safebooru - Safebooru，安全过滤\n• lolicon - Lolicon，Pixiv源（默认）\n• danbooru - Danbooru，海量图片"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎮 趣味游戏\n\n/魔女审判 @用户 - 发起投票禁言\n  • 群友通过贴表情投票决定是否禁言目标用户\n  • 👌 贴【OK】表示同意，❓ 贴【问号】表示反对\n  • 投票时间结束后自动统计并执行\n\n/禁言大转盘 - 随机禁言自己\n  • 转动转盘，随机抽取禁言时长\n  • 考验你的运气！\n\n/俄罗斯轮盘 <容量> <子弹> - 创建俄罗斯轮盘游戏\n/开枪 - 参与游戏，中弹则禁言\n/轮盘状态 - 查看当前游戏状态\n/结束轮盘 - 终止游戏（仅管理员）\n  • 示例：/俄罗斯轮盘 6 1\n  • 刺激的运气游戏，敢来挑战吗？\n\n💡 所有游戏功能都有冷却时间"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="✨ 互动功能\n\n• 戳一戳 - 戳机器人会被戳回去\n• @机器人 早安/晚安 - 根据时间段回复不同内容\n  • 在不同时间说早安/晚安会有不同反应哦~\n• @机器人 - @机器人会随机回复\n\n💡 这些是自动触发的功能，无需命令"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="🎭 娱乐工具\n\n/伪造发言 @用户1 文本1 @用户2 文本2 ... - 生成伪造的聊天记录\n  • 示例：/伪造发言 @张三 你好啊 @李四 好的没问题\n  • 可以伪造多条发言记录\n\n💡 仅供娱乐，请勿用于恶意用途"
        ),
        MessageSegment.node_custom(
            user_id=bot_id,
            nickname=bot_name,
            content="📖 其他说明\n\n💡 所有命令都需要使用 / 前缀\n💡 例如：/help\n💡 大部分命令支持群聊和私聊"
        ),
    ]

    try:
        if isinstance(event, GroupMessageEvent):
            await bot.send_group_forward_msg(
                group_id=event.group_id,
                messages=messages
            )
        else:
            await bot.send_private_forward_msg(user_id=event.user_id, messages=messages)
    except FinishedException:
        # finish异常直接向上传播
        raise
    except Exception as e:
        # 如果转发消息发送失败，提示用户
        await help_cmd.finish(f"❌ 发送帮助信息失败：{e}")
