#!/usr/bin/env python3
"""
手动导入图片工具
用于导入已下载的图片到本地图片库，支持压缩和标签管理
"""

import csv
import hashlib
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from PIL import Image

# 配置
SOURCE_DIR = Path("data/import_images")  # 放置待导入图片的目录
IMAGE_DIR = Path("data/anime_pics")
CSV_FILE = Path("data/anime_pics.csv")
TAGS_FILE = Path("data/import_tags.txt")  # 可选的标签文件
COMPRESS_QUALITY = 85
MAX_SIZE = (1920, 1920)


class ImageImporter:
    """图片导入工具"""

    def __init__(self):
        self.source_dir = SOURCE_DIR
        self.image_dir = IMAGE_DIR
        self.csv_file = CSV_FILE
        self.tags_file = TAGS_FILE

        # 创建目录
        self.source_dir.mkdir(parents=True, exist_ok=True)
        self.image_dir.mkdir(parents=True, exist_ok=True)

        # 初始化CSV
        self._init_csv()

    def _init_csv(self):
        """初始化CSV文件"""
        if not self.csv_file.exists():
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'filename', 'title', 'author', 'tags',
                    'source', 'source_id', 'download_time',
                    'width', 'height', 'file_size'
                ])

    def _generate_filename(self, original_name: str) -> str:
        """生成唯一文件名"""
        name_hash = hashlib.md5(original_name.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:17]
        return f"{timestamp}_{name_hash}.jpg"

    def _compress_image(self, img: Image.Image) -> Image.Image:
        """压缩图片"""
        # 转换RGBA为RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if img.mode in ('RGBA', 'LA'):
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        # 调整大小
        if img.width > MAX_SIZE[0] or img.height > MAX_SIZE[1]:
            img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)

        return img

    def _save_image(self, img: Image.Image, filename: str) -> tuple[int, int, int]:
        """保存压缩后的图片"""
        filepath = self.image_dir / filename

        # 压缩图片
        compressed_img = self._compress_image(img)

        # 保存
        compressed_img.save(
            filepath,
            'JPEG',
            quality=COMPRESS_QUALITY,
            optimize=True
        )

        file_size = filepath.stat().st_size
        return compressed_img.width, compressed_img.height, file_size

    def _save_metadata(self, metadata: Dict):
        """保存元数据到CSV"""
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                metadata.get('filename', ''),
                metadata.get('title', ''),
                metadata.get('author', ''),
                metadata.get('tags', ''),
                metadata.get('source', ''),
                metadata.get('source_id', ''),
                metadata.get('download_time', ''),
                metadata.get('width', 0),
                metadata.get('height', 0),
                metadata.get('file_size', 0)
            ])

    def _load_tags_mapping(self) -> Dict[str, str]:
        """加载标签映射文件"""
        if not self.tags_file.exists():
            return {}

        mapping = {}
        try:
            with open(self.tags_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        filename, tags = line.split('=', 1)
                        mapping[filename.strip()] = tags.strip()
        except Exception as e:
            print(f"⚠️ 读取标签文件失败: {e}")

        return mapping

    def import_images(self, default_tags: str = "二次元,动漫") -> tuple[int, int]:
        """导入所有图片"""
        print(f"📂 扫描导入目录: {self.source_dir.absolute()}")
        print(f"📁 目标目录: {self.image_dir.absolute()}")
        print(f"🔧 压缩质量: {COMPRESS_QUALITY}, 最大尺寸: {MAX_SIZE}")
        print("-" * 60)

        # 加载标签映射
        tags_mapping = self._load_tags_mapping()
        if tags_mapping:
            print(f"📝 加载了 {len(tags_mapping)} 个标签映射")

        # 支持的图片格式
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}

        # 查找所有图片文件
        image_files = []
        for ext in image_extensions:
            image_files.extend(self.source_dir.glob(f"*{ext}"))
            image_files.extend(self.source_dir.glob(f"*{ext.upper()}"))

        if not image_files:
            print(f"❌ 在 {self.source_dir} 中没有找到图片文件")
            print(f"💡 请将图片放到该目录中，支持的格式: {', '.join(image_extensions)}")
            return 0, 0

        print(f"🔍 找到 {len(image_files)} 张图片\n")

        success = 0
        failed = 0

        for i, img_path in enumerate(image_files, 1):
            try:
                print(f"[{i}/{len(image_files)}] {img_path.name}")

                # 打开图片
                img = Image.open(img_path)

                # 生成新文件名
                new_filename = self._generate_filename(img_path.name)

                # 保存压缩图片
                width, height, file_size = self._save_image(img, new_filename)

                # 获取标签
                tags = tags_mapping.get(img_path.name, default_tags)

                # 保存元数据
                metadata = {
                    'filename': new_filename,
                    'title': img_path.stem,  # 使用原文件名作为标题
                    'author': '手动导入',
                    'tags': tags,
                    'source': '本地导入',
                    'source_id': '',
                    'download_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'width': width,
                    'height': height,
                    'file_size': file_size
                }
                self._save_metadata(metadata)

                file_size_kb = file_size / 1024
                original_size_kb = img_path.stat().st_size / 1024
                compression_ratio = (1 - file_size / img_path.stat().st_size) * 100

                print(f"  ✅ {width}x{height}")
                print(f"  📦 {original_size_kb:.1f}KB → {file_size_kb:.1f}KB (压缩 {compression_ratio:.1f}%)")
                print(f"  🏷️ {tags}")

                success += 1

            except Exception as e:
                print(f"  ❌ 失败: {e}")
                failed += 1
                continue

        print("\n" + "=" * 60)
        print(f"📊 导入完成! 成功: {success}, 失败: {failed}")
        print(f"📁 图片保存在: {self.image_dir.absolute()}")
        print(f"📄 元数据保存在: {self.csv_file.absolute()}")

        return success, failed


def create_tags_template():
    """创建标签模板文件"""
    template = """# 图片标签映射文件
# 格式: 文件名 = 标签1,标签2,标签3
# 示例:
# image001.jpg = 白毛,猫娘,可爱
# image002.png = 原神,胡桃,萝莉
#
# 如果不指定，默认使用: 二次元,动漫

"""
    with open(TAGS_FILE, 'w', encoding='utf-8') as f:
        f.write(template)

    print(f"✅ 已创建标签模板文件: {TAGS_FILE.absolute()}")
    print("💡 编辑此文件为每张图片指定标签")


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='手动导入图片工具')
    parser.add_argument('--tags', type=str, default='二次元,动漫', help='默认标签（逗号分隔）')
    parser.add_argument('--create-template', action='store_true', help='创建标签模板文件')

    args = parser.parse_args()

    if args.create_template:
        create_tags_template()
        return

    # 确保导入目录存在
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    importer = ImageImporter()
    importer.import_images(args.tags)


if __name__ == "__main__":
    main()
