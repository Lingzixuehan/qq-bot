"""
Steam图片渲染模块

提供Steam好友列表和玩家状态的可视化渲染功能
"""
import colorsys
import random
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# 资源目录
RES_DIR = Path(__file__).parent / "res"

# 字体路径
FONT_PATHS = {
    "regular": "/home/user/qq-bot/fonts/MiSans-Regular.ttf",
    "light": "/home/user/qq-bot/fonts/MiSans-Light.ttf",
    "bold": "/home/user/qq-bot/fonts/MiSans-Bold.ttf",
}

# 字体大小常量
FONT_SIZE_TITLE = 48
FONT_SIZE_SUBTITLE = 36
FONT_SIZE_LARGE = 32
FONT_SIZE_MEDIUM = 28
FONT_SIZE_NORMAL = 24
FONT_SIZE_SMALL = 20
FONT_SIZE_TINY = 16

# 状态颜色
STATUS_COLORS = {
    "gaming": (144, 186, 106),  # 绿色 - 游戏中
    "online": (87, 166, 214),   # 蓝色 - 在线
    "offline": (128, 128, 128), # 灰色 - 离线
    "busy": (200, 100, 100),    # 红色 - 忙碌
}

# 在线状态映射
PERSONA_STATE_MAP = {
    0: "offline",  # 离线
    1: "online",   # 在线
    2: "busy",     # 忙碌
    3: "online",   # 离开
    4: "online",   # 打盹
    5: "online",   # 想交易
    6: "online",   # 想玩游戏
}


# ==================== 字体管理 ====================


def set_font_paths(
    regular: Optional[str] = None,
    light: Optional[str] = None,
    bold: Optional[str] = None
) -> None:
    """
    设置字体文件路径

    Args:
        regular: 常规字体路径
        light: 细体字体路径
        bold: 粗体字体路径
    """
    if regular:
        FONT_PATHS["regular"] = regular
    if light:
        FONT_PATHS["light"] = light
    if bold:
        FONT_PATHS["bold"] = bold


def check_font() -> bool:
    """
    检查字体文件是否存在

    Returns:
        所有字体文件都存在返回True，否则返回False
    """
    for font_type, font_path in FONT_PATHS.items():
        if not Path(font_path).exists():
            return False
    return True


def get_font(size: int, font_type: str = "regular") -> ImageFont.FreeTypeFont:
    """
    获取指定大小和类型的字体

    Args:
        size: 字体大小
        font_type: 字体类型 (regular/light/bold)

    Returns:
        ImageFont对象
    """
    font_path = FONT_PATHS.get(font_type, FONT_PATHS["regular"])
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        return ImageFont.load_default()


# ==================== 图像工具函数 ====================


def vertically_concatenate_images(images: List[Image.Image], spacing: int = 0) -> Image.Image:
    """
    垂直拼接图片列表

    Args:
        images: 图片列表
        spacing: 图片间距（像素）

    Returns:
        拼接后的图片
    """
    if not images:
        return Image.new("RGBA", (1, 1), (255, 255, 255, 0))

    # 计算总宽度和高度
    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images) + spacing * (len(images) - 1)

    # 创建新图片
    result = Image.new("RGBA", (max_width, total_height), (255, 255, 255, 0))

    # 粘贴图片
    y_offset = 0
    for img in images:
        result.paste(img, (0, y_offset), img if img.mode == "RGBA" else None)
        y_offset += img.height + spacing

    return result


def split_image(image: Image.Image, rows: int, cols: int) -> List[List[Image.Image]]:
    """
    将图片分割成网格

    Args:
        image: 要分割的图片
        rows: 行数
        cols: 列数

    Returns:
        二维图片列表 [行][列]
    """
    width, height = image.size
    piece_width = width // cols
    piece_height = height // rows

    pieces = []
    for row in range(rows):
        row_pieces = []
        for col in range(cols):
            left = col * piece_width
            top = row * piece_height
            right = left + piece_width
            bottom = top + piece_height
            piece = image.crop((left, top, right, bottom))
            row_pieces.append(piece)
        pieces.append(row_pieces)

    return pieces


def get_average_color(image: Image.Image) -> Tuple[int, int, int]:
    """
    计算图片的平均颜色

    Args:
        image: PIL Image对象

    Returns:
        RGB颜色元组
    """
    # 缩小图片以提高性能
    img = image.copy()
    img.thumbnail((100, 100))
    img = img.convert("RGB")

    # 计算平均值
    np_img = np.array(img)
    avg_color = np_img.mean(axis=(0, 1))

    return tuple(int(c) for c in avg_color)


def get_brightest_and_darkest_color(
    image: Image.Image,
    sample_size: int = 100,
    saturation_threshold: float = 0.3
) -> Tuple[Tuple[int, int, int], Tuple[int, int, int]]:
    """
    通过HSV饱和度获取图片中最鲜艳的亮色和暗色

    Args:
        image: PIL Image对象
        sample_size: 采样大小
        saturation_threshold: 饱和度阈值

    Returns:
        (最亮的鲜艳色, 最暗的鲜艳色) RGB元组
    """
    # 缩小图片
    img = image.copy()
    img.thumbnail((sample_size, sample_size))
    img = img.convert("RGB")

    # 转换为numpy数组
    np_img = np.array(img).reshape(-1, 3)

    # 转换为HSV
    vivid_colors = []
    for rgb in np_img:
        r, g, b = rgb / 255.0
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        if s >= saturation_threshold:  # 只保留饱和度高的颜色
            vivid_colors.append((v, tuple(rgb)))

    if not vivid_colors:
        # 如果没有鲜艳颜色，使用平均色
        avg = get_average_color(image)
        return avg, avg

    # 按明度排序
    vivid_colors.sort(key=lambda x: x[0])

    # 返回最暗和最亮的鲜艳色
    darkest = vivid_colors[0][1]
    brightest = vivid_colors[-1][1]

    return brightest, darkest


