"""
Steam图片渲染模块

提供Steam好友列表和玩家状态的可视化渲染功能
仿照 Steam 好友列表样式和个人主页渲染
"""
import colorsys
import random
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
from colorsys import rgb_to_hsv, hsv_to_rgb

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# 资源目录
RES_DIR = Path(__file__).parent / "res"

# 字体路径（默认指向仓库内字体，避免中文显示乱码）
REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_PATHS = {
    "regular": str(REPO_ROOT / "fonts" / "MiSans-Regular.ttf"),
    "light": str(REPO_ROOT / "fonts" / "MiSans-Light.ttf"),
    "bold": str(REPO_ROOT / "fonts" / "MiSans-Bold.ttf"),
}

# Steam 好友列表样式常量
WIDTH = 400
PARENT_AVATAR_SIZE = 72
MEMBER_AVATAR_SIZE = 50

# 资源路径
unknown_avatar_path = RES_DIR / "unknown_avatar.jpg"
parent_status_path = RES_DIR / "parent_status.png"
friends_search_path = RES_DIR / "friends_search.png"
busy_path = RES_DIR / "busy.png"
zzz_online_path = RES_DIR / "zzz_online.png"
zzz_gaming_path = RES_DIR / "zzz_gaming.png"
gaming_path = RES_DIR / "gaming.png"

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

# Steam 状态颜色映射 (personastate -> (主色, 副色))
def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """十六进制颜色转RGB"""
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

personastate_colors = {
    0: (hex_to_rgb("969697"), hex_to_rgb("656565")),      # 离线 - 灰色
    1: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),      # 在线 - 蓝色
    2: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),      # 忙碌 - 蓝色
    3: (hex_to_rgb("45778e"), hex_to_rgb("365969")),      # 离开 - 深蓝
    4: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),      # 打盹 - 蓝色
    5: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),      # 查看招聘信息 - 蓝色
    6: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),      # 拥有物品待出售 - 蓝色
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


# ==================== Steam 风格好友列表渲染函数 ====================


def draw_start_gaming(
    avatar: Image.Image, friend_name: str, game_name: str, nickname: str = None
) -> Image.Image:
    """绘制开始游戏通知（Steam 风格）"""
    canvas = Image.open(gaming_path)
    canvas.paste(avatar.resize((66, 66), Image.BICUBIC), (15, 20))

    draw = ImageDraw.Draw(canvas)
    font_regular = ImageFont.truetype(FONT_PATHS["regular"], 19)
    font_bold = ImageFont.truetype(FONT_PATHS["bold"], 14)

    # 绘制名称
    draw.text(
        (104, 14),
        f"{friend_name} ({nickname})" if nickname is not None else friend_name,
        font=font_regular,
        fill=hex_to_rgb("e3ffc2"),
    )

    # 绘制"正在玩"
    draw.text(
        (103, 42),
        "正在玩",
        font=ImageFont.truetype(FONT_PATHS["regular"], 17),
        fill=hex_to_rgb("969696"),
    )

    # 绘制游戏名称
    draw.text(
        (104, 66),
        game_name,
        font=font_bold,
        fill=hex_to_rgb("91c257"),
    )

    return canvas


def draw_parent_status(parent_avatar: Image.Image, parent_name: str) -> Image.Image:
    """绘制群组头部状态（Steam 风格）"""
    parent_avatar = parent_avatar.resize(
        (PARENT_AVATAR_SIZE, PARENT_AVATAR_SIZE), Image.BICUBIC
    )

    canvas = Image.open(parent_status_path).resize((WIDTH, 120), Image.BICUBIC)

    draw = ImageDraw.Draw(canvas)
    font_bold = ImageFont.truetype(FONT_PATHS["bold"], 20)
    font_light = ImageFont.truetype(FONT_PATHS["light"], 18)

    # 在左下角 (16, 16) 处绘制头像
    avatar_height = 120 - 16 - PARENT_AVATAR_SIZE
    canvas.paste(parent_avatar, (16, avatar_height))

    # 绘制名称
    draw.text(
        (16 + PARENT_AVATAR_SIZE + 16, avatar_height + 12),
        parent_name,
        font=font_bold,
        fill=hex_to_rgb("6dcff6"),
    )

    # 绘制状态
    draw.text(
        (16 + PARENT_AVATAR_SIZE + 16, avatar_height + 20 + 16),
        "在线",
        font=font_light,
        fill=hex_to_rgb("4c91ac"),
    )

    return canvas


