"""
二次元美图插件 - 本地图片库版本
从本地图片库发送图片，支持标签搜索
"""

import base64
import csv
import random
from pathlib import Path
from typing import List, Optional

from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message

# 配置
IMAGE_DIR = Path("data/anime_pics")
CSV_FILE = Path("data/anime_pics.csv")


class LocalImageManager:
    """本地图片管理器"""

    def __init__(self):
        self.image_dir = IMAGE_DIR
        self.csv_file = CSV_FILE

    def _load_metadata(self) -> List[dict]:
        """加载所有图片元数据"""
        if not self.csv_file.exists():
            return []

        images = []
        try:
            with open(self.csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    images.append(row)
        except Exception as e:
            print(f"读取CSV失败: {e}")
            return []

        return images

    def get_random_image(self) -> Optional[dict]:
        """随机获取一张图片"""
        images = self._load_metadata()
        if not images:
            return None

        # 过滤存在的图片
        valid_images = [
            img for img in images
            if (self.image_dir / img['filename']).exists()
        ]

        if not valid_images:
            return None

        return random.choice(valid_images)

    def search_by_tag(self, keyword: str) -> List[dict]:
        """根据关键词搜索图片"""
        images = self._load_metadata()
        if not images:
            return []

        keyword = keyword.lower()
        matched = []

        for img in images:
            # 检查文件是否存在
            if not (self.image_dir / img['filename']).exists():
                continue

            # 搜索标题、作者、标签
            title = img.get('title', '').lower()
            author = img.get('author', '').lower()
            tags = img.get('tags', '').lower()

            if keyword in title or keyword in author or keyword in tags:
                matched.append(img)

        return matched

    def get_image_base64(self, filename: str) -> Optional[str]:
        """获取图片的base64编码"""
        filepath = self.image_dir / filename
        if not filepath.exists():
            return None

        try:
            with open(filepath, 'rb') as f:
                img_data = f.read()
                return base64.b64encode(img_data).decode()
        except Exception as e:
            print(f"读取图片失败: {e}")
            return None

    def get_total_count(self) -> int:
        """获取图片总数"""
        images = self._load_metadata()
        return len([img for img in images if (self.image_dir / img['filename']).exists()])


# 创建管理器实例
image_manager = LocalImageManager()


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """随机获取一张二次元图片"""
    # 检查图片库
    total = image_manager.get_total_count()
    if total == 0:
        await random_pic.finish(
            "❌ 本地图片库为空\n\n"
            "请先使用以下命令下载图片：\n"
            "python scripts/download_anime_pics.py 50"
        )
        return

    # 随机选择图片
    img_info = image_manager.get_random_image()
    if not img_info:
        await random_pic.finish("❌ 获取图片失败")
        return

    # 读取图片
    img_base64 = image_manager.get_image_base64(img_info['filename'])
    if not img_base64:
        await random_pic.finish("❌ 读取图片失败")
        return

    # 构建消息
    title = img_info.get('title', '未知')
    author = img_info.get('author', '未知')
    tags = img_info.get('tags', '')
    source = img_info.get('source', '')

    msg = f"🎨 {title}\n"
    msg += f"👤 作者: {author}\n"
    if tags:
        tag_list = tags.split(',')[:5]  # 最多显示5个标签
        msg += f"🏷️ {', '.join(tag_list)}\n"
    msg += f"📦 来源: {source}\n"
    msg += f"💾 图片库: {total}张"

    # 发送
    try:
        await random_pic.send(msg)
        await random_pic.finish(MessageSegment.image(f"base64://{img_base64}"))
    except Exception as e:
        print(f"发送图片失败: {e}")
        await random_pic.finish("❌ 图片发送失败")


# 关键词搜索图片
search_pic = on_command("搜图", aliases={"找图", "图片搜索"}, priority=5)


@search_pic.handle()
async def handle_search_pic(event: MessageEvent, args: Message = CommandArg()):
    """根据关键词搜索图片"""
    keyword = args.extract_plain_text().strip()

    if not keyword:
        await search_pic.finish(
            "用法：/搜图 <关键词>\n\n"
            "示例：\n"
            "/搜图 白毛\n"
            "/搜图 猫娘\n"
            "/搜图 原神\n\n"
            "💡 支持搜索标题、作者、标签"
        )
        return

    # 检查图片库
    total = image_manager.get_total_count()
    if total == 0:
        await search_pic.finish(
            "❌ 本地图片库为空\n\n"
            "请先使用以下命令下载图片：\n"
            "python scripts/download_anime_pics.py 50"
        )
        return

    # 搜索
    matched = image_manager.search_by_tag(keyword)
    if not matched:
        await search_pic.finish(
            f"❌ 没有找到包含 '{keyword}' 的图片\n\n"
            f"💡 当前图片库共有 {total} 张图片\n"
            "💡 试试其他关键词或使用 /美图 获取随机图片"
        )
        return

    # 随机选择一张匹配的图片
    img_info = random.choice(matched)

    # 读取图片
    img_base64 = image_manager.get_image_base64(img_info['filename'])
    if not img_base64:
        await search_pic.finish("❌ 读取图片失败")
        return

    # 构建消息
    title = img_info.get('title', '未知')
    author = img_info.get('author', '未知')
    tags = img_info.get('tags', '')
    source = img_info.get('source', '')

    msg = f"🔍 搜索: {keyword}\n"
    msg += f"📊 找到 {len(matched)} 张相关图片\n\n"
    msg += f"🎨 {title}\n"
    msg += f"👤 作者: {author}\n"
    if tags:
        tag_list = tags.split(',')[:5]
        msg += f"🏷️ {', '.join(tag_list)}\n"
    msg += f"📦 来源: {source}"

    # 发送
    try:
        await search_pic.send(msg)
        await search_pic.finish(MessageSegment.image(f"base64://{img_base64}"))
    except Exception as e:
        print(f"发送图片失败: {e}")
        await search_pic.finish("❌ 图片发送失败")


# 多图模式
multi_pic = on_command("来点图", aliases={"多来点", "美图x3"}, priority=5)


@multi_pic.handle()
async def handle_multi_pic(event: MessageEvent, args: Message = CommandArg()):
    """获取多张随机图片（最多5张）"""
    # 解析数量
    arg_text = args.extract_plain_text().strip()
    num = 3  # 默认3张

    if arg_text.isdigit():
        num = min(int(arg_text), 5)  # 最多5张

    # 检查图片库
    total = image_manager.get_total_count()
    if total == 0:
        await multi_pic.finish(
            "❌ 本地图片库为空\n\n"
            "请先使用以下命令下载图片：\n"
            "python scripts/download_anime_pics.py 50"
        )
        return

    if total < num:
        num = total

    await multi_pic.send(f"📦 正在从本地图片库发送 {num} 张图片...")

    success_count = 0
    sent_files = set()  # 避免重复

    for i in range(num):
        # 随机选择图片（避免重复）
        attempts = 0
        img_info = None
        while attempts < 10:  # 最多尝试10次
            temp_img = image_manager.get_random_image()
            if temp_img and temp_img['filename'] not in sent_files:
                img_info = temp_img
                sent_files.add(temp_img['filename'])
                break
            attempts += 1

        if not img_info:
            continue

        # 读取图片
        img_base64 = image_manager.get_image_base64(img_info['filename'])
        if not img_base64:
            continue

        try:
            title = img_info.get('title', '未知')
            author = img_info.get('author', '未知')

            await multi_pic.send(f"[{i+1}/{num}] 🎨 {title} - {author}")
            await multi_pic.send(MessageSegment.image(f"base64://{img_base64}"))
            success_count += 1
        except Exception as e:
            print(f"发送第{i+1}张图片失败: {e}")
            continue

    if success_count > 0:
        await multi_pic.finish(f"✅ 成功发送 {success_count}/{num} 张图片")
    else:
        await multi_pic.finish("❌ 所有图片发送失败")


# 图片库统计
pic_stats = on_command("图片库", aliases={"图库统计", "图片统计"}, priority=5)


@pic_stats.handle()
async def handle_pic_stats(event: MessageEvent):
    """查看图片库统计信息"""
    total = image_manager.get_total_count()

    if total == 0:
        await pic_stats.finish(
            "📊 图片库统计\n\n"
            "❌ 本地图片库为空\n\n"
            "请先使用以下命令下载图片：\n"
            "python scripts/download_anime_pics.py 50"
        )
        return

    # 统计来源
    images = image_manager._load_metadata()
    sources = {}
    for img in images:
        if (IMAGE_DIR / img['filename']).exists():
            source = img.get('source', '未知')
            sources[source] = sources.get(source, 0) + 1

    msg = f"📊 图片库统计\n\n"
    msg += f"📦 总图片数: {total} 张\n"
    msg += f"📁 存储路径: data/anime_pics/\n\n"
    msg += "📈 来源分布:\n"

    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        msg += f"  • {source}: {count} 张\n"

    msg += f"\n💡 使用 /美图 获取随机图片\n"
    msg += f"💡 使用 /搜图 <关键词> 搜索图片"

    await pic_stats.finish(msg)
