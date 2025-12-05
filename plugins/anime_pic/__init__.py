"""
二次元美图插件
使用 Danbooru API 获取随机二次元图片，支持标签搜索
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException
import httpx
import random


# API 配置
DANBOORU_API = "https://danbooru.donmai.us/posts.json"


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片"""
    try:
        # Danbooru API 参数
        params = {
            "tags": "rating:safe order:random",  # 安全内容 + 随机排序
            "limit": 1
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://danbooru.donmai.us/'
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            response = await client.get(DANBOORU_API, params=params)

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()

            if not data or len(data) == 0:
                await random_pic.finish("❌ 没有找到图片")

            # 获取第一张图片
            post = data[0]
            img_url = post.get("file_url")

            if not img_url:
                await random_pic.finish("❌ 图片链接无效")

            # 提取信息
            tags = post.get("tag_string", "").split()[:5]  # 前5个标签
            rating = post.get("rating", "")
            post_id = post.get("id", "")

            # 评级说明
            rating_map = {"s": "安全", "q": "问题", "e": "限制"}
            rating_text = rating_map.get(rating, "未知")

        # 发送图片信息和图片
        msg = f"🎨 Danbooru 随机图片\n"
        msg += f"🆔 ID: {post_id}\n"
        msg += f"🔰 评级: {rating_text}\n"
        if tags:
            msg += f"🏷️ 标签: {', '.join(tags[:3])}"

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
            "/搜图 cat_girl\n"
            "/搜图 original\n"
            "/搜图 1girl solo\n\n"
            "💡 可以使用多个标签（空格分隔）\n"
            "💡 免费用户最多2个标签\n"
            "💡 使用英文标签效果更好"
        )
        return

    try:
        # 处理标签（用空格分隔）
        tags = keyword.replace("，", " ").replace(",", " ")
        search_tags = f"{tags} rating:safe order:random"

        params = {
            "tags": search_tags,
            "limit": 1
        }

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://danbooru.donmai.us/'
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            response = await client.get(DANBOORU_API, params=params)

            if response.status_code != 200:
                await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()

            if not data or len(data) == 0:
                await search_pic.finish(
                    f"❌ 没有找到包含 '{keyword}' 的图片\n\n"
                    "💡 试试其他标签或使用英文标签"
                )

            # 获取图片
            post = data[0]
            img_url = post.get("file_url")

            if not img_url:
                await search_pic.finish("❌ 图片链接无效")

            # 提取信息
            all_tags = post.get("tag_string", "").split()
            rating = post.get("rating", "")
            post_id = post.get("id", "")
            score = post.get("score", 0)

            rating_map = {"s": "安全", "q": "问题", "e": "限制"}
            rating_text = rating_map.get(rating, "未知")

        # 发送信息
        msg = f"🔍 搜索: {keyword}\n\n"
        msg += f"🆔 ID: {post_id}\n"
        msg += f"⭐ 评分: {score}\n"
        msg += f"🔰 评级: {rating_text}\n"
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
        "tags": "rating:safe order:random",
        "limit": num
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    success_count = 0

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            response = await client.get(DANBOORU_API, params=params)

            if response.status_code == 200:
                data = response.json()

                for i, post in enumerate(data[:num], 1):
                    try:
                        img_url = post.get("file_url")
                        if img_url:
                            post_id = post.get("id", "")
                            await multi_pic.send(f"[{i}/{num}] 🎨 ID: {post_id}")
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
