"""
Steam个人资料和游戏信息图片生成器
生成Steam风格的资料卡片和游戏列表图片
"""
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import httpx
from typing import List, Dict, Optional


# Steam风格颜色
BG_COLOR = (27, 40, 56)
CARD_BG_COLOR = (35, 47, 62)
TEXT_COLOR = (193, 199, 208)
HIGHLIGHT_COLOR = (87, 186, 255)
GAME_COLOR = (144, 186, 60)
SECONDARY_TEXT = (117, 128, 140)

# 尺寸
WIDTH = 700
PADDING = 20


def download_image(url: str) -> Optional[Image.Image]:
    """下载图片"""
    try:
        response = httpx.get(url, timeout=5)
        if response.status_code == 200:
            return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"下载图片失败: {e}")
    return None


def get_font(size: int, bold: bool = False):
    """获取字体"""
    try:
        if bold:
            return ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", size)
        return ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", size)
    except:
        try:
            if bold:
                return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except:
            return ImageFont.load_default()


def generate_steam_profile_image(player_info: Dict, recent_games: List[Dict] = None, qq_user: str = None) -> BytesIO:
    """
    生成Steam个人资料图片

    Args:
        player_info: Steam玩家信息
        recent_games: 最近玩的游戏列表（可选）
        qq_user: QQ用户昵称（可选）

    Returns:
        BytesIO: 图片字节流
    """
    # 计算高度
    base_height = 300
    game_section_height = 0
    if recent_games:
        game_section_height = len(recent_games) * 60 + 60

    total_height = base_height + game_section_height + PADDING * 2

    # 创建图片
    img = Image.new('RGB', (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 字体
    font_title = get_font(28, bold=True)
    font_large = get_font(22)
    font_normal = get_font(18)
    font_small = get_font(14)

    y_offset = PADDING

    # 绘制标题
    title = "🎮 Steam个人资料"
    draw.text((PADDING, y_offset), title, fill=TEXT_COLOR, font=font_title)
    y_offset += 50

    # 下载并绘制头像
    avatar_url = player_info.get("avatarfull", "")
    avatar_x = PADDING
    avatar_y = y_offset

    if avatar_url:
        avatar = download_image(avatar_url)
        if avatar:
            avatar = avatar.resize((120, 120), Image.Resampling.LANCZOS)
            img.paste(avatar, (avatar_x, avatar_y))

    # 绘制用户信息
    info_x = avatar_x + 140
    info_y = avatar_y

    # Steam昵称
    personaname = player_info.get("personaname", "未知用户")
    draw.text((info_x, info_y), personaname, fill=HIGHLIGHT_COLOR, font=font_large)
    info_y += 35

    # 状态
    state_map = {0: "离线", 1: "在线", 2: "忙碌", 3: "离开", 4: "打盹"}
    state = state_map.get(player_info.get("personastate", 0), "未知")
    game_name = player_info.get("gameextrainfo", None)

    if game_name:
        draw.text((info_x, info_y), f"状态: 游戏中", fill=GAME_COLOR, font=font_normal)
        info_y += 30
        draw.text((info_x, info_y), f"正在玩: {game_name}", fill=GAME_COLOR, font=font_small)
    else:
        draw.text((info_x, info_y), f"状态: {state}", fill=TEXT_COLOR, font=font_normal)

    info_y += 35

    # QQ用户信息
    if qq_user:
        draw.text((info_x, info_y), f"QQ用户: {qq_user}", fill=SECONDARY_TEXT, font=font_small)
        info_y += 25

    # Steam ID
    steam_id = player_info.get("steamid", "")
    draw.text((info_x, info_y), f"Steam ID: {steam_id}", fill=SECONDARY_TEXT, font=font_small)

    y_offset += 140

    # 绘制主页链接
    profile_url = player_info.get("profileurl", "")
    if profile_url:
        draw.text((PADDING, y_offset), f"主页: {profile_url}", fill=SECONDARY_TEXT, font=font_small)

    y_offset += 40

    # 绘制最近游戏
    if recent_games and len(recent_games) > 0:
        # 分隔线
        draw.line([(PADDING, y_offset), (WIDTH - PADDING, y_offset)], fill=SECONDARY_TEXT, width=1)
        y_offset += 20

        draw.text((PADDING, y_offset), "📋 最近在玩", fill=TEXT_COLOR, font=font_large)
        y_offset += 40

        for game in recent_games[:5]:
            game_name = game.get("name", "未知游戏")
            playtime_2weeks = game.get("playtime_2weeks", 0)
            playtime_forever = game.get("playtime_forever", 0)

            # 限制游戏名长度
            if len(game_name) > 40:
                game_name = game_name[:40] + "..."

            # 游戏名
            draw.text((PADDING, y_offset), f"• {game_name}", fill=TEXT_COLOR, font=font_normal)
            y_offset += 28

            # 游戏时长
            time_text = f"  最近: {format_playtime(playtime_2weeks)} | 总计: {format_playtime(playtime_forever)}"
            draw.text((PADDING, y_offset), time_text, fill=SECONDARY_TEXT, font=font_small)
            y_offset += 35

    # 保存
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output


def generate_steam_games_image(games: List[Dict], qq_user: str = None) -> BytesIO:
    """
    生成Steam游戏库图片

    Args:
        games: 游戏列表
        qq_user: QQ用户昵称（可选）

    Returns:
        BytesIO: 图片字节流
    """
    # 计算总时长
    total_playtime = sum(game.get("playtime_forever", 0) for game in games)

    # 按时长排序
    games_sorted = sorted(games, key=lambda x: x.get("playtime_forever", 0), reverse=True)

    # 计算高度（显示前15个游戏）
    display_count = min(15, len(games_sorted))
    total_height = 200 + display_count * 50 + PADDING * 2

    # 创建图片
    img = Image.new('RGB', (WIDTH, total_height), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # 字体
    font_title = get_font(28, bold=True)
    font_large = get_font(20)
    font_normal = get_font(16)
    font_small = get_font(14)

    y_offset = PADDING

    # 标题
    draw.text((PADDING, y_offset), "📚 Steam游戏库", fill=TEXT_COLOR, font=font_title)
    y_offset += 50

    # QQ用户
    if qq_user:
        draw.text((PADDING, y_offset), f"QQ用户: {qq_user}", fill=SECONDARY_TEXT, font=font_small)
        y_offset += 30

    # 统计信息
    draw.text((PADDING, y_offset), f"游戏总数: {len(games)} 款", fill=HIGHLIGHT_COLOR, font=font_large)
    y_offset += 35

    draw.text((PADDING, y_offset), f"总游戏时长: {format_playtime(total_playtime)}", fill=TEXT_COLOR, font=font_normal)
    y_offset += 40

    # 分隔线
    draw.line([(PADDING, y_offset), (WIDTH - PADDING, y_offset)], fill=SECONDARY_TEXT, width=1)
    y_offset += 20

    # TOP游戏
    draw.text((PADDING, y_offset), "🏆 游戏时长排行", fill=TEXT_COLOR, font=font_large)
    y_offset += 40

    for i, game in enumerate(games_sorted[:display_count], 1):
        game_name = game.get("name", "未知游戏")
        playtime = game.get("playtime_forever", 0)

        # 限制名称长度
        if len(game_name) > 45:
            game_name = game_name[:45] + "..."

        # 排名和游戏名
        rank_color = GAME_COLOR if i <= 3 else TEXT_COLOR
        text = f"{i}. {game_name}"
        draw.text((PADDING, y_offset), text, fill=rank_color, font=font_normal)

        # 时长（右对齐）
        time_text = format_playtime(playtime)
        time_bbox = draw.textbbox((0, 0), time_text, font=font_normal)
        time_width = time_bbox[2] - time_bbox[0]
        draw.text((WIDTH - PADDING - time_width, y_offset), time_text, fill=SECONDARY_TEXT, font=font_normal)

        y_offset += 50

    # 保存
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output


def format_playtime(minutes: int) -> str:
    """格式化游戏时长"""
    if minutes < 60:
        return f"{minutes}分钟"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f}小时"
    days = hours / 24
    return f"{days:.1f}天"


def generate_steam_profile_image_base64(player_info: Dict, recent_games: List[Dict] = None, qq_user: str = None) -> str:
    """生成Steam个人资料图片并返回base64"""
    import base64
    img_bytes = generate_steam_profile_image(player_info, recent_games, qq_user)
    return f"base64://{base64.b64encode(img_bytes.read()).decode()}"


def generate_steam_games_image_base64(games: List[Dict], qq_user: str = None) -> str:
    """生成Steam游戏库图片并返回base64"""
    import base64
    img_bytes = generate_steam_games_image(games, qq_user)
    return f"base64://{base64.b64encode(img_bytes.read()).decode()}"
