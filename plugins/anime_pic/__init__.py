"""
二次元美图插件
支持 LoliAPI 和 Danbooru API，可通过配置切换
"""
from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException
import httpx
import random


# 获取配置
driver = get_driver()
config = driver.config
API_SOURCE = getattr(config, "anime_pic_api", "loli").lower()

# API 配置
LOLI_API = "https://www.loliapi.com/bg/"
DANBOORU_API = "https://danbooru.donmai.us/posts.json"


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }

        if API_SOURCE == "danbooru":
            # 使用 Danbooru API
            params = {
                "tags": "rating:safe order:random",
                "limit": 1
            }

            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(DANBOORU_API, params=params)

                if response.status_code != 200:
                    await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

                data = response.json()
                if not data or len(data) == 0:
                    await random_pic.finish("❌ 没有找到图片")

                post = data[0]
                img_url = post.get('file_url') or post.get('large_file_url')

                if not img_url:
                    await random_pic.finish("❌ 图片链接无效")

                # 提取信息
                tags = post.get('tag_string', '').split()[:3]
                post_id = post.get('id', '')

                msg = f"🎨 Danbooru 随机图片\n🆔 ID: {post_id}"
                if tags:
                    msg += f"\n🏷️ {', '.join(tags)}"
        else:
            # 使用 LoliAPI
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(LOLI_API)

                if response.status_code != 200:
                    await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

                img_url = str(response.url)

                if not img_url:
                    await random_pic.finish("❌ 图片链接无效")

                msg = "🎨 LoliAPI 随机图片"

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
        if API_SOURCE == "danbooru":
            await search_pic.finish(
                "用法：/搜图 <标签>\n\n"
                "示例：\n"
                "/搜图 cat_girl\n"
                "/搜图 maid\n"
                "/搜图 1girl solo\n\n"
                "💡 使用英文标签，空格分隔多个标签"
            )
        else:
            await search_pic.finish(
                "用法：/搜图 <关键词>\n\n"
                "💡 注意：当前使用LoliAPI，暂不支持标签搜索\n"
                "💡 将返回随机图片"
            )
        return

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json'
        }

        if API_SOURCE == "danbooru":
            # 使用 Danbooru API 进行标签搜索
            search_tags = f"{keyword} rating:safe order:random"
            params = {
                "tags": search_tags,
                "limit": 1
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

                post = data[0]
                img_url = post.get('file_url') or post.get('large_file_url')

                if not img_url:
                    await search_pic.finish("❌ 图片链接无效")

                # 提取信息
                all_tags = post.get('tag_string', '').split()
                post_id = post.get('id', '')
                score = post.get('score', 0)

                msg = f"🔍 搜索: {keyword}\n\n"
                msg += f"🆔 ID: {post_id}\n"
                msg += f"⭐ 评分: {score}\n"
                if all_tags:
                    msg += f"🏷️ 标签: {', '.join(all_tags[:5])}"
        else:
            # LoliAPI 不支持标签搜索，返回随机图片
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(LOLI_API)

                if response.status_code != 200:
                    await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

                img_url = str(response.url)

                if not img_url:
                    await search_pic.finish("❌ 图片链接无效")

                msg = f"🔍 搜索: {keyword}\n"
                msg += "💡 LoliAPI暂不支持标签搜索，返回随机图片"

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

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }

    success_count = 0

    try:
        if API_SOURCE == "danbooru":
            # 使用 Danbooru API
            params = {
                "tags": "rating:safe order:random",
                "limit": num
            }

            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
                response = await client.get(DANBOORU_API, params=params)

                if response.status_code == 200:
                    data = response.json()

                    for post in data[:num]:
                        try:
                            img_url = post.get('file_url') or post.get('large_file_url')
                            if img_url:
                                await multi_pic.send(MessageSegment.image(img_url))
                                success_count += 1
                        except Exception as e:
                            print(f"发送图片失败: {e}")
                            continue
        else:
            # 使用 LoliAPI
            async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
                for i in range(num):
                    try:
                        response = await client.get(LOLI_API)
                        if response.status_code == 200:
                            img_url = str(response.url)
                            if img_url:
                                await multi_pic.send(MessageSegment.image(img_url))
                                success_count += 1
                    except Exception as e:
                        print(f"发送第{i+1}张图片失败: {e}")
                        continue

    except Exception as e:
        print(f"获取多图失败: {e}")

    if success_count > 0:
        await multi_pic.finish(f"✅ 成功发送 {success_count}/{num} 张图片")
    else:
        await multi_pic.finish("❌ 所有图片获取失败")