def recolor_image(
    size: Tuple[int, int],
    color: Tuple[int, int, int],
    alpha: int = 255
) -> Image.Image:
    """
    创建指定颜色的圆形图像

    Args:
        size: 图像大小 (width, height)
        color: RGB颜色
        alpha: 透明度 (0-255)

    Returns:
        圆形颜色图像
    """
    img = Image.new("RGBA", size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # 绘制圆形
    draw.ellipse([0, 0, size[0] - 1, size[1] - 1], fill=(*color, alpha))

    return img


def create_gradient_image(
    width: int,
    height: int,
    start_color: Tuple[int, int, int],
    end_color: Tuple[int, int, int],
    alpha: int = 255
) -> Image.Image:
    """
    创建水平渐变图像

    Args:
        width: 宽度
        height: 高度
        start_color: 起始颜色 RGB
        end_color: 结束颜色 RGB
        alpha: 透明度 (0-255)

    Returns:
        渐变图像
    """
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    for x in range(width):
        # 计算当前位置的颜色
        ratio = x / width
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)

        draw.line([(x, 0), (x, height)], fill=(r, g, b, alpha))

    return img


def create_vertical_gradient_rect(
    width: int,
    height: int,
    start_color: Tuple[int, int, int, int],
    end_color: Tuple[int, int, int, int]
) -> Image.Image:
    """
    创建垂直渐变矩形

    Args:
        width: 宽度
        height: 高度
        start_color: 起始颜色 RGBA
        end_color: 结束颜色 RGBA

    Returns:
        垂直渐变图像
    """
    img = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        # 计算当前位置的颜色
        ratio = y / height
        r = int(start_color[0] + (end_color[0] - start_color[0]) * ratio)
        g = int(start_color[1] + (end_color[1] - start_color[1]) * ratio)
        b = int(start_color[2] + (end_color[2] - start_color[2]) * ratio)
        a = int(start_color[3] + (end_color[3] - start_color[3]) * ratio)

        draw.line([(0, y), (width, y)], fill=(r, g, b, a))

    return img


def rounded_rectangle(
    size: Tuple[int, int],
    radius: int,
    fill_color: Tuple[int, int, int, int],
    border_color: Optional[Tuple[int, int, int, int]] = None,
    border_width: int = 0
) -> Image.Image:
    """
    创建圆角矩形

    Args:
        size: 尺寸 (width, height)
        radius: 圆角半径
        fill_color: 填充颜色 RGBA
        border_color: 边框颜色 RGBA
        border_width: 边框宽度

    Returns:
        圆角矩形图像
    """
    width, height = size
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # 绘制圆角矩形
    draw.rounded_rectangle(
        [(0, 0), (width - 1, height - 1)],
        radius=radius,
        fill=fill_color,
        outline=border_color if border_color else None,
        width=border_width
    )

    return img


def create_progress_bar(
    width: int,
    height: int,
    progress: float,
    bg_color: Tuple[int, int, int, int] = (50, 50, 50, 255),
    fg_color: Tuple[int, int, int, int] = (100, 180, 255, 255),
    radius: int = 0
) -> Image.Image:
    """
    创建进度条

    Args:
        width: 宽度
        height: 高度
        progress: 进度 (0.0-1.0)
        bg_color: 背景颜色 RGBA
        fg_color: 前景颜色 RGBA
        radius: 圆角半径

    Returns:
        进度条图像
    """
    progress = max(0.0, min(1.0, progress))
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))

    # 绘制背景
    bg = rounded_rectangle((width, height), radius, bg_color)
    img.paste(bg, (0, 0), bg)

    # 绘制进度
    if progress > 0:
        progress_width = int(width * progress)
        if progress_width > 0:
            fg = rounded_rectangle((progress_width, height), radius, fg_color)
            img.paste(fg, (0, 0), fg)

    return img


def random_color_offset(
    color: Tuple[int, int, int],
    max_offset: int = 30
) -> Tuple[int, int, int]:
    """
    对颜色添加随机偏移

    Args:
        color: RGB颜色
        max_offset: 最大偏移量

    Returns:
        偏移后的RGB颜色
    """
    r, g, b = color
    r = max(0, min(255, r + random.randint(-max_offset, max_offset)))
    g = max(0, min(255, g + random.randint(-max_offset, max_offset)))
    b = max(0, min(255, b + random.randint(-max_offset, max_offset)))
    return (r, g, b)


# ==================== 核心绘制函数 ====================


