"""
Steam好友列表图片生成器
生成类似Steam好友列表的图片，显示用户在线状态
"""
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import httpx
from typing import List, Dict


# 颜色配置
BG_COLOR = (27, 40, 56)  # Steam深蓝色背景
ITEM_BG_COLOR = (35, 47, 62)  # 列表项背景
ITEM_HOVER_BG = (44, 58, 77)  # 列表项悬停背景
TEXT_COLOR = (193, 199, 208)  # 主文字颜色
GAME_TEXT_COLOR = (144, 186, 60)  # 游戏名称颜色（绿色）
ONLINE_COLOR = (87, 186, 255)  # 在线状态颜色（蓝色）
INGAME_COLOR = (144, 186, 60)  # 游戏中状态颜色（绿色）
OFFLINE_COLOR = (117, 128, 140)  # 离线状态颜色（灰色）

# 尺寸配置
WIDTH = 600
PADDING = 15
ITEM_HEIGHT = 80
AVATAR_SIZE = 60
HEADER_HEIGHT = 60


def download_steam_avatar(avatar_url: str) -> Image.Image:
    """
    下载Steam头像

    Args:
        avatar_url: Steam头像URL

    Returns:
        PIL Image对象，如果下载失败返回None
    """
    try:
        response = httpx.get(avatar_url, timeout=5)
        if response.status_code == 200:
            avatar_img = Image.open(BytesIO(response.content))
            return avatar_img
    except Exception as e:
        print(f"下载Steam头像失败: {e}")
    return None


def create_rounded_rectangle_mask(size: tuple, radius: int) -> Image.Image:
    """创建圆角矩形蒙版"""
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
    return mask


def get_status_info(player_info: Dict) -> tuple:
    """
    获取玩家状态信息

    Returns:
        (状态文字, 状态颜色, 游戏名称或None)
    """
    personastate = player_info.get("personastate", 0)
    game_name = player_info.get("gameextrainfo", None)

    if game_name:
        return ("游戏中", INGAME_COLOR, game_name)
    elif personastate == 1:
        return ("在线", ONLINE_COLOR, None)
    elif personastate == 2:
        return ("忙碌", ONLINE_COLOR, None)
    elif personastate == 3:
        return ("离开", ONLINE_COLOR, None)
    else:
        return ("离线", OFFLINE_COLOR, None)


def generate_steam_friends_list(players_data: List[Dict]) -> BytesIO:
    """
    生成Steam好友列表样式的图片

    Args:
        players_data: 玩家数据列表，每项包含:
            - personaname: Steam昵称
            - avatar: 头像URL
            - personastate: 状态代码
            - gameextrainfo: 游戏名称(可选)

    Returns:
        BytesIO: 图片的字节流
    """
    # 计算总高度
    total_height = HEADER_HEIGHT + len(players_data) * ITEM_HEIGHT + PADDING * 2

    # 创建图片
    img = Image.new('RGB', (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 加载字体
    try:
        # Windows
        font_title = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 24)
        font_name = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
        font_status = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
        font_game = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except:
        try:
            # Linux
            font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            font_name = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
            font_status = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            font_game = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            font_title = ImageFont.load_default()
            font_name = ImageFont.load_default()
            font_status = ImageFont.load_default()
            font_game = ImageFont.load_default()

    # 绘制标题
    title_text = f"🎮 Steam好友列表 ({len(players_data)}人在线)"
    draw.text((PADDING, 20), title_text, fill=TEXT_COLOR, font=font_title)

    # 绘制每个玩家
    y_offset = HEADER_HEIGHT + PADDING

    for i, player in enumerate(players_data):
        # 交替背景色
        item_bg = ITEM_BG_COLOR if i % 2 == 0 else ITEM_HOVER_BG
        draw.rectangle(
            [(0, y_offset), (WIDTH, y_offset + ITEM_HEIGHT)],
            fill=item_bg
        )

        # 下载并绘制头像
        avatar_url = player.get("avatarfull", player.get("avatarmedium", ""))
        avatar_x = PADDING
        avatar_y = y_offset + (ITEM_HEIGHT - AVATAR_SIZE) // 2

        avatar_img = download_steam_avatar(avatar_url)
        if avatar_img:
            # 调整头像大小
            avatar_img = avatar_img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
            # 创建圆角蒙版
            mask = create_rounded_rectangle_mask((AVATAR_SIZE, AVATAR_SIZE), 5)
            # 转换为RGBA
            if avatar_img.mode != 'RGBA':
                avatar_img = avatar_img.convert('RGBA')
            # 应用蒙版
            avatar_with_mask = Image.new('RGBA', (AVATAR_SIZE, AVATAR_SIZE), (0, 0, 0, 0))
            avatar_with_mask.paste(avatar_img, (0, 0))
            avatar_with_mask.putalpha(mask)
            # 粘贴到主图
            img.paste(avatar_with_mask, (avatar_x, avatar_y), avatar_with_mask)
        else:
            # 如果头像下载失败，绘制占位符
            draw.rounded_rectangle(
                [(avatar_x, avatar_y), (avatar_x + AVATAR_SIZE, avatar_y + AVATAR_SIZE)],
                radius=5,
                fill=(100, 100, 100)
            )

        # 获取状态信息
        status_text, status_color, game_name = get_status_info(player)

        # 绘制昵称
        name_x = avatar_x + AVATAR_SIZE + 15
        name_y = y_offset + 15
        personaname = player.get("personaname", "未知用户")
        # 限制昵称长度
        if len(personaname) > 20:
            personaname = personaname[:20] + "..."
        draw.text((name_x, name_y), personaname, fill=TEXT_COLOR, font=font_name)

        # 绘制状态
        status_y = name_y + 25
        draw.text((name_x, status_y), f"● {status_text}", fill=status_color, font=font_status)

        # 如果在游戏中，绘制游戏名称
        if game_name:
            game_y = status_y + 20
            # 限制游戏名称长度
            if len(game_name) > 30:
                game_name = game_name[:30] + "..."
            draw.text((name_x, game_y), f"正在玩: {game_name}", fill=GAME_TEXT_COLOR, font=font_game)

        y_offset += ITEM_HEIGHT

    # 保存到字节流
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)

    return output


def generate_steam_friends_list_base64(players_data: List[Dict]) -> str:
    """
    生成Steam好友列表图片并返回base64编码

    Args:
        players_data: 玩家数据列表

    Returns:
        str: base64编码的图片数据
    """
    import base64

    img_bytes = generate_steam_friends_list(players_data)
    img_base64 = base64.b64encode(img_bytes.read()).decode()

    return f"base64://{img_base64}"
