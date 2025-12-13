"""
趣味游戏插件
包含：魔女审判、禁言大转盘
"""
import asyncio
import math
import random
from datetime import datetime, timedelta
from io import BytesIO
from typing import Dict, Optional, Tuple

from nonebot import on_command, get_driver, get_bot
from nonebot.adapters.onebot.v11 import (
    Bot,
    GroupMessageEvent,
    Message,
    MessageSegment,
)
from nonebot.log import logger
from nonebot.params import CommandArg
from PIL import Image, ImageDraw, ImageFont

# ============== 配置 ==============
driver = get_driver()
config = driver.config

# 魔女审判配置
WITCH_TRIAL_BAN_DURATION = int(getattr(config, "witch_trial_ban_duration", 60))  # 禁言时长（秒）
WITCH_TRIAL_VOTE_TIME = int(getattr(config, "witch_trial_vote_time", 60))  # 投票时间（秒）
WITCH_TRIAL_COOLDOWN = int(getattr(config, "witch_trial_cooldown", 300))  # 冷却时间（秒）
WITCH_TRIAL_MIN_VOTES = int(getattr(config, "witch_trial_min_votes", 3))  # 最少投票数

# 禁言大转盘配置
ROULETTE_DURATIONS_STR = str(getattr(config, "roulette_durations", "10,30,60,120,300,600"))
ROULETTE_DURATIONS = [int(x.strip()) for x in ROULETTE_DURATIONS_STR.split(",") if x.strip()]
ROULETTE_COOLDOWN = int(getattr(config, "roulette_cooldown", 60))  # 冷却时间（秒）

# 表情 ID（QQ 表情）
EMOJI_AGREE = "124"  # OK手势
EMOJI_DISAGREE = "32"  # 问号

# ============== 数据存储 ==============
# 魔女审判冷却：{group_id: last_use_time}
witch_trial_cooldowns: Dict[str, datetime] = {}

# 禁言大转盘冷却：{(group_id, user_id): last_use_time}
roulette_cooldowns: Dict[Tuple[str, str], datetime] = {}

# 进行中的审判：{group_id: {target_id, message_id, initiator_id, end_time}}
active_trials: Dict[str, dict] = {}