def draw_friends_search() -> Image.Image:
    """绘制好友搜索栏（Steam 风格）"""
    canvas = Image.new("RGB", (WIDTH, 50), hex_to_rgb("434953"))

    friends_search = Image.open(friends_search_path)

    canvas.paste(friends_search, (WIDTH - friends_search.width, 0))

    draw = ImageDraw.Draw(canvas)
    font_regular = ImageFont.truetype(FONT_PATHS["regular"], 20)

    draw.text(
        (24, 10),
        "好友",
        hex_to_rgb("b7ccd5"),
        font=font_regular,
    )

    return canvas


def draw_friend_status_steam(
    friend_avatar: Image.Image,
    friend_name: str,
    status: str,
    personastate: int,
    nickname: str = None,
) -> Image.Image:
    """
    绘制单个好友状态项（Steam 风格）

    Args:
        friend_avatar: 好友头像
        friend_name: 好友名字
        status: 状态文本（在线/游戏名/离线等）
        personastate: 状态代码
        nickname: 昵称（可选）
    """
    friend_avatar = friend_avatar.resize(
        (MEMBER_AVATAR_SIZE, MEMBER_AVATAR_SIZE), Image.BICUBIC
    )

    canvas = Image.new("RGB", (WIDTH, 64), hex_to_rgb("1e2024"))

    draw = ImageDraw.Draw(canvas)
    font_bold = ImageFont.truetype(FONT_PATHS["bold"], 20)
    font_regular = ImageFont.truetype(FONT_PATHS["regular"], 18)

    display_name = (
        f"{friend_name} ({nickname})" if nickname is not None else friend_name
    )

    if personastate == 2:
        # 忙碌 加上一个忙碌图标
        canvas = draw_friend_status_steam(friend_avatar, friend_name, status, 1, nickname)
        draw = ImageDraw.Draw(canvas)

        busy = Image.open(busy_path)

        name_width = int(
            draw.textlength(display_name, font=font_bold)
        )

        canvas.paste(busy, (22 + MEMBER_AVATAR_SIZE + 16 + name_width + 4, 18))

        return canvas

    if personastate == 4:
        # 打盹 加上一个 ZZZ
        canvas = draw_friend_status_steam(friend_avatar, friend_name, status, 1, nickname)
        draw = ImageDraw.Draw(canvas)

        zzz = Image.open(zzz_online_path if status == "在线" else zzz_gaming_path)

        name_width = int(
            draw.textlength(display_name, font=font_bold)
        )

        canvas.paste(zzz, (22 + MEMBER_AVATAR_SIZE + 16 + name_width + 8, 18))

        return canvas

    # 绘制头像
    canvas.paste(friend_avatar, (22, 8))

    if status != "在线" and personastate == 1:
        fill = (hex_to_rgb("e3ffc2"), hex_to_rgb("8ebe56"))
    elif status != "离开" and personastate == 3:
        fill = (hex_to_rgb("e3ffc2"), hex_to_rgb("8ebe56"))
    else:
        fill = personastate_colors.get(personastate, personastate_colors[0])

    # 绘制名称
    draw.text(
        (22 + MEMBER_AVATAR_SIZE + 18, 12),
        display_name,
        font=font_bold,
        fill=fill[0],
    )

    # 绘制状态
    draw.text(
        (22 + MEMBER_AVATAR_SIZE + 16, 36),
        status,
        font=font_regular,
        fill=fill[1],
    )

    return canvas


