#!/usr/bin/env python3
"""
二次元图片批量下载脚本
功能：
1. 从多个API源下载图片
2. 压缩图片并保存到本地
3. 抓取元数据（标签、标题、作者等）并保存到CSV
"""

import asyncio
import csv
import hashlib
import os
import sys
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from PIL import Image

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

# 配置
IMAGE_DIR = Path("data/anime_pics")
CSV_FILE = Path("data/anime_pics.csv")
COMPRESS_QUALITY = 85  # JPEG压缩质量 (1-100)
MAX_SIZE = (1920, 1920)  # 最大分辨率


class AnimeImageDownloader:
    """二次元图片下载器"""

    def __init__(self):
        self.image_dir = IMAGE_DIR
        self.csv_file = CSV_FILE
        self.image_dir.mkdir(parents=True, exist_ok=True)

        # API配置
        self.apis = [
            {
                "name": "Lolicon",
                "url": "https://api.lolicon.app/setu/v2",
                "params": {"r18": 0, "num": 1, "size": ["regular"], "proxy": "i.pixiv.re"},
                "type": "lolicon"
            },
            {
                "name": "搏天API",
                "url": "https://api.btstu.cn/sjbz/api.php",
                "params": {"lx": "dongman", "format": "json"},
                "type": "btstu"
            },
            {
                "name": "保罗API",
                "url": "https://api.paugram.com/wallpaper/",
                "params": {"source": "pixiv"},
                "type": "paugram"
            },
            {
                "name": "Dmoe",
                "url": "https://www.dmoe.cc/random.php",
                "params": {"return": "json"},
                "type": "dmoe"
            }
        ]

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

    def _generate_filename(self, url: str, ext: str = 'jpg') -> str:
        """根据URL生成唯一文件名"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{timestamp}_{url_hash}.{ext}"

    def _compress_image(self, img: Image.Image) -> Image.Image:
        """压缩图片"""
        # 转换RGBA为RGB
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
            img = background

        # 调整大小
        if img.width > MAX_SIZE[0] or img.height > MAX_SIZE[1]:
            img.thumbnail(MAX_SIZE, Image.Resampling.LANCZOS)

        return img

    async def _download_image(self, url: str) -> Optional[Image.Image]:
        """下载图片"""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    img = Image.open(BytesIO(response.content))
                    return img
        except Exception as e:
            print(f"❌ 下载图片失败: {e}")
        return None

    def _save_image(self, img: Image.Image, filename: str) -> tuple[int, int, int]:
        """保存压缩后的图片，返回(宽度, 高度, 文件大小)"""
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

    async def _fetch_lolicon(self, api: Dict) -> Optional[Dict]:
        """从Lolicon API获取图片信息"""
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(api["url"], params=api["params"])
                if response.status_code == 200:
                    data = response.json()
                    pics = data.get("data", [])
                    if pics:
                        pic = pics[0]
                        urls = pic.get("urls", {})
                        img_url = urls.get("regular")
                        if img_url:
                            return {
                                "url": img_url,
                                "title": pic.get("title", "未知"),
                                "author": pic.get("author", "未知"),
                                "tags": ",".join(pic.get("tags", [])),
                                "source": "Lolicon",
                                "source_id": str(pic.get("pid", ""))
                            }
        except Exception as e:
            print(f"❌ Lolicon API失败: {e}")
        return None

    async def _fetch_btstu(self, api: Dict) -> Optional[Dict]:
        """从搏天API获取图片信息"""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(api["url"], params=api["params"])
                if response.status_code == 200:
                    data = response.json()
                    img_url = data.get("imgurl")
                    if img_url:
                        return {
                            "url": img_url,
                            "title": "二次元壁纸",
                            "author": "搏天API",
                            "tags": "动漫,壁纸",
                            "source": "搏天API",
                            "source_id": ""
                        }
        except Exception as e:
            print(f"❌ 搏天API失败: {e}")
        return None

    async def _fetch_paugram(self, api: Dict) -> Optional[Dict]:
        """从保罗API获取图片信息"""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(api["url"], params=api["params"])
                if response.status_code == 200:
                    data = response.json()
                    img_url = data.get("url")
                    if img_url:
                        return {
                            "url": img_url,
                            "title": "Pixiv壁纸",
                            "author": "保罗API",
                            "tags": "pixiv,壁纸",
                            "source": "保罗API",
                            "source_id": ""
                        }
        except Exception as e:
            print(f"❌ 保罗API失败: {e}")
        return None

    async def _fetch_dmoe(self, api: Dict) -> Optional[Dict]:
        """从Dmoe API获取图片信息"""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(api["url"], params=api["params"])
                if response.status_code == 200:
                    data = response.json()
                    img_url = data.get("imgurl")
                    if img_url:
                        return {
                            "url": img_url,
                            "title": "二次元图片",
                            "author": "Dmoe",
                            "tags": "二次元,动漫",
                            "source": "Dmoe",
                            "source_id": ""
                        }
        except Exception as e:
            print(f"❌ Dmoe API失败: {e}")
        return None

    async def download_one(self, api_name: Optional[str] = None) -> bool:
        """下载一张图片"""
        # 选择API
        apis_to_try = self.apis if not api_name else [a for a in self.apis if a["name"] == api_name]

        for api in apis_to_try:
            print(f"🔄 尝试使用 {api['name']}...")

            # 根据API类型调用对应的fetch方法
            image_info = None
            if api["type"] == "lolicon":
                image_info = await self._fetch_lolicon(api)
            elif api["type"] == "btstu":
                image_info = await self._fetch_btstu(api)
            elif api["type"] == "paugram":
                image_info = await self._fetch_paugram(api)
            elif api["type"] == "dmoe":
                image_info = await self._fetch_dmoe(api)

            if not image_info:
                continue

            # 下载图片
            print(f"📥 下载图片: {image_info['title']}")
            img = await self._download_image(image_info["url"])
            if not img:
                continue

            # 生成文件名
            filename = self._generate_filename(image_info["url"])

            # 保存图片
            print(f"💾 保存图片: {filename}")
            width, height, file_size = self._save_image(img, filename)

            # 保存元数据
            metadata = {
                **image_info,
                "filename": filename,
                "download_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "width": width,
                "height": height,
                "file_size": file_size
            }
            self._save_metadata(metadata)

            file_size_kb = file_size / 1024
            print(f"✅ 成功! {width}x{height}, {file_size_kb:.1f}KB, 标签: {image_info['tags']}")
            return True

        print("❌ 所有API都失败了")
        return False

    async def download_batch(self, count: int, api_name: Optional[str] = None):
        """批量下载图片"""
        print(f"🚀 开始批量下载 {count} 张图片...")
        print(f"📁 保存目录: {self.image_dir.absolute()}")
        print(f"📊 元数据文件: {self.csv_file.absolute()}")
        print(f"🔧 压缩质量: {COMPRESS_QUALITY}, 最大尺寸: {MAX_SIZE}")
        print("-" * 60)

        success = 0
        failed = 0

        for i in range(count):
            print(f"\n[{i+1}/{count}]")
            if await self.download_one(api_name):
                success += 1
            else:
                failed += 1

            # 避免请求过快
            if i < count - 1:
                await asyncio.sleep(2)

        print("\n" + "=" * 60)
        print(f"📊 下载完成! 成功: {success}, 失败: {failed}")
        print(f"📁 图片保存在: {self.image_dir.absolute()}")
        print(f"📄 元数据保存在: {self.csv_file.absolute()}")


async def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description='二次元图片批量下载工具')
    parser.add_argument('count', type=int, nargs='?', default=10, help='下载数量 (默认: 10)')
    parser.add_argument('--api', type=str, help='指定API源 (Lolicon/搏天API/保罗API/Dmoe)')

    args = parser.parse_args()

    downloader = AnimeImageDownloader()
    await downloader.download_batch(args.count, args.api)


if __name__ == "__main__":
    asyncio.run(main())