def draw_friend_status(
    avatar: Image.Image,
    name: str,
    status_text: str,
    game_name: Optional[str] = None,
    status_type: str = "offline",
    width: int = 500,
    height: int = 100
) -> Image.Image:
    """
    绘制单个好友状态卡片

    Args:
        avatar: 头像图片
        name: 玩家名称
        status_text: 状态文本
        game_name: 游戏名称（可选）
        status_type: 状态类型 (gaming/online/offline/busy)
        width: 卡片宽度
        height: 卡片高度

    Returns:
        好友状态卡片图像
    """
    # 创建画布
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)

    # 背景
    bg_color = (40, 40, 45, 230)
    bg = rounded_rectangle((width, height), 15, bg_color)
    img.paste(bg, (0, 0), bg)

    # 处理头像
    avatar_size = height - 20
    avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    # 创建圆形头像遮罩
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)

    # 粘贴头像
    img.paste(avatar, (10, 10), mask)

    # 状态指示器
    status_color = STATUS_COLORS.get(status_type, STATUS_COLORS["offline"])
    status_indicator = recolor_image((20, 20), status_color, 255)
    img.paste(status_indicator, (avatar_size, height - 25), status_indicator)

    # 文本区域
    text_x = avatar_size + 30
    text_y_start = 15

    # 绘制名称
    font_name = get_font(FONT_SIZE_NORMAL, "bold")
    draw.text((text_x, text_y_start), name, fill=(255, 255, 255, 255), font=font_name)

    # 绘制状态
    font_status = get_font(FONT_SIZE_SMALL, "regular")
    status_y = text_y_start + 30
    draw.text((text_x, status_y), status_text, fill=(180, 180, 180, 255), font=font_status)

    # 绘制游戏名称
    if game_name:
        font_game = get_font(FONT_SIZE_SMALL, "light")
        game_y = status_y + 25
        # 截断过长的游戏名
        max_game_width = width - text_x - 20
        game_text = game_name
        if draw.textlength(game_text, font=font_game) > max_game_width:
            while draw.textlength(game_text + "...", font=font_game) > max_game_width and len(game_text) > 0:
                game_text = game_text[:-1]
            game_text += "..."
        draw.text((text_x, game_y), game_text, fill=(144, 186, 106, 255), font=font_game)

    return img


def draw_gaming_friends_status(
    friends_data: List[Dict[str, Any]],
    avatars: Dict[str, Image.Image],
    title: str = "游戏中"
) -> Optional[Image.Image]:
    """
    绘制正在游戏的好友列表

    Args:
        friends_data: 好友数据列表
        avatars: 头像字典 {steamid: Image}
        title: 标题文本

    Returns:
        好友列表图像，如果没有好友则返回None
    """
    if not friends_data:
        return None

    card_width = 520
    card_height = 100
    spacing = 15
    padding = 30

    # 创建标题
    title_height = 60
    title_img = Image.new("RGBA", (card_width + padding * 2, title_height), (255, 255, 255, 0))
    title_draw = ImageDraw.Draw(title_img)

    # 加载游戏图标
    gaming_icon_path = RES_DIR / "gaming.png"
    if gaming_icon_path.exists():
        gaming_icon = Image.open(gaming_icon_path).convert("RGBA")
        gaming_icon = gaming_icon.resize((40, 40), Image.Resampling.LANCZOS)
        title_img.paste(gaming_icon, (padding, 10), gaming_icon)

    # 绘制标题文字
    font_title = get_font(FONT_SIZE_SUBTITLE, "bold")
    title_draw.text((padding + 50, 10), title, fill=(144, 186, 106, 255), font=font_title)

    # 绘制好友卡片
    cards = []
    for friend in friends_data:
        steamid = friend.get("steamid", "")
        avatar = avatars.get(steamid, Image.new("RGB", (100, 100), (100, 100, 100)))
        name = friend.get("personaname", "Unknown")
        game_name = friend.get("gameextrainfo", "未知游戏")

        card = draw_friend_status(
            avatar=avatar,
            name=name,
            status_text="正在游戏",
            game_name=game_name,
            status_type="gaming",
            width=card_width,
            height=card_height
        )
        cards.append(card)

    # 垂直拼接所有卡片
    cards_img = vertically_concatenate_images(cards, spacing)

    # 创建最终图像
    total_height = title_height + cards_img.height + spacing
    final_img = Image.new("RGBA", (card_width + padding * 2, total_height), (255, 255, 255, 0))
    final_img.paste(title_img, (0, 0), title_img)
    final_img.paste(cards_img, (padding, title_height + spacing), cards_img)

    return final_img