def draw_gaming_friends_status_steam(data: List[Dict[str, Any]]) -> Image.Image:
    """绘制游戏中好友列表（Steam 风格）"""
    # 排序数据，按照游戏名称字母表顺序排序
    data.sort(key=lambda x: x.get("status", ""))

    canvas = Image.new(
        "RGB",
        (WIDTH, 64 + (MEMBER_AVATAR_SIZE + 16) * len(data) + 16),
        hex_to_rgb("1e2024"),
    )

    draw = ImageDraw.Draw(canvas)
    font_regular = ImageFont.truetype(FONT_PATHS["regular"], 22)

    # 绘制标题
    draw.text(
        (22, 22),
        "游戏中",
        hex_to_rgb("c5d6d4"),
        font=font_regular,
    )

    # 绘制好友头像和名称
    friends_status_list = [
        draw_friend_status_steam(
            d["avatar"], d["name"], d["status"], d["personastate"], d.get("nickname")
        )
        for d in data
    ]

    # 拼接好友头像和名称
    for i, friend_status in enumerate(friends_status_list):
        canvas.paste(friend_status, (0, 64 + (MEMBER_AVATAR_SIZE + 16) * i))

    return canvas


def draw_online_friends_status_steam(data: List[Dict[str, Any]]) -> Image.Image:
    """绘制在线好友列表（Steam 风格）"""
    canvas = Image.new(
        "RGB",
        (WIDTH, 64 + (MEMBER_AVATAR_SIZE + 16) * len(data) + 16),
        hex_to_rgb("1e2024"),
    )

    draw = ImageDraw.Draw(canvas)
    font_regular = ImageFont.truetype(FONT_PATHS["regular"], 22)
    font_small = ImageFont.truetype(FONT_PATHS["regular"], 18)

    # 绘制标题
    draw.text(
        (22, 22),
        "在线好友",
        hex_to_rgb("c5d6d4"),
        font=font_regular,
    )

    # 绘制在线人数
    draw.text(
        (115, 25),
        f"({len(data)})",
        hex_to_rgb("67665c"),
        font=font_small,
    )

    # 绘制好友头像和名称
    friends_status_list = [
        draw_friend_status_steam(
            d["avatar"], d["name"], d["status"], d["personastate"], d.get("nickname")
        )
        for d in data
    ]

    # 拼接好友头像和名称
    for i, friend_status in enumerate(friends_status_list):
        canvas.paste(friend_status, (0, 64 + (MEMBER_AVATAR_SIZE + 16) * i))

    return canvas


def draw_offline_friends_status_steam(data: List[Dict[str, Any]]) -> Image.Image:
    """绘制离线好友列表（Steam 风格）"""
    canvas = Image.new(
        "RGB",
        (WIDTH, 64 + (MEMBER_AVATAR_SIZE + 16) * len(data) + 16),
        hex_to_rgb("1e2024"),
    )

    draw = ImageDraw.Draw(canvas)
    font_regular = ImageFont.truetype(FONT_PATHS["regular"], 22)
    font_small = ImageFont.truetype(FONT_PATHS["regular"], 18)

    # 绘制标题
    draw.text(
        (22, 22),
        "离线",
        hex_to_rgb("c5d6d4"),
        font=font_regular,
    )

    # 绘制离线人数
    draw.text(
        (72, 25),
        f"({len(data)})",
        hex_to_rgb("67665c"),
        font=font_small,
    )

    # 绘制好友头像和名称
    friends_status_list = [
        draw_friend_status_steam(
            d["avatar"], d["name"], d["status"], d["personastate"], d.get("nickname")
        )
        for d in data
    ]

    # 拼接好友头像和名称
    for i, friend_status in enumerate(friends_status_list):
        canvas.paste(friend_status, (0, 64 + (MEMBER_AVATAR_SIZE + 16) * i))

    return canvas