# ============== 工具函数 ==============
def format_duration(seconds: int) -> str:
    """格式化时长显示"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}分{secs}秒" if secs else f"{minutes}分钟"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}小时{minutes}分钟" if minutes else f"{hours}小时"


def draw_roulette(durations: list, selected_index: int) -> bytes:
    """
    绘制转盘图像

    Args:
        durations: 时间选项列表（秒）
        selected_index: 选中的索引

    Returns:
        PNG 图像数据
    """
    # 图像尺寸
    size = 500
    center = size // 2
    radius = 200

    # 创建图像
    img = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    # 颜色列表
    colors = [
        (255, 99, 71),    # 番茄红
        (255, 165, 0),    # 橙色
        (255, 215, 0),    # 金色
        (144, 238, 144),  # 浅绿
        (135, 206, 250),  # 天蓝
        (221, 160, 221),  # 梅红
        (255, 182, 193),  # 浅粉
        (176, 196, 222),  # 钢蓝
    ]

    n = len(durations)
    angle_per_slice = 360 / n

    # 尝试加载字体
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except:
        font = ImageFont.load_default()
        font_large = font

    # 绘制扇形
    for i, duration in enumerate(durations):
        start_angle = i * angle_per_slice - 90  # 从12点方向开始
        end_angle = start_angle + angle_per_slice

        color = colors[i % len(colors)]

        # 如果是选中的扇形，加深颜色
        if i == selected_index:
            color = tuple(max(0, c - 50) for c in color)

        # 绘制扇形
        draw.pieslice(
            [center - radius, center - radius, center + radius, center + radius],
            start_angle,
            end_angle,
            fill=color,
            outline=(50, 50, 50),
            width=2
        )

        # 计算文字位置（扇形中心）
        mid_angle = math.radians(start_angle + angle_per_slice / 2)
        text_r = radius * 0.65
        text_x = center + text_r * math.cos(mid_angle)
        text_y = center + text_r * math.sin(mid_angle)

        # 绘制时间文字
        text = format_duration(duration)
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        draw.text(
            (text_x - text_w / 2, text_y - text_h / 2),
            text,
            fill=(0, 0, 0),
            font=font
        )

    # 绘制中心圆
    center_radius = 30
    draw.ellipse(
        [center - center_radius, center - center_radius,
         center + center_radius, center + center_radius],
        fill=(255, 255, 255),
        outline=(50, 50, 50),
        width=3
    )

    # 绘制指针（指向选中的扇形）
    pointer_angle = math.radians(selected_index * angle_per_slice - 90 + angle_per_slice / 2)
    pointer_length = radius + 30
    pointer_x = center + pointer_length * math.cos(pointer_angle)
    pointer_y = center + pointer_length * math.sin(pointer_angle)

    # 绘制指针三角形
    arrow_size = 20
    arrow_angle1 = pointer_angle + math.radians(150)
    arrow_angle2 = pointer_angle - math.radians(150)

    arrow_points = [
        (pointer_x, pointer_y),
        (pointer_x + arrow_size * math.cos(arrow_angle1),
         pointer_y + arrow_size * math.sin(arrow_angle1)),
        (pointer_x + arrow_size * math.cos(arrow_angle2),
         pointer_y + arrow_size * math.sin(arrow_angle2)),
    ]
    draw.polygon(arrow_points, fill=(255, 0, 0), outline=(100, 0, 0))

    # 绘制标题
    title = "禁言大转盘"
    bbox = draw.textbbox((0, 0), title, font=font_large)
    title_w = bbox[2] - bbox[0]
    draw.text((center - title_w / 2, 20), title, fill=(50, 50, 50), font=font_large)

    # 绘制结果
    result_text = f"结果: {format_duration(durations[selected_index])}"
    bbox = draw.textbbox((0, 0), result_text, font=font_large)
    result_w = bbox[2] - bbox[0]
    draw.text((center - result_w / 2, size - 50), result_text, fill=(255, 0, 0), font=font_large)

    # 导出为 bytes
    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


# ============== 魔女审判 ==============
witch_trial = on_command("魔女审判", priority=5, block=True)


@witch_trial.handle()
async def handle_witch_trial(bot: Bot, event: GroupMessageEvent, args: Message = CommandArg()):
    """魔女审判：发起投票禁言"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 检查是否有进行中的审判
    if group_id in active_trials:
        trial = active_trials[group_id]
        remaining = (trial["end_time"] - datetime.now()).total_seconds()
        if remaining > 0:
            await witch_trial.finish(f"当前群有正在进行的审判，请等待 {int(remaining)} 秒后再发起新审判")

    # 检查冷却
    if group_id in witch_trial_cooldowns:
        elapsed = (datetime.now() - witch_trial_cooldowns[group_id]).total_seconds()
        if elapsed < WITCH_TRIAL_COOLDOWN:
            remaining = int(WITCH_TRIAL_COOLDOWN - elapsed)
            await witch_trial.finish(f"魔女审判冷却中，请等待 {remaining} 秒")

    # 解析目标用户
    target_id: Optional[str] = None
    for seg in args:
        if seg.type == "at":
            target_id = str(seg.data.get("qq"))
            break

    if not target_id:
        await witch_trial.finish(
            "用法：/魔女审判 @目标用户\n"
            "发起对目标用户的投票禁言"
        )

    # 不能审判自己
    if target_id == user_id:
        await witch_trial.finish("不能对自己发起魔女审判！")

    # 不能审判机器人
    if target_id == bot.self_id:
        await witch_trial.finish("不能对我发起魔女审判！")

    # 发送投票消息
    vote_msg = (
        f"📢 魔女审判发起\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 目标用户："
    )
    vote_msg_obj = Message(vote_msg) + MessageSegment.at(target_id) + Message(
        f"\n⏱️ 禁言时长：{format_duration(WITCH_TRIAL_BAN_DURATION)}\n"
        f"🗳️ 投票方式：给本条消息贴表情\n"
        f"   👌 贴【OK】= 同意\n"
        f"   ❓ 贴【问号】= 反对\n"
        f"⏰ 投票时间：{WITCH_TRIAL_VOTE_TIME}秒\n"
        f"📊 最少票数：{WITCH_TRIAL_MIN_VOTES}票\n"
        f"━━━━━━━━━━━━━━\n"
        f"发起人："
    ) + MessageSegment.at(user_id)

    # 发送消息并获取 message_id
    result = await bot.send_group_msg(group_id=event.group_id, message=vote_msg_obj)
    message_id = result.get("message_id")

    if not message_id:
        await witch_trial.finish("发送投票消息失败")

    # 给消息贴上投票表情
    try:
        # 贴同意表情
        await bot.call_api("set_msg_emoji_like", message_id=message_id, emoji_id=EMOJI_AGREE)
        await asyncio.sleep(0.3)
        # 贴反对表情
        await bot.call_api("set_msg_emoji_like", message_id=message_id, emoji_id=EMOJI_DISAGREE)
    except Exception as e:
        logger.warning(f"贴表情失败: {e}")

    # 记录审判信息
    active_trials[group_id] = {
        "target_id": target_id,
        "message_id": message_id,
        "initiator_id": user_id,
        "end_time": datetime.now() + timedelta(seconds=WITCH_TRIAL_VOTE_TIME),
    }

    # 更新冷却时间
    witch_trial_cooldowns[group_id] = datetime.now()

    # 等待投票结束
    await asyncio.sleep(WITCH_TRIAL_VOTE_TIME)

    # 检查审判是否仍然有效
    if group_id not in active_trials or active_trials[group_id]["message_id"] != message_id:
        return

    # 获取投票结果
    agree_count = 0
    disagree_count = 0

    try:
        # 分别获取两种表情的回应统计
        # fetch_emoji_like 需要 message_id 和 emojiId 参数
        try:
            agree_data = await bot.call_api(
                "fetch_emoji_like",
                message_id=message_id,
                emojiId=EMOJI_AGREE,
                emojiType="1"  # QQ系统表情
            )
            logger.debug(f"同意表情数据: {agree_data}")
            if isinstance(agree_data, dict):
                # 尝试多种可能的数据格式
                agree_count = agree_data.get("result", {}).get("emojiLikesList", [])
                if isinstance(agree_count, list):
                    agree_count = len(agree_count)
                else:
                    agree_count = agree_data.get("count", 0)
                # 减去机器人自己贴的
                agree_count = max(0, agree_count - 1)
        except Exception as e:
            logger.debug(f"获取同意表情失败: {e}")

        try:
            disagree_data = await bot.call_api(
                "fetch_emoji_like",
                message_id=message_id,
                emojiId=EMOJI_DISAGREE,
                emojiType="1"
            )
            logger.debug(f"反对表情数据: {disagree_data}")
            if isinstance(disagree_data, dict):
                disagree_count = disagree_data.get("result", {}).get("emojiLikesList", [])
                if isinstance(disagree_count, list):
                    disagree_count = len(disagree_count)
                else:
                    disagree_count = disagree_data.get("count", 0)
                disagree_count = max(0, disagree_count - 1)
        except Exception as e:
            logger.debug(f"获取反对表情失败: {e}")
    except Exception as e:
        logger.warning(f"获取表情回应失败: {e}")
        # API 不支持时使用备用逻辑
        await bot.send_group_msg(
            group_id=event.group_id,
            message="⚠️ 无法获取投票结果（API不支持）\n审判取消"
        )
        active_trials.pop(group_id, None)
        return

    # 清理审判记录
    active_trials.pop(group_id, None)

    # 计算结果
    total_votes = agree_count + disagree_count

    result_msg = (
        f"📊 魔女审判结果\n"
        f"━━━━━━━━━━━━━━\n"
        f"🎯 目标："
    )
    result_msg_obj = Message(result_msg) + MessageSegment.at(target_id) + Message(
        f"\n👌 同意：{agree_count} 票\n"
        f"❓ 反对：{disagree_count} 票\n"
        f"📈 总票数：{total_votes}\n"
        f"━━━━━━━━━━━━━━\n"
    )

    # 判断结果
    if total_votes < WITCH_TRIAL_MIN_VOTES:
        result_msg_obj += Message(f"❌ 投票人数不足（需要至少 {WITCH_TRIAL_MIN_VOTES} 票），审判无效")
    elif agree_count > disagree_count:
        # 执行禁言
        try:
            await bot.set_group_ban(
                group_id=event.group_id,
                user_id=int(target_id),
                duration=WITCH_TRIAL_BAN_DURATION
            )
            result_msg_obj += Message(
                f"✅ 审判通过！\n"
                f"🔇 已禁言 {format_duration(WITCH_TRIAL_BAN_DURATION)}"
            )
        except Exception as e:
            logger.error(f"禁言失败: {e}")
            result_msg_obj += Message(f"⚠️ 审判通过但禁言执行失败\n错误：{str(e)[:50]}")
    else:
        result_msg_obj += Message("❌ 审判未通过，目标用户逃过一劫！")

    await bot.send_group_msg(group_id=event.group_id, message=result_msg_obj)