def draw_online_friends_status(
    friends_data: List[Dict[str, Any]],
    avatars: Dict[str, Image.Image],
    title: str = "在线"
) -> Optional[Image.Image]:
    """
    绘制在线好友列表

    Args:
        friends_data: 好友数据列表
        avatars: 头像字典 {steamid: Image}
        title: 标题文本

    Returns:
        好友列表图像，如果没有好友则返回None
    """
    if not friends_data:
        return None

    card_width = 520
    card_height = 100
    spacing = 15
    padding = 30

    # 创建标题
    title_height = 60
    title_img = Image.new("RGBA", (card_width + padding * 2, title_height), (255, 255, 255, 0))
    title_draw = ImageDraw.Draw(title_img)

    # 加载在线图标
    online_icon_path = RES_DIR / "zzz_online.png"
    if online_icon_path.exists():
        online_icon = Image.open(online_icon_path).convert("RGBA")
        online_icon = online_icon.resize((40, 40), Image.Resampling.LANCZOS)
        title_img.paste(online_icon, (padding, 10), online_icon)

    # 绘制标题文字
    font_title = get_font(FONT_SIZE_SUBTITLE, "bold")
    title_draw.text((padding + 50, 10), title, fill=(87, 166, 214, 255), font=font_title)

    # 绘制好友卡片
    cards = []
    for friend in friends_data:
        steamid = friend.get("steamid", "")
        avatar = avatars.get(steamid, Image.new("RGB", (100, 100), (100, 100, 100)))
        name = friend.get("personaname", "Unknown")

        # 获取状态文本
        persona_state = friend.get("personastate", 1)
        state_texts = {1: "在线", 2: "忙碌", 3: "离开", 4: "打盹", 5: "想交易", 6: "想玩游戏"}
        status_text = state_texts.get(persona_state, "在线")

        card = draw_friend_status(
            avatar=avatar,
            name=name,
            status_text=status_text,
            status_type="online" if persona_state != 2 else "busy",
            width=card_width,
            height=card_height
        )
        cards.append(card)

    # 垂直拼接所有卡片
    cards_img = vertically_concatenate_images(cards, spacing)

    # 创建最终图像
    total_height = title_height + cards_img.height + spacing
    final_img = Image.new("RGBA", (card_width + padding * 2, total_height), (255, 255, 255, 0))
    final_img.paste(title_img, (0, 0), title_img)
    final_img.paste(cards_img, (padding, title_height + spacing), cards_img)

    return final_img


def draw_offline_friends_status(
    friends_data: List[Dict[str, Any]],
    avatars: Dict[str, Image.Image],
    title: str = "离线"
) -> Optional[Image.Image]:
    """
    绘制离线好友列表

    Args:
        friends_data: 好友数据列表
        avatars: 头像字典 {steamid: Image}
        title: 标题文本

    Returns:
        好友列表图像，如果没有好友则返回None
    """
    if not friends_data:
        return None

    card_width = 520
    card_height = 100
    spacing = 15
    padding = 30

    # 创建标题
    title_height = 60
    title_img = Image.new("RGBA", (card_width + padding * 2, title_height), (255, 255, 255, 0))
    title_draw = ImageDraw.Draw(title_img)

    # 绘制标题文字
    font_title = get_font(FONT_SIZE_SUBTITLE, "bold")
    title_draw.text((padding, 10), title, fill=(128, 128, 128, 255), font=font_title)

    # 绘制好友卡片
    cards = []
    for friend in friends_data:
        steamid = friend.get("steamid", "")
        avatar = avatars.get(steamid, Image.new("RGB", (100, 100), (100, 100, 100)))
        name = friend.get("personaname", "Unknown")

        # 计算离线时间
        lastlogoff = friend.get("lastlogoff", 0)
        status_text = "离线"
        if lastlogoff > 0:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).timestamp()
            offline_seconds = int(now - lastlogoff)
            if offline_seconds < 3600:
                minutes = offline_seconds // 60
                status_text = f"离线 {minutes}分钟"
            elif offline_seconds < 86400:
                hours = offline_seconds // 3600
                status_text = f"离线 {hours}小时"
            else:
                days = offline_seconds // 86400
                status_text = f"离线 {days}天"

        card = draw_friend_status(
            avatar=avatar,
            name=name,
            status_text=status_text,
            status_type="offline",
            width=card_width,
            height=card_height
        )
        cards.append(card)

    # 垂直拼接所有卡片
    cards_img = vertically_concatenate_images(cards, spacing)

    # 创建最终图像
    total_height = title_height + cards_img.height + spacing
    final_img = Image.new("RGBA", (card_width + padding * 2, total_height), (255, 255, 255, 0))
    final_img.paste(title_img, (0, 0), title_img)
    final_img.paste(cards_img, (padding, title_height + spacing), cards_img)

    return final_img