def draw_friends_status_steam(
    parent_avatar: Image.Image, parent_name: str, data: List[Dict[str, Any]]
) -> Image.Image:
    """
    绘制完整好友列表（Steam 风格）

    Args:
        parent_avatar: 群主/自己的头像
        parent_name: 群主/自己的名字
        data: 好友数据列表，每个包含 {avatar, name, status, personastate, nickname}
    """
    data.sort(key=lambda x: x.get("personastate", 0))

    parent_status = draw_parent_status(parent_avatar, parent_name)
    friends_search = draw_friends_search()

    status_images: List[Image.Image] = []
    height = parent_status.height + friends_search.height

    gaming_data = [
        d
        for d in data
        if (d.get("personastate") == 1 and d.get("status") != "在线")
        or (d.get("personastate") == 3 and d.get("status") != "离开")
        or (d.get("personastate") == 4 and d.get("status") != "在线")
    ]

    if gaming_data:
        status_images.append(draw_gaming_friends_status_steam(gaming_data))
        height += status_images[-1].height

    online_data = [
        d
        for d in data
        if (d.get("personastate") == 1 and d.get("status") == "在线")
        or (d.get("personastate") == 3 and d.get("status") == "离开")
        or (d.get("personastate") == 4 and d.get("status") == "在线")
        or (d.get("personastate") in [2, 5, 6])
    ]
    # 按 1, 2, 4, 5, 6, 3 的顺序排序
    online_data.sort(key=lambda x: (7 if x.get("personastate") == 3 else x.get("personastate", 0)))

    if online_data:
        status_images.append(draw_online_friends_status_steam(online_data))
        height += status_images[-1].height

    offline_data = [d for d in data if d.get("personastate") == 0]
    if offline_data:
        status_images.append(draw_offline_friends_status_steam(offline_data))
        height += status_images[-1].height

    # 拼合图片
    canvas = Image.new("RGB", (WIDTH, height), hex_to_rgb("1e2024"))
    draw = ImageDraw.Draw(canvas)

    canvas.paste(parent_status, (0, 0))
    canvas.paste(friends_search, (0, parent_status.height))

    y = parent_status.height + friends_search.height

    for i, status_image in enumerate(status_images):
        canvas.paste(status_image, (0, y))
        y += status_image.height

        # 绘制分割线
        if i != len(status_images) - 1:
            draw.rectangle([0, y - 1, WIDTH, y], fill=hex_to_rgb("333439"))

    return canvas


# ==================== Steam 风格个人主页渲染函数 ====================


