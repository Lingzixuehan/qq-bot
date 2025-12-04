"""
聊天截图生成器
使用 Pillow 生成类似 QQ 聊天截图的图片
"""
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from pathlib import Path
from datetime import datetime
import textwrap

# 颜色配置
BG_COLOR = (245, 245, 245)  # 背景色
BUBBLE_COLOR = (255, 255, 255)  # 消息气泡背景
TEXT_COLOR = (51, 51, 51)  # 文字颜色
NAME_COLOR = (102, 102, 102)  # 昵称颜色
TIME_COLOR = (153, 153, 153)  # 时间颜色

# 尺寸配置
WIDTH = 600  # 图片宽度
PADDING = 20  # 边距
BUBBLE_PADDING = 15  # 气泡内边距
AVATAR_SIZE = 50  # 头像大小
LINE_HEIGHT = 30  # 行高


def wrap_text(text: str, font, max_width: int):
    """
    将文本按宽度换行
    """
    lines = []
    for paragraph in text.split('\n'):
        if not paragraph:
            lines.append('')
            continue

        words = list(paragraph)
        current_line = ''

        for char in words:
            test_line = current_line + char
            bbox = font.getbbox(test_line)
            width = bbox[2] - bbox[0]

            if width <= max_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = char

        if current_line:
            lines.append(current_line)

    return lines


def generate_quote_image(user_name: str, content: str, timestamp: str = None) -> BytesIO:
    """
    生成语录截图

    Args:
        user_name: 用户昵称
        content: 语录内容
        timestamp: 时间戳（可选）

    Returns:
        BytesIO: 图片的字节流
    """
    # 如果没有提供时间戳，使用当前时间
    if not timestamp:
        timestamp = datetime.now().strftime("%H:%M")

    # 尝试加载字体
    try:
        # Windows 系统字体路径
        font_name = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)  # 微软雅黑
        font_time = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except:
        try:
            # Linux 系统字体路径
            font_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            # 如果都找不到，使用默认字体
            font_name = ImageFont.load_default()
            font_time = ImageFont.load_default()

    # 计算文本区域宽度
    text_max_width = WIDTH - PADDING * 2 - AVATAR_SIZE - 20 - BUBBLE_PADDING * 2

    # 换行处理
    lines = wrap_text(content, font_name, text_max_width)

    # 计算气泡高度
    text_height = len(lines) * LINE_HEIGHT
    bubble_height = text_height + BUBBLE_PADDING * 2

    # 计算总高度
    total_height = PADDING * 2 + 25 + 10 + bubble_height + 20

    # 创建图片
    img = Image.new('RGB', (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 绘制头像（简单的圆形占位符）
    avatar_x = PADDING
    avatar_y = PADDING + 25 + 10
    draw.ellipse(
        [avatar_x, avatar_y, avatar_x + AVATAR_SIZE, avatar_y + AVATAR_SIZE],
        fill=(200, 200, 200),
        outline=(180, 180, 180),
        width=2
    )

    # 在头像中绘制用户名首字母
    if user_name:
        first_char = user_name[0]
        # 使用较大的字体
        try:
            avatar_font = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 24)
        except:
            avatar_font = font_name

        char_bbox = draw.textbbox((0, 0), first_char, font=avatar_font)
        char_width = char_bbox[2] - char_bbox[0]
        char_height = char_bbox[3] - char_bbox[1]

        char_x = avatar_x + (AVATAR_SIZE - char_width) // 2
        char_y = avatar_y + (AVATAR_SIZE - char_height) // 2 - 5

        draw.text((char_x, char_y), first_char, fill=(255, 255, 255), font=avatar_font)

    # 绘制昵称和时间
    name_y = PADDING
    draw.text((avatar_x, name_y), user_name, fill=NAME_COLOR, font=font_name)

    name_bbox = draw.textbbox((avatar_x, name_y), user_name, font=font_name)
    time_x = name_bbox[2] + 15
    draw.text((time_x, name_y + 3), timestamp, fill=TIME_COLOR, font=font_time)

    # 绘制消息气泡
    bubble_x = avatar_x + AVATAR_SIZE + 10
    bubble_y = avatar_y

    # 绘制圆角矩形气泡
    bubble_rect = [
        bubble_x,
        bubble_y,
        bubble_x + text_max_width + BUBBLE_PADDING * 2,
        bubble_y + bubble_height
    ]

    # 绘制气泡背景
    draw.rounded_rectangle(bubble_rect, radius=10, fill=BUBBLE_COLOR, outline=(220, 220, 220), width=1)

    # 绘制文本内容
    text_x = bubble_x + BUBBLE_PADDING
    text_y = bubble_y + BUBBLE_PADDING

    for i, line in enumerate(lines):
        draw.text(
            (text_x, text_y + i * LINE_HEIGHT),
            line,
            fill=TEXT_COLOR,
            font=font_name
        )

    # 将图片保存到字节流
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output


def generate_quote_image_base64(user_name: str, content: str, timestamp: str = None) -> str:
    """
    生成语录截图并返回 base64 编码
    """
    import base64

    img_bytes = generate_quote_image(user_name, content, timestamp)
    img_base64 = base64.b64encode(img_bytes.read()).decode()

    return f"base64://{img_base64}"