def draw_friends_status(
    friends_data: List[Dict[str, Any]],
    avatars: Dict[str, Image.Image],
    show_title: bool = True
) -> Image.Image:
    """
    绘制完整的好友状态列表（包含所有分类）

    Args:
        friends_data: 好友数据列表
        avatars: 头像字典 {steamid: Image}
        show_title: 是否显示总标题

    Returns:
        完整的好友状态图像
    """
    # 分类好友
    gaming_friends = []
    online_friends = []
    offline_friends = []

    for friend in friends_data:
        if friend.get("gameextrainfo"):
            gaming_friends.append(friend)
        elif friend.get("personastate", 0) > 0:
            online_friends.append(friend)
        else:
            offline_friends.append(friend)

    # 绘制各个分类
    sections = []

    gaming_img = draw_gaming_friends_status(gaming_friends, avatars)
    if gaming_img:
        sections.append(gaming_img)

    online_img = draw_online_friends_status(online_friends, avatars)
    if online_img:
        sections.append(online_img)

    offline_img = draw_offline_friends_status(offline_friends, avatars)
    if offline_img:
        sections.append(offline_img)

    if not sections:
        # 没有好友
        empty_img = Image.new("RGBA", (580, 200), (255, 255, 255, 0))
        draw = ImageDraw.Draw(empty_img)
        font = get_font(FONT_SIZE_LARGE, "regular")
        draw.text((290, 100), "暂无好友数据", fill=(128, 128, 128, 255), font=font, anchor="mm")
        sections.append(empty_img)

    # 拼接所有分类
    result = vertically_concatenate_images(sections, 30)

    # 添加总标题
    if show_title:
        padding = 30
        title_height = 80
        title_img = Image.new("RGBA", (result.width, title_height), (255, 255, 255, 0))
        title_draw = ImageDraw.Draw(title_img)

        # 加载好友搜索图标
        friends_icon_path = RES_DIR / "friends_search.png"
        if friends_icon_path.exists():
            friends_icon = Image.open(friends_icon_path).convert("RGBA")
            friends_icon = friends_icon.resize((50, 50), Image.Resampling.LANCZOS)
            title_img.paste(friends_icon, (padding, 15), friends_icon)

        # 标题文字
        font_title = get_font(FONT_SIZE_TITLE, "bold")
        title_text = f"好友列表 ({len(friends_data)})"
        title_draw.text((padding + 60, 15), title_text, fill=(255, 255, 255, 255), font=font_title)

        # 拼接标题和内容
        final_img = vertically_concatenate_images([title_img, result], 20)
        result = final_img

    # 添加背景
    bg_width = result.width + 60
    bg_height = result.height + 60
    bg_dots_path = RES_DIR / "bg_dots.png"
    if bg_dots_path.exists():
        bg = Image.open(bg_dots_path).convert("RGBA")
        bg = bg.resize((bg_width, bg_height), Image.Resampling.LANCZOS)
    else:
        bg = Image.new("RGBA", (bg_width, bg_height), (30, 30, 35, 255))

    bg.paste(result, (30, 30), result)

    return bg


def draw_player_status(
    player_name: str,
    avatar: Image.Image,
    background: Image.Image,
    description: str,
    recent_playtime: str,
    game_data: List[Dict[str, Any]],
    width: int = 1000,
) -> Image.Image:
    """
    绘制玩家详细状态卡片

    Args:
        player_name: 玩家名称
        avatar: 头像图片
        background: 背景图片
        description: 玩家描述/状态
        recent_playtime: 最近游戏时长
        game_data: 游戏数据列表
        width: 卡片宽度

    Returns:
        玩家状态卡片图像
    """
    padding = 40
    header_height = 250

    # 处理背景
    bg = background.copy()
    # 获取背景主色调
    bright_color, dark_color = get_brightest_and_darkest_color(bg)

    # 创建顶部区域
    header_img = Image.new("RGBA", (width, header_height), (255, 255, 255, 0))

    # 背景图片（模糊处理）
    bg_resized = bg.resize((width, header_height), Image.Resampling.LANCZOS)
    bg_resized = bg_resized.filter(ImageFilter.GaussianBlur(10))

    # 添加渐变遮罩
    gradient = create_vertical_gradient_rect(
        width, header_height,
        (0, 0, 0, 150),
        (0, 0, 0, 200)
    )
    bg_resized.paste(gradient, (0, 0), gradient)

    header_img.paste(bg_resized, (0, 0), bg_resized)

    # 头像
    avatar_size = 150
    avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    # 圆形头像遮罩
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)

    # 添加边框
    avatar_with_border = Image.new("RGBA", (avatar_size + 10, avatar_size + 10), (255, 255, 255, 0))
    border_draw = ImageDraw.Draw(avatar_with_border)
    border_draw.ellipse([0, 0, avatar_size + 9, avatar_size + 9], outline=bright_color, width=5)
    avatar_with_border.paste(avatar, (5, 5), mask)

    header_img.paste(avatar_with_border, (padding, padding), avatar_with_border)

    # 文本信息
    draw = ImageDraw.Draw(header_img)
    text_x = padding + avatar_size + 30
    text_y = padding

    # 玩家名称
    font_name = get_font(FONT_SIZE_TITLE, "bold")
    draw.text((text_x, text_y), player_name, fill=(255, 255, 255, 255), font=font_name)

    # 描述
    font_desc = get_font(FONT_SIZE_NORMAL, "regular")
    desc_y = text_y + 60
    draw.text((text_x, desc_y), description, fill=(200, 200, 200, 255), font=font_desc)

    # 最近游戏时长
    font_time = get_font(FONT_SIZE_SMALL, "light")
    time_y = desc_y + 40
    draw.text((text_x, time_y), f"最近两周: {recent_playtime}", fill=(150, 150, 150, 255), font=font_time)

    # 绘制游戏列表
    game_cards = []
    for game in game_data:
        game_card = draw_game_info(
            game_name=game.get("game_name", "未知游戏"),
            play_time=game.get("play_time", "0小时"),
            last_played=game.get("last_played", "从未"),
            game_image=game.get("game_image"),
            achievements=game.get("achievements", []),
            completed=game.get("completed_achievement_number", 0),
            total=game.get("total_achievement_number", 0),
            width=width - padding * 2
        )
        game_cards.append(game_card)

    # 拼接所有内容
    if game_cards:
        games_img = vertically_concatenate_images(game_cards, 20)
        total_height = header_height + 30 + games_img.height + padding
        final_img = Image.new("RGBA", (width, total_height), (30, 30, 35, 255))
        final_img.paste(header_img, (0, 0), header_img)
        final_img.paste(games_img, (padding, header_height + 30), games_img)
    else:
        total_height = header_height + padding
        final_img = Image.new("RGBA", (width, total_height), (30, 30, 35, 255))
        final_img.paste(header_img, (0, 0), header_img)

    return final_img


