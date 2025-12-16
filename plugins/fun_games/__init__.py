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

from ..common import require_fun_group
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


def _get_chinese_font(size: int):
    """获取支持中文的字体"""
    # 常见中文字体路径
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # 文泉驿正黑
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",  # 文泉驿微米黑
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Noto Sans CJK
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",  # Windows 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
        "/System/Library/Fonts/PingFang.ttc",  # macOS
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue

    # 如果都找不到，返回默认字体
    return ImageFont.load_default()


def _draw_roulette_frame(
    durations: list,
    rotation_angle: float,
    size: int = 400,
    highlight_index: int = -1,
    show_result: bool = False,
    result_text: str = ""
) -> Image.Image:
    """
    绘制转盘的单帧

    Args:
        durations: 时间选项列表
        rotation_angle: 转盘旋转角度（度）
        size: 图像尺寸
        highlight_index: 高亮的扇形索引（-1 表示不高亮）
        show_result: 是否显示结果文字
        result_text: 结果文字
    """
    center = size // 2
    radius = int(size * 0.38)

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

    # 加载字体
    font = _get_chinese_font(14)
    font_large = _get_chinese_font(20)

    # 绘制扇形（带旋转）
    for i, duration in enumerate(durations):
        # 计算旋转后的角度
        start_angle = i * angle_per_slice - 90 + rotation_angle
        end_angle = start_angle + angle_per_slice

        color = colors[i % len(colors)]

        # 如果是高亮的扇形，加深颜色
        if i == highlight_index:
            color = tuple(max(0, c - 60) for c in color)

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
    center_radius = int(size * 0.06)
    draw.ellipse(
        [center - center_radius, center - center_radius,
         center + center_radius, center + center_radius],
        fill=(255, 255, 255),
        outline=(50, 50, 50),
        width=3
    )

    # 绘制固定指针（在12点方向）
    pointer_y = center - radius - 15
    arrow_size = 18
    arrow_points = [
        (center, pointer_y + arrow_size),  # 指向转盘的尖端
        (center - arrow_size // 2, pointer_y),
        (center + arrow_size // 2, pointer_y),
    ]
    draw.polygon(arrow_points, fill=(255, 0, 0), outline=(150, 0, 0))

    # 绘制标题
    title = "禁言大转盘"
    bbox = draw.textbbox((0, 0), title, font=font_large)
    title_w = bbox[2] - bbox[0]
    draw.text((center - title_w / 2, 10), title, fill=(50, 50, 50), font=font_large)

    # 绘制结果（如果需要）
    if show_result and result_text:
        bbox = draw.textbbox((0, 0), result_text, font=font_large)
        result_w = bbox[2] - bbox[0]
        # 绘制背景框
        padding = 10
        draw.rectangle(
            [center - result_w // 2 - padding, size - 45,
             center + result_w // 2 + padding, size - 10],
            fill=(255, 255, 200),
            outline=(200, 150, 0),
            width=2
        )
        draw.text((center - result_w / 2, size - 42), result_text, fill=(200, 0, 0), font=font_large)

    return img


def draw_roulette_gif(durations: list, selected_index: int) -> bytes:
    """
    绘制转盘动图（GIF）

    Args:
        durations: 时间选项列表（秒）
        selected_index: 最终选中的索引

    Returns:
        GIF 图像数据
    """
    frames = []
    size = 400
    n = len(durations)
    angle_per_slice = 360 / n

    # 计算最终停止角度：让选中的扇形对准12点方向的指针
    # 指针在12点方向（-90度），扇形中心需要对准这个位置
    target_angle = -(selected_index * angle_per_slice + angle_per_slice / 2)

    # 转盘旋转动画：快速旋转几圈，然后减速停下
    total_rotation = 360 * 4 + target_angle  # 转4圈多

    # 使用缓动函数（ease-out）
    num_frames = 30

    for frame_idx in range(num_frames):
        # 缓动进度 (ease-out cubic)
        t = frame_idx / (num_frames - 1)
        eased_t = 1 - (1 - t) ** 3

        current_angle = total_rotation * eased_t

        # 判断当前指针指向哪个扇形
        normalized_angle = (-current_angle - 90) % 360
        current_slice = int(normalized_angle / angle_per_slice) % n

        # 最后几帧高亮选中的扇形
        highlight = selected_index if frame_idx >= num_frames - 5 else -1
        show_result = frame_idx == num_frames - 1
        result_text = f"结果: {format_duration(durations[selected_index])}" if show_result else ""

        frame = _draw_roulette_frame(
            durations,
            current_angle,
            size=size,
            highlight_index=highlight,
            show_result=show_result,
            result_text=result_text
        )

        # 转换为 P 模式以支持 GIF
        frame_p = frame.convert("P", palette=Image.ADAPTIVE, colors=256)
        frames.append(frame_p)

    # 最后一帧多停留一会
    for _ in range(10):
        frames.append(frames[-1].copy())

    # 导出为 GIF
    output = BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=[80] * (num_frames - 1) + [100] * 11,  # 最后停留久一点
        loop=0
    )
    return output.getvalue()


def draw_roulette(durations: list, selected_index: int) -> bytes:
    """
    绘制转盘静态图像（备用）

    Args:
        durations: 时间选项列表（秒）
        selected_index: 选中的索引

    Returns:
        PNG 图像数据
    """
    n = len(durations)
    angle_per_slice = 360 / n
    target_angle = -(selected_index * angle_per_slice + angle_per_slice / 2)

    img = _draw_roulette_frame(
        durations,
        target_angle,
        size=400,
        highlight_index=selected_index,
        show_result=True,
        result_text=f"结果: {format_duration(durations[selected_index])}"
    )

    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()


# ============== 魔女审判 ==============
witch_trial = on_command("魔女审判", priority=5, block=True)

@require_fun_group()

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
            logger.info(f"同意表情原始数据: {agree_data}")
            if isinstance(agree_data, dict):
                # 数据格式: {'result': 0, 'emojiLikesList': [...]}
                emoji_list = agree_data.get("emojiLikesList", [])
                if isinstance(emoji_list, list):
                    agree_count = len(emoji_list)
                    # 减去机器人自己贴的
                    agree_count = max(0, agree_count - 1)
                logger.info(f"同意票数: {agree_count}")
        except Exception as e:
            logger.warning(f"获取同意表情失败: {e}")

        try:
            disagree_data = await bot.call_api(
                "fetch_emoji_like",
                message_id=message_id,
                emojiId=EMOJI_DISAGREE,
                emojiType="1"
            )
            logger.info(f"反对表情原始数据: {disagree_data}")
            if isinstance(disagree_data, dict):
                # 数据格式: {'result': 0, 'emojiLikesList': [...]}
                emoji_list = disagree_data.get("emojiLikesList", [])
                if isinstance(emoji_list, list):
                    disagree_count = len(emoji_list)
                    # 减去机器人自己贴的
                    disagree_count = max(0, disagree_count - 1)
                logger.info(f"反对票数: {disagree_count}")
        except Exception as e:
            logger.warning(f"获取反对表情失败: {e}")
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

@require_fun_group()

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

    # 绘制转盘动图
    try:
        img_bytes = draw_roulette_gif(ROULETTE_DURATIONS, selected_index)
        img_seg = MessageSegment.image(f"base64://{__import__('base64').b64encode(img_bytes).decode()}")
    except Exception as e:
        logger.error(f"绘制转盘动图失败: {e}")
        # 失败时尝试静态图
        try:
            img_bytes = draw_roulette(ROULETTE_DURATIONS, selected_index)
            img_seg = MessageSegment.image(f"base64://{__import__('base64').b64encode(img_bytes).decode()}")
        except Exception as e2:
            logger.error(f"绘制转盘静态图也失败: {e2}")
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