def draw_game_info_steam(
    header: Image.Image,
    game_name: str,
    game_time: str,
    last_play_time: str,
    achievements: List[Dict[str, Any]],
    completed_achievement_number: int,
    total_achievement_number: int,
    achievement_color: Tuple[int, int, int],
) -> Image.Image:
    """绘制游戏信息卡片（Steam 风格）"""
    bg = Image.new("RGBA", (880, 110 + 64 + 10), (0, 0, 0, 110))
    header = header.resize((229, 86), Image.BICUBIC)
    bg.paste(header, (10, 110 // 2 - header.height // 2))

    draw = ImageDraw.Draw(bg)
    font_regular = ImageFont.truetype(FONT_PATHS["regular"], 26)
    font_light = ImageFont.truetype(FONT_PATHS["light"], 22)

    # 画游戏名
    draw.text(
        (260, 10),
        game_name,
        font=font_regular,
        fill=(255, 255, 255),
    )

    # 画最后游玩时间
    display_text = last_play_time
    draw.text(
        (int(bg.width - font_light.getlength(display_text)) - 10, 75),
        display_text,
        font=font_light,
        fill=(150, 150, 150),
    )

    # 画游戏时间
    display_text = f"总时数 {game_time}"
    draw.text(
        (int(bg.width - font_light.getlength(display_text)) - 10, 50),
        display_text,
        font=font_light,
        fill=(150, 150, 150),
    )

    if completed_achievement_number is None or total_achievement_number is None:
        return bg.crop((0, 0, bg.width, 110))

    # 画成就背景
    achievement_bg = Image.new("RGBA", (860, 64), achievement_color)
    draw_achievement = ImageDraw.Draw(achievement_bg)

    # 画成就进度
    font_small = ImageFont.truetype(FONT_PATHS["light"], 18)
    x = 14
    draw_achievement.text(
        (x, 20),
        "成就进度",
        font=font_small,
        fill=(255, 255, 255, 255),
    )
    x += font_small.getlength("成就进度") + 10
    draw_achievement.text(
        (int(x), 20),
        f"{completed_achievement_number} / {total_achievement_number}",
        font=font_small,
        fill=(130, 130, 130),
    )
    x += (
        font_small.getlength(f"{completed_achievement_number} / {total_achievement_number}")
        + 10
    )

    # 绘制进度条
    if total_achievement_number > 0:
        progress_bar = create_progress_bar(
            completed_achievement_number / total_achievement_number, achievement_color
        )
        achievement_bg.paste(progress_bar, (int(x), 24), progress_bar)

    # 画成就图标
    x = 860 - 48 * 6 - 10 * 6
    for achievement in achievements[:6]:
        if "image" in achievement:
            try:
                achievement_image = Image.open(BytesIO(achievement["image"])).resize((48, 48))
                achievement_bg.paste(achievement_image, (x, 8))
            except Exception:
                pass
        x += 48 + 10

    if completed_achievement_number > 6:
        font_num = ImageFont.truetype(FONT_PATHS["regular"], 22)
        display_text = f"+{completed_achievement_number - 5}"
        draw_achievement.rectangle((x, 8, x + 48, 56), fill=(34, 34, 34))
        draw_achievement.text(
            (x + 24 - font_num.getlength(display_text) // 2, 18),
            display_text,
            font=font_num,
            fill=(255, 255, 255),
        )

    bg.paste(achievement_bg, (10, 110), achievement_bg)
    return bg


def draw_player_status_steam(
    player_bg: Union[Image.Image, bytes],
    player_avatar: Union[Image.Image, bytes],
    player_name: str,
    player_id: str,
    player_description: str,
    player_last_two_weeks_time: str,
    player_games: List[Dict[str, Any]],
) -> Image.Image:
    """
    绘制个人 Steam 主页（Steam 风格）

    Args:
        player_bg: 背景图片
        player_avatar: 头像图片
        player_name: 玩家昵称
        player_id: 好友代码
        player_description: 个人简介
        player_last_two_weeks_time: 最近两周游戏时间
        player_games: 游戏数据列表
    """
    if isinstance(player_bg, bytes):
        player_bg = Image.open(BytesIO(player_bg))
    if isinstance(player_avatar, bytes):
        player_avatar = Image.open(BytesIO(player_avatar))

    # 处理背景
    bg = recolor_image(
        player_bg.crop(
            (
                (player_bg.width - 960) // 2,
                0,
                (player_bg.width + 960) // 2,
                player_bg.height,
            )
        ),
        10,
        10,
    )
    # 调暗背景
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.7)

    player_avatar = player_avatar.resize((200, 200))
    bg.paste(player_avatar, (40, 40))

    draw = ImageDraw.Draw(bg)
    font_light_40 = ImageFont.truetype(FONT_PATHS["light"], 40)
    font_regular_19 = ImageFont.truetype(FONT_PATHS["regular"], 19)
    font_light_22 = ImageFont.truetype(FONT_PATHS["light"], 22)
    font_light_26 = ImageFont.truetype(FONT_PATHS["light"], 26)

    # 画头像外框
    draw.rectangle((40, 40, 240, 240), outline=(83, 164, 196), width=3)

    # 画昵称
    draw.text(
        (280, 48),
        player_name,
        font=font_light_40,
        fill=(255, 255, 255),
    )

    # 画ID
    draw.text(
        (280, 100),
        f"好友代码: {player_id}",
        font=font_regular_19,
        fill=(191, 191, 191),
    )

    # 画简介
    line_width = 0
    offset = 0
    line = ""
    for idx, char in enumerate(player_description):
        line += char
        line_width += font_light_22.getlength(char)
        if line_width > 640 or idx == len(player_description) - 1 or char == "\n":
            draw.text(
                (280, 132 + offset),
                line,
                font=font_light_22,
                fill=(255, 255, 255),
            )
            line = ""
            offset += 25
            line_width = 0
        if offset >= 25 * 4:
            break

    # 获取颜色
    brightest_color, darkest_color = get_brightest_and_darkest_color(player_bg)
    brightest_color = tuple(map(lambda x: x - 30 if x >= 30 else 0, brightest_color))
    darkest_color = tuple(
        map(lambda x: x + 30 if x <= 255 - 30 else 255, darkest_color)
    )
    brightest_color = (brightest_color[0], brightest_color[1], brightest_color[2], 128)
    brightest_color = random_color_offset(brightest_color, 20)
    darkest_color = (darkest_color[0], darkest_color[1], darkest_color[2], 128)
    darkest_color = random_color_offset(darkest_color, 20)

    # 计算成就颜色
    hsv_achievement_color = rgb_to_hsv(*brightest_color[:3])
    achievement_color = tuple(
        map(
            int,
            hsv_to_rgb(
                hsv_achievement_color[0],
                hsv_achievement_color[1] * 0.85,
                hsv_achievement_color[2] * 0.6,
            ),
        )
    )

    # 绘制游戏信息
    game_images: List[Image.Image] = []
    for game in player_games:
        game_header = game.get("game_header")
        if isinstance(game_header, bytes):
            game_image = Image.open(BytesIO(game_header))
        elif isinstance(game_header, Image.Image):
            game_image = game_header
        else:
            game_image = Image.new("RGB", (229, 86), (60, 60, 65))

        game_info = draw_game_info_steam(
            game_image,
            game.get("game_name", "未知游戏"),
            game.get("game_time", "0 小时"),
            game.get("last_play_time", ""),
            game.get("achievements", []),
            game.get("completed_achievement_number"),
            game.get("total_achievement_number"),
            achievement_color,
        )
        game_images.append(game_info)

    # 画半透明黑色背景
    if game_images:
        bg_game = Image.new(
            "RGBA", (920, 106 + sum([game_image.height + 26 for game_image in game_images]))
        )
        draw_game = ImageDraw.Draw(bg_game)
        draw_game.rectangle(
            (0, 0, 920, bg_game.height),
            fill=(0, 0, 0, 120),
        )
        bg.paste(bg_game, (20, 272), bg_game)

        # 画渐变条
        gradient = create_gradient_image((920, 50), brightest_color, darkest_color)
        bg.paste(gradient, (20, 272), gradient)

        # 画渐变条的文字
        draw.text(
            (34, 279),
            "最新动态",
            font=font_light_26,
            fill=(255, 255, 255),
        )
        if player_last_two_weeks_time:
            width_text = font_light_26.getlength(player_last_two_weeks_time)
            draw.text(
                (960 - width_text - 34, 279),
                player_last_two_weeks_time,
                font=font_light_26,
                fill=(255, 255, 255),
            )

        y = 350
        for game_image in game_images:
            bg.paste(
                game_image,
                ((920 - game_image.width) // 2 + 20, y),
                game_image.convert("RGBA"),
            )
            y += game_image.height + 26

    player_bg.paste(bg, ((player_bg.width - 960) // 2, 0), bg.convert("RGBA"))

    return player_bg


# ==================== 兼容层：保留原有接口 ====================


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
    绘制单个好友状态卡片（兼容层）

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
    # 映射 status_type 到 personastate
    status_to_persona = {
        "gaming": 1,
        "online": 1,
        "offline": 0,
        "busy": 2,
    }
    personastate = status_to_persona.get(status_type, 0)

    # 确定状态文本
    status = game_name if game_name else status_text

    return draw_friend_status_steam(avatar, name, status, personastate)


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


def draw_game_price_info(
    game_name: str,
    english_name: Optional[str],
    appid: int,
    header_image: Optional[bytes],
    prices: List[Dict[str, Any]],
    historical_low: Optional[float],
    historical_low_currency: str,
    historical_low_date: Optional[str],
    width: int = 950
) -> Image.Image:
    """
    渲染游戏价格信息卡片

    Args:
        game_name: 游戏中文名
        english_name: 游戏英文名
        appid: Steam AppID
        header_image: 游戏头图（字节数据）
        prices: 价格列表，每个包含 {region, currency, price, discount, converted_price}
        historical_low: 史低价格
        historical_low_currency: 史低货币
        historical_low_date: 史低日期
        width: 图片宽度

    Returns:
        价格信息图片
    """
    padding = 30
    header_height = 250  # 游戏头图区域
    info_height = 150    # 基本信息区域
    price_row_height = 50
    price_section_height = len(prices) * price_row_height + 80
    # 史低区域：标题(40) + 价格(35) + 日期(可选，35+30) + 提示(可选，35) + 边距(20)
    low_section_height = 0
    if historical_low:
        low_section_height = 115  # 基础高度
        if historical_low_date:
            low_section_height += 65  # 日期行
    total_height = padding * 2 + header_height + info_height + price_section_height + low_section_height

    # 创建画布
    img = Image.new("RGBA", (width, total_height), (24, 27, 33, 255))
    draw = ImageDraw.Draw(img)

    y_offset = padding

    # 游戏头图
    header_w, header_h = width - padding * 2, header_height
    header = Image.new("RGBA", (header_w, header_h), (42, 45, 53, 255))
    if header_image:
        try:
            header_img = Image.open(BytesIO(header_image)).convert("RGBA")
            # 调整大小保持比例
            aspect = header_img.width / header_img.height
            if aspect > header_w / header_h:
                new_w = header_w
                new_h = int(header_w / aspect)
            else:
                new_h = header_h
                new_w = int(header_h * aspect)
            header_img = header_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            # 居中粘贴
            x_pos = (header_w - new_w) // 2
            y_pos = (header_h - new_h) // 2
            header.paste(header_img, (x_pos, y_pos))
        except Exception:
            pass

    # 圆角头图
    header_mask = rounded_rectangle((header_w, header_h), 15, (255, 255, 255, 255))
    header_canvas = Image.new("RGBA", (header_w, header_h), (0, 0, 0, 0))
    header_canvas.paste(header, (0, 0), header_mask)
    img.paste(header_canvas, (padding, y_offset), header_canvas)
    y_offset += header_height + 20

    # 游戏名称和基本信息
    title_font = get_font(FONT_SIZE_TITLE, "bold")
    subtitle_font = get_font(FONT_SIZE_MEDIUM, "light")
    small_font = get_font(FONT_SIZE_SMALL, "regular")

    # 中文名
    draw.text((padding, y_offset), game_name, font=title_font, fill=(255, 255, 255, 255))
    y_offset += 55

    # 英文名
    if english_name and english_name != game_name:
        draw.text((padding, y_offset), english_name, font=subtitle_font, fill=(180, 180, 190, 255))
        y_offset += 40

    # Steam链接
    store_link = f"https://store.steampowered.com/app/{appid}"
    draw.text((padding, y_offset), f"🔗 {store_link}", font=small_font, fill=(100, 150, 200, 255))
    y_offset += 50

    # 价格对比区域标题
    price_title_font = get_font(FONT_SIZE_LARGE, "bold")
    draw.text((padding, y_offset), "💰 价格对比", font=price_title_font, fill=(255, 255, 255, 255))
    y_offset += 45

    # 价格列表
    region_font = get_font(FONT_SIZE_NORMAL, "regular")
    price_font = get_font(FONT_SIZE_NORMAL, "bold")

    region_names = {
        "cn": "中国🇨🇳",
        "us": "美国🇺🇸",
        "ua": "乌克兰🇺🇦",
        "jp": "日本🇯🇵",
        "ar": "阿根廷🇦🇷",
        "tr": "土耳其🇹🇷",
    }

    for price_data in prices:
        region = price_data.get("region", "").lower()
        region_name = region_names.get(region, region.upper())
        price = price_data.get("price", 0)
        original_price = price_data.get("original_price", 0)
        discount = price_data.get("discount", 0)
        currency = price_data.get("currency", "CNY")
        converted_price = price_data.get("converted_price")

        # 货币符号
        currency_symbols = {
            "CNY": "¥", "USD": "$", "EUR": "€",
            "JPY": "¥", "UAH": "₴", "ARS": "$", "TRY": "₺"
        }
        symbol = currency_symbols.get(currency, currency + " ")

        # 区域名
        draw.text((padding + 20, y_offset), region_name, font=region_font, fill=(200, 200, 210, 255))

        # 价格
        price_text = f"{symbol}{price:.2f}"
        price_color = (144, 186, 106, 255) if discount > 0 else (255, 255, 255, 255)
        draw.text((padding + 200, y_offset), price_text, font=price_font, fill=price_color)

        # 折扣
        if discount > 0:
            discount_text = f"-{discount}%"
            discount_w = draw.textlength(discount_text, font=price_font)
            discount_bg = rounded_rectangle((int(discount_w) + 20, 32), 8, (144, 186, 106, 200))
            img.paste(discount_bg, (padding + 380, y_offset - 5), discount_bg)
            draw.text((padding + 390, y_offset), discount_text, font=price_font, fill=(255, 255, 255, 255))

        # 原价（如果有折扣）
        if discount > 0 and original_price > price:
            original_text = f"{symbol}{original_price:.2f}"
            draw.text((padding + 500, y_offset), original_text, font=region_font, fill=(150, 150, 160, 255))
            # 删除线
            text_w = draw.textlength(original_text, font=region_font)
            draw.line(
                [(padding + 500, y_offset + 12), (padding + 500 + text_w, y_offset + 12)],
                fill=(150, 150, 160, 255),
                width=2
            )

        # 换算价（如果不是CNY）
        if converted_price and currency != "CNY":
            converted_text = f"≈ ¥{converted_price:.2f}"
            draw.text((padding + 650, y_offset), converted_text, font=region_font, fill=(160, 170, 180, 255))

        y_offset += price_row_height

    # 史低价格
    if historical_low:
        y_offset += 20
        low_title_font = get_font(FONT_SIZE_LARGE, "bold")
        draw.text((padding, y_offset), "📉 历史最低价", font=low_title_font, fill=(255, 255, 255, 255))
        y_offset += 40

        # 史低价格
        low_symbol = {"CNY": "¥", "USD": "$", "EUR": "€"}.get(historical_low_currency, historical_low_currency + " ")
        low_price_text = f"{low_symbol}{historical_low:.2f}"
        draw.text((padding + 20, y_offset), low_price_text, font=price_font, fill=(255, 180, 100, 255))

        # 史低日期（如果有）
        if historical_low_date:
            y_offset += 35
            date_font = get_font(FONT_SIZE_SMALL, "regular")
            date_text = f"上次史低时间：{historical_low_date}"
            draw.text((padding + 20, y_offset), date_text, font=date_font, fill=(200, 200, 210, 255))
            y_offset += 30

        # 对比当前价格（如果当前就是史低）
        if prices:
            cn_price = next((p for p in prices if p.get("region", "").lower() == "cn"), None)
            if cn_price and cn_price.get("price"):
                current = cn_price.get("price")
                # 转换史低价格到人民币（如果需要）
                low_in_cny = historical_low
                if historical_low_currency != "CNY":
                    # 简单估算，如果是USD约*7，EUR约*7.5
                    rate_map = {"USD": 7.0, "EUR": 7.5, "JPY": 0.05}
                    low_in_cny = historical_low * rate_map.get(historical_low_currency, 1.0)

                if current > 0 and low_in_cny > 0:
                    diff_percent = abs(current - low_in_cny) / low_in_cny * 100
                    if diff_percent <= 5:
                        # 当前价格接近史低
                        y_offset += 5
                        tip_font = get_font(FONT_SIZE_SMALL, "bold")
                        draw.text((padding + 20, y_offset), "💎 当前已达史低价格！", font=tip_font, fill=(144, 238, 144, 255))

    return img


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