def draw_game_info(
    game_name: str,
    play_time: str,
    last_played: str,
    game_image: Optional[bytes] = None,
    achievements: Optional[List[Dict[str, Any]]] = None,
    completed: int = 0,
    total: int = 0,
    width: int = 920
) -> Image.Image:
    """
    绘制单个游戏信息卡片

    Args:
        game_name: 游戏名称
        play_time: 游戏时长
        last_played: 最后游玩时间
        game_image: 游戏头图（字节数据）
        achievements: 成就列表
        completed: 已完成成就数
        total: 总成就数
        width: 卡片宽度

    Returns:
        游戏信息卡片图像
    """
    height = 200
    padding = 20

    # 创建背景
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    bg = rounded_rectangle((width, height), 15, (45, 45, 50, 255))
    img.paste(bg, (0, 0), bg)

    # 游戏头图
    header_width = 300
    header_height = height - padding * 2

    if game_image:
        try:
            game_img = Image.open(BytesIO(game_image)).convert("RGBA")
            game_img = game_img.resize((header_width, header_height), Image.Resampling.LANCZOS)
        except Exception:
            # 使用默认图片
            default_path = RES_DIR / "default_header_image.jpg"
            if default_path.exists():
                game_img = Image.open(default_path).convert("RGBA")
                game_img = game_img.resize((header_width, header_height), Image.Resampling.LANCZOS)
            else:
                game_img = Image.new("RGBA", (header_width, header_height), (60, 60, 65, 255))
    else:
        default_path = RES_DIR / "default_header_image.jpg"
        if default_path.exists():
            game_img = Image.open(default_path).convert("RGBA")
            game_img = game_img.resize((header_width, header_height), Image.Resampling.LANCZOS)
        else:
            game_img = Image.new("RGBA", (header_width, header_height), (60, 60, 65, 255))

    # 圆角遮罩
    game_img_rounded = rounded_rectangle((header_width, header_height), 10, (255, 255, 255, 255))
    game_img_rounded.paste(game_img, (0, 0), game_img_rounded)
    img.paste(game_img_rounded, (padding, padding), game_img_rounded)

    # 文本信息
    draw = ImageDraw.Draw(img)
    text_x = padding + header_width + 25
    text_y = padding + 10

    # 游戏名称
    font_name = get_font(FONT_SIZE_LARGE, "bold")
    max_name_width = width - text_x - padding - 20
    game_name_display = game_name
    if draw.textlength(game_name_display, font=font_name) > max_name_width:
        while draw.textlength(game_name_display + "...", font=font_name) > max_name_width and len(game_name_display) > 0:
            game_name_display = game_name_display[:-1]
        game_name_display += "..."
    draw.text((text_x, text_y), game_name_display, fill=(255, 255, 255, 255), font=font_name)

    # 游戏时长
    font_info = get_font(FONT_SIZE_SMALL, "regular")
    info_y = text_y + 45
    draw.text((text_x, info_y), f"游戏时长: {play_time}", fill=(180, 180, 180, 255), font=font_info)

    # 最后游玩
    last_y = info_y + 30
    draw.text((text_x, last_y), f"最后游玩: {last_played}", fill=(150, 150, 150, 255), font=font_info)

    # 成就进度
    if total > 0:
        achievement_y = last_y + 40
        progress = completed / total

        # 进度条
        progress_bar_width = width - text_x - padding - 20
        progress_bar = create_progress_bar(
            progress_bar_width, 20, progress,
            bg_color=(60, 60, 65, 255),
            fg_color=(100, 180, 255, 255),
            radius=10
        )
        img.paste(progress_bar, (text_x, achievement_y), progress_bar)

        # 成就文本
        achievement_text = f"{completed}/{total} 成就"
        font_achievement = get_font(FONT_SIZE_TINY, "regular")
        draw.text(
            (text_x + progress_bar_width // 2, achievement_y + 2),
            achievement_text,
            fill=(255, 255, 255, 255),
            font=font_achievement,
            anchor="mm"
        )

    # 显示成就图标
    if achievements:
        icon_size = 40
        icon_spacing = 10
        icon_y = height - padding - icon_size
        icon_x_start = text_x

        displayed = 0
        max_display = min(len(achievements), (width - text_x - padding - 20) // (icon_size + icon_spacing))

        for i, achievement in enumerate(achievements[:max_display]):
            if "image" not in achievement:
                continue

            try:
                ach_img = Image.open(BytesIO(achievement["image"])).convert("RGBA")
                ach_img = ach_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)

                # 圆角遮罩
                ach_mask = rounded_rectangle((icon_size, icon_size), 8, (255, 255, 255, 255))
                ach_img_rounded = Image.new("RGBA", (icon_size, icon_size), (255, 255, 255, 0))
                ach_img_rounded.paste(ach_img, (0, 0), ach_mask)

                icon_x = icon_x_start + displayed * (icon_size + icon_spacing)
                img.paste(ach_img_rounded, (icon_x, icon_y), ach_img_rounded)
                displayed += 1
            except Exception:
                continue

    return img


def draw_start_gaming(
    player_name: str,
    game_name: str,
    avatar: Image.Image,
    width: int = 600,
    height: int = 200
) -> Image.Image:
    """
    绘制开始游戏通知卡片

    Args:
        player_name: 玩家名称
        game_name: 游戏名称
        avatar: 头像图片
        width: 卡片宽度
        height: 卡片高度

    Returns:
        开始游戏通知卡片图像
    """
    # 创建背景
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))

    # 背景渐变
    gradient = create_gradient_image(width, height, (60, 80, 60), (40, 60, 40), 230)
    bg = rounded_rectangle((width, height), 20, (255, 255, 255, 0))
    gradient_rounded = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    gradient_rounded.paste(gradient, (0, 0), bg)
    img.paste(gradient_rounded, (0, 0), gradient_rounded)

    # 头像
    avatar_size = height - 40
    avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    # 圆形头像遮罩
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse([0, 0, avatar_size, avatar_size], fill=255)

    img.paste(avatar, (20, 20), mask)

    # 游戏图标
    gaming_icon_path = RES_DIR / "zzz_gaming.png"
    if gaming_icon_path.exists():
        gaming_icon = Image.open(gaming_icon_path).convert("RGBA")
        gaming_icon = gaming_icon.resize((50, 50), Image.Resampling.LANCZOS)
        img.paste(gaming_icon, (avatar_size + 10, height - 60), gaming_icon)

    # 文本
    draw = ImageDraw.Draw(img)
    text_x = avatar_size + 40
    text_y = 30

    # 玩家名称
    font_name = get_font(FONT_SIZE_LARGE, "bold")
    draw.text((text_x, text_y), player_name, fill=(255, 255, 255, 255), font=font_name)

    # 状态文本
    font_status = get_font(FONT_SIZE_MEDIUM, "regular")
    status_y = text_y + 50
    draw.text((text_x, status_y), "正在游戏", fill=(144, 186, 106, 255), font=font_status)

    # 游戏名称
    font_game = get_font(FONT_SIZE_NORMAL, "light")
    game_y = status_y + 45
    max_game_width = width - text_x - 30
    game_text = game_name
    if draw.textlength(game_text, font=font_game) > max_game_width:
        while draw.textlength(game_text + "...", font=font_game) > max_game_width and len(game_text) > 0:
            game_text = game_text[:-1]
        game_text += "..."
    draw.text((text_x, game_y), game_text, fill=(220, 220, 220, 255), font=font_game)

    return img