# ============== 禁言大转盘 ==============
ban_roulette = on_command("禁言大转盘", aliases={"禁言轮盘"}, priority=5, block=True)


@ban_roulette.handle()
async def handle_ban_roulette(bot: Bot, event: GroupMessageEvent):
    """禁言大转盘：随机禁言自己"""
    group_id = str(event.group_id)
    user_id = str(event.user_id)

    # 检查冷却
    cooldown_key = (group_id, user_id)
    if cooldown_key in roulette_cooldowns:
        elapsed = (datetime.now() - roulette_cooldowns[cooldown_key]).total_seconds()
        if elapsed < ROULETTE_COOLDOWN:
            remaining = int(ROULETTE_COOLDOWN - elapsed)
            await ban_roulette.finish(f"转盘冷却中，请等待 {remaining} 秒")

    # 更新冷却
    roulette_cooldowns[cooldown_key] = datetime.now()

    # 随机选择一个时间
    selected_index = random.randint(0, len(ROULETTE_DURATIONS) - 1)
    selected_duration = ROULETTE_DURATIONS[selected_index]

    # 绘制转盘图像
    try:
        img_bytes = draw_roulette(ROULETTE_DURATIONS, selected_index)
        img_seg = MessageSegment.image(f"base64://{__import__('base64').b64encode(img_bytes).decode()}")
    except Exception as e:
        logger.error(f"绘制转盘失败: {e}")
        img_seg = None

    # 发送结果消息
    result_msg = Message(f"🎰 禁言大转盘\n\n")
    result_msg += MessageSegment.at(user_id)
    result_msg += Message(f" 转动了转盘...\n\n")

    if img_seg:
        result_msg += img_seg
        result_msg += Message("\n")

    result_msg += Message(f"🎯 结果：{format_duration(selected_duration)}！")

    await bot.send_group_msg(group_id=event.group_id, message=result_msg)

    # 执行禁言
    try:
        await bot.set_group_ban(
            group_id=event.group_id,
            user_id=int(user_id),
            duration=selected_duration
        )
    except Exception as e:
        logger.error(f"禁言失败: {e}")
        await bot.send_group_msg(
            group_id=event.group_id,
            message=f"⚠️ 禁言执行失败：{str(e)[:50]}\n（可能是权限不足）"
        )
