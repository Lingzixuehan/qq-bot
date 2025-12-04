"""
帮助插件
显示机器人所有功能的帮助信息
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent

help_cmd = on_command("help", aliases={"帮助", "菜单", "功能"}, priority=1)

@help_cmd.handle()
async def handle_help(event: GroupMessageEvent):
    """显示帮助信息"""
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

📖 其他
  /help - 显示本帮助信息

==================
💡 提示：命令支持带 / 或不带 / 都可以
    """.strip()

    await help_cmd.finish(help_text)