def draw_parent_status(
    parent_name: str,
    friend_count: int,
    gaming_count: int,
    online_count: int,
    offline_count: int,
    width: int = 600,
    height: int = 250
) -> Image.Image:
    """
    绘制群组/父级状态信息卡片

    Args:
        parent_name: 群组名称
        friend_count: 好友总数
        gaming_count: 游戏中人数
        online_count: 在线人数
        offline_count: 离线人数
        width: 卡片宽度
        height: 卡片高度

    Returns:
        群组状态卡片图像
    """
    # 创建背景
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    bg = rounded_rectangle((width, height), 20, (40, 40, 45, 240))
    img.paste(bg, (0, 0), bg)

    draw = ImageDraw.Draw(img)
    padding = 30

    # 加载图标
    icon_path = RES_DIR / "parent_status.png"
    if icon_path.exists():
        icon = Image.open(icon_path).convert("RGBA")
        icon = icon.resize((60, 60), Image.Resampling.LANCZOS)
        img.paste(icon, (padding, padding), icon)

    # 标题
    font_title = get_font(FONT_SIZE_SUBTITLE, "bold")
    title_x = padding + 75
    draw.text((title_x, padding), parent_name, fill=(255, 255, 255, 255), font=font_title)

    # 统计信息
    stats_y = padding + 75
    font_stats = get_font(FONT_SIZE_NORMAL, "regular")

    # 好友总数
    draw.text((padding, stats_y), f"好友总数: {friend_count}", fill=(200, 200, 200, 255), font=font_stats)

    # 状态统计
    stats_y += 45
    gaming_text = f"游戏中: {gaming_count}"
    draw.text((padding, stats_y), gaming_text, fill=STATUS_COLORS["gaming"], font=font_stats)

    online_text = f"在线: {online_count}"
    draw.text((padding + 200, stats_y), online_text, fill=STATUS_COLORS["online"], font=font_stats)

    offline_text = f"离线: {offline_count}"
    draw.text((padding + 400, stats_y), offline_text, fill=STATUS_COLORS["offline"], font=font_stats)

    # 进度条
    bar_y = stats_y + 60
    bar_width = width - padding * 2
    bar_height = 30

    # 分段进度条
    if friend_count > 0:
        gaming_width = int(bar_width * gaming_count / friend_count)
        online_width = int(bar_width * online_count / friend_count)
        offline_width = bar_width - gaming_width - online_width

        # 背景
        bg_bar = rounded_rectangle((bar_width, bar_height), 15, (60, 60, 65, 255))
        img.paste(bg_bar, (padding, bar_y), bg_bar)

        # 游戏中部分
        if gaming_width > 0:
            gaming_bar = rounded_rectangle((gaming_width, bar_height), 15, (*STATUS_COLORS["gaming"], 255))
            img.paste(gaming_bar, (padding, bar_y), gaming_bar)

        # 在线部分
        if online_width > 0:
            online_bar = rounded_rectangle((online_width, bar_height), 15, (*STATUS_COLORS["online"], 255))
            img.paste(online_bar, (padding + gaming_width, bar_y), online_bar)

        # 离线部分（已经是背景色，不需要绘制）

    return img


