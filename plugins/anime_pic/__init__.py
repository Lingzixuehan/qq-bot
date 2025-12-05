"""
二次元美图插件
使用 Waifu.im API 获取随机二次元图片，支持标签搜索
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException
import httpx
import random


# API 配置
WAIFU_API = "https://api.waifu.im/search"


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片"""
    try:
        # Waifu.im API 参数
        params = {
            "is_nsfw": "false"  # 只要安全内容
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            response = await client.get(WAIFU_API, params=params)

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()
            images = data.get("images", [])

            if not images:
                await random_pic.finish("❌ 没有找到图片")

            # 获取第一张图片
            img = images[0]
            img_url = img.get("url")

            if not img_url:
                await random_pic.finish("❌ 图片链接无效")

            # 提取信息
            tags = [tag.get("name") for tag in img.get("tags", [])[:5]]
            artist = img.get("artist", {})
            artist_name = artist.get("name", "未知") if artist else "未知"
            width = img.get("width", "未知")
            height = img.get("height", "未知")

        # 发送图片信息和图片
        msg = f"🎨 Waifu.im 随机图片\n"
        msg += f"👤 画师: {artist_name}\n"
        msg += f"📐 尺寸: {width}x{height}\n"
        if tags:
            msg += f"🏷️ 标签: {', '.join(tags)}"

        await random_pic.send(msg)
        await random_pic.finish(MessageSegment.image(img_url))

    except FinishedException:
        raise
    except httpx.TimeoutException:
        await random_pic.finish("❌ 请求超时，请稍后重试")
    except httpx.HTTPError as e:
        print(f"HTTP错误: {e}")
        await random_pic.finish("❌ 网络请求失败，请稍后重试")
    except Exception as e:
        print(f"获取图片失败: {e}")
        import traceback
        traceback.print_exc()
        await random_pic.finish("❌ 获取图片时出错")


# 标签搜索图片
search_pic = on_command("搜图", aliases={"找图", "图片搜索"}, priority=5)


@search_pic.handle()
async def handle_search_pic(event: MessageEvent, args: Message = CommandArg()):
    """根据标签搜索图片"""
    keyword = args.extract_plain_text().strip()

    if not keyword:
        await search_pic.finish(
            "用法：/搜图 <标签>\n\n"
            "示例：\n"
            "/搜图 maid\n"
            "/搜图 waifu\n"
            "/搜图 uniform\n\n"
            "💡 可用标签：maid, waifu, marin-kitagawa, mori-calliope, \n"
            "    raiden-shogun, oppai, selfies, uniform 等\n"
            "💡 使用英文标签，多个标签用空格分隔"
        )
        return

    try:
        # 处理标签（空格分隔）
        tags = keyword.replace("，", ",").replace(",", " ").strip().split()

        params = {
            "is_nsfw": "false"
        }

        # 添加所有标签
        if tags:
            params["included_tags"] = tags

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            response = await client.get(WAIFU_API, params=params)

            if response.status_code != 200:
                await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()
            images = data.get("images", [])

            if not images:
                await search_pic.finish(
                    f"❌ 没有找到包含 '{keyword}' 的图片\n\n"
                    "💡 试试其他标签，如：maid, waifu, uniform"
                )

            # 获取图片
            img = images[0]
            img_url = img.get("url")

            if not img_url:
                await search_pic.finish("❌ 图片链接无效")

            # 提取信息
            all_tags = [tag.get("name") for tag in img.get("tags", [])]
            artist = img.get("artist", {})
            artist_name = artist.get("name", "未知") if artist else "未知"
            width = img.get("width", "未知")
            height = img.get("height", "未知")
            favorites = img.get("favorites", 0)

        # 发送信息
        msg = f"🔍 搜索: {keyword}\n\n"
        msg += f"👤 画师: {artist_name}\n"
        msg += f"📐 尺寸: {width}x{height}\n"
        msg += f"❤️ 收藏: {favorites}\n"
        if all_tags:
            msg += f"🏷️ 标签: {', '.join(all_tags[:5])}"

        await search_pic.send(msg)
        await search_pic.finish(MessageSegment.image(img_url))

    except FinishedException:
        raise
    except httpx.TimeoutException:
        await search_pic.finish("❌ 请求超时，请稍后重试")
    except httpx.HTTPError as e:
        print(f"HTTP错误: {e}")
        await search_pic.finish("❌ 网络请求失败，请稍后重试")
    except Exception as e:
        print(f"搜索图片失败: {e}")
        import traceback
        traceback.print_exc()
        await search_pic.finish("❌ 搜索图片时出错")


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

    await multi_pic.send(f"📦 正在获取 {num} 张图片...")

    params = {
        "is_nsfw": "false",
        "many": str(num)  # 一次请求多张
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    success_count = 0

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            response = await client.get(WAIFU_API, params=params)

            if response.status_code == 200:
                data = response.json()
                images = data.get("images", [])

                for i, img in enumerate(images[:num], 1):
                    try:
                        img_url = img.get("url")
                        if img_url:
                            await multi_pic.send(MessageSegment.image(img_url))
                            success_count += 1
                    except Exception as e:
                        print(f"发送第{i}张图片失败: {e}")
                        continue

    except Exception as e:
        print(f"获取多图失败: {e}")

    if success_count > 0:
        await multi_pic.finish(f"✅ 成功发送 {success_count}/{num} 张图片")
    else:
        await multi_pic.finish("❌ 所有图片获取失败")