def _render_tag_line(draw: ImageDraw.ImageDraw, tags: List[str], start_pos: Tuple[int, int], max_width: int) -> int:
    """绘制标签行，返回占用的高度"""
    x, y = start_pos
    tag_font = get_font(FONT_SIZE_TINY, "regular")
    tag_padding = 10
    tag_height = 28
    current_y = y
    for tag in tags:
        text_width = int(draw.textlength(tag, font=tag_font))
        box_width = text_width + tag_padding * 2
        if x + box_width > start_pos[0] + max_width:
            x = start_pos[0]
            current_y += tag_height + 6
        shape = [x, current_y, x + box_width, current_y + tag_height]
        draw.rounded_rectangle(shape, radius=10, fill=(70, 70, 80, 255))
        draw.text((x + tag_padding, current_y + 6), tag, font=tag_font, fill=(220, 220, 230, 255))
        x += box_width + 10

    return (current_y - y) + tag_height


def draw_game_list_with_tags(
    title: str,
    games: List[Dict[str, Any]],
    subtitle: str = "",
    width: int = 1100,
) -> Image.Image:
    """渲染包含标签和封面的游戏列表（史低推荐/热销榜通用）"""

    padding = 30
    header_height = 120
    card_height = 210
    card_spacing = 18
    total_height = header_height + padding + (card_height + card_spacing) * len(games) + padding
    img = Image.new("RGBA", (width, total_height), (24, 27, 33, 255))

    draw = ImageDraw.Draw(img)
    title_font = get_font(FONT_SIZE_TITLE, "bold")
    subtitle_font = get_font(FONT_SIZE_MEDIUM, "regular")
    draw.text((padding, padding), title, font=title_font, fill=(255, 255, 255, 255))
    if subtitle:
        draw.text((padding, padding + 60), subtitle, font=subtitle_font, fill=(190, 190, 200, 255))

    card_width = width - padding * 2
    y_offset = header_height

    for idx, game in enumerate(games, 1):
        card = Image.new("RGBA", (card_width, card_height), (255, 255, 255, 0))
        card_bg = rounded_rectangle((card_width, card_height), 18, (42, 45, 53, 255))
        card.paste(card_bg, (0, 0), card_bg)

        card_draw = ImageDraw.Draw(card)
        left_padding = 20
        image_w, image_h = 300, 170

        # 封面
        header = Image.new("RGBA", (image_w, image_h), (60, 65, 75, 255))
        if game.get("image"):
            try:
                header = Image.open(BytesIO(game["image"])).convert("RGBA")
                header = header.resize((image_w, image_h), Image.Resampling.LANCZOS)
            except Exception:
                pass
        header_mask = rounded_rectangle((image_w, image_h), 12, (255, 255, 255, 255))
        header_canvas = Image.new("RGBA", (image_w, image_h), (0, 0, 0, 0))
        header_canvas.paste(header, (0, 0), header_mask)
        card.paste(header_canvas, (left_padding, (card_height - image_h) // 2), header_canvas)

        # 文本块
        text_x = left_padding + image_w + 20
        name_font = get_font(FONT_SIZE_LARGE, "bold")
        info_font = get_font(FONT_SIZE_SMALL, "regular")
        tag_max_width = card_width - text_x - left_padding

        card_draw.text((left_padding + 4, 10), f"#{idx:02d}", font=info_font, fill=(140, 150, 170, 255))

        name = game.get("name", "未知游戏")
        max_name_width = card_width - text_x - 20
        while card_draw.textlength(name, font=name_font) > max_name_width and len(name) > 0:
            name = name[:-1]
        if card_draw.textlength(game.get("name", "未知游戏"), font=name_font) > max_name_width:
            name = name[:-1] + "..."
        card_draw.text((text_x, 24), name, font=name_font, fill=(245, 245, 248, 255))

        info_line = game.get("info", "")
        extra_line = game.get("extra", "")
        badge = game.get("badge")

        text_y = 70
        if info_line:
            card_draw.text((text_x, text_y), info_line, font=info_font, fill=(200, 230, 200, 255))
            text_y += 30
        if extra_line:
            card_draw.text((text_x, text_y), extra_line, font=info_font, fill=(190, 190, 200, 255))
            text_y += 30

        tags = game.get("tags", [])[:8]
        if tags:
            consumed = _render_tag_line(card_draw, tags, (text_x, text_y + 5), tag_max_width)
            text_y += consumed + 5

        if badge:
            badge_font = get_font(FONT_SIZE_SMALL, "bold")
            badge_w, badge_h = 70, 32
            badge_bg = rounded_rectangle((badge_w, badge_h), 10, (255, 108, 108, 230))
            card.paste(badge_bg, (card_width - badge_w - 20, 20), badge_bg)
            badge_draw = ImageDraw.Draw(card)
            badge_draw.text(
                (card_width - badge_w + 10, 24),
                badge,
                font=badge_font,
                fill=(255, 255, 255, 255),
            )

        img.paste(card, (padding, y_offset), card)
        y_offset += card_height + card_spacing

    return img
