"""
二次元美图插件
支持多个API源：LoliAPI、Danbooru、Safebooru、Lolicon
可通过配置切换
"""
from nonebot import on_command, get_driver
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException
from nonebot.log import logger
import requests
import asyncio
import random
import base64
import httpx
from datetime import datetime, timedelta


# 获取配置
driver = get_driver()
config = driver.config
DEFAULT_API = getattr(config, "anime_pic_api", "lolicon").lower()

# 频率限制配置
RATE_LIMIT_CONFIG = {}
rate_limit_str = getattr(config, "search_pic_rate_limit_groups", "")
if rate_limit_str:
    # 格式：群号:次数,群号:次数
    for item in rate_limit_str.split(","):
        if ":" in item:
            group_id, limit = item.strip().split(":")
            RATE_LIMIT_CONFIG[group_id.strip()] = int(limit.strip())

# 白名单配置（不受频率限制的QQ号）
RATE_LIMIT_WHITELIST = set()
whitelist_str = getattr(config, "search_pic_whitelist", "")
if whitelist_str:
    # 格式：QQ号,QQ号,QQ号
    whitelist_str = str(whitelist_str)  # 确保是字符串类型
    RATE_LIMIT_WHITELIST = set(uid.strip() for uid in whitelist_str.split(",") if uid.strip())

# 频率限制数据：{群号: {用户ID: {"count": 次数, "reset_time": 重置时间}}}
rate_limit_data = {}

# API 配置
LOLI_API = "https://www.loliapi.com/bg/"
DANBOORU_API = "https://danbooru.donmai.us/posts.json"
SAFEBOORU_API = "https://safebooru.org/index.php"
LOLICON_API = "https://api.lolicon.app/setu/v2"

# 支持的API列表
SUPPORTED_APIS = ["loli", "safebooru", "lolicon", "danbooru"]


def check_rate_limit(group_id: str, user_id: str) -> tuple[bool, int, int]:
    """
    检查频率限制
    返回：(是否允许, 已使用次数, 限制次数)
    """
    # 白名单用户不受限制
    if user_id in RATE_LIMIT_WHITELIST:
        return True, 0, 0

    if group_id not in RATE_LIMIT_CONFIG:
        return True, 0, 0  # 不限制

    limit = RATE_LIMIT_CONFIG[group_id]
    now = datetime.now()

    # 初始化群数据
    if group_id not in rate_limit_data:
        rate_limit_data[group_id] = {}

    # 初始化用户数据或检查重置时间
    if user_id not in rate_limit_data[group_id]:
        rate_limit_data[group_id][user_id] = {
            "count": 0,
            "reset_time": now + timedelta(hours=1)
        }
    else:
        user_data = rate_limit_data[group_id][user_id]
        # 检查是否需要重置
        if now >= user_data["reset_time"]:
            user_data["count"] = 0
            user_data["reset_time"] = now + timedelta(hours=1)

    user_data = rate_limit_data[group_id][user_id]
    used = user_data["count"]

    return used < limit, used, limit


def increment_usage(group_id: str, user_id: str):
    """增加使用次数"""
    if group_id in rate_limit_data and user_id in rate_limit_data[group_id]:
        rate_limit_data[group_id][user_id]["count"] += 1


async def download_image_as_base64(
    url: str,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delay: float = 3.0
) -> MessageSegment | None:
    """
    下载图片并转换为 base64 格式的 MessageSegment
    这样可以避免 NapCat 下载外部 URL 失败的问题

    支持失败重试机制

    Args:
        url: 图片URL
        timeout: 超时时间（秒），默认30秒
        max_retries: 最大重试次数，默认3次
        retry_delay: 重试间隔（秒），默认3秒

    Returns:
        MessageSegment.image 或 None（下载失败时）
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": url,
    }

    last_error = None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.get(url, headers=headers)

                if response.status_code == 200:
                    # 成功，转换为 base64
                    img_base64 = base64.b64encode(response.content).decode()
                    if attempt > 0:
                        logger.info(f"下载图片成功（第{attempt + 1}次尝试）: {url}")
                    return MessageSegment.image(f"base64://{img_base64}")
                else:
                    last_error = f"status={response.status_code}"
                    logger.warning(f"下载图片失败（第{attempt + 1}/{max_retries}次）: {url}, {last_error}")

        except httpx.TimeoutException:
            last_error = "超时"
            logger.warning(f"下载图片超时（第{attempt + 1}/{max_retries}次）: {url}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"下载图片异常（第{attempt + 1}/{max_retries}次）: {url}, error={e}")

        # 如果还有重试机会，等待后继续
        if attempt < max_retries - 1:
            logger.info(f"等待 {retry_delay} 秒后重试...")
            await asyncio.sleep(retry_delay)

    logger.error(f"下载图片最终失败（已重试{max_retries}次）: {url}, 最后错误: {last_error}")
    return None


async def send_image_safe(matcher, url: str, fallback_msg: str = "图片加载失败"):
    """
    安全地发送图片，如果下载失败则发送提示消息

    Args:
        matcher: nonebot matcher
        url: 图片URL
        fallback_msg: 下载失败时的提示消息
    """
    img_seg = await download_image_as_base64(url)
    if img_seg:
        await matcher.finish(img_seg)
    else:
        await matcher.finish(f"❌ {fallback_msg}\n🔗 原图: {url}")


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent, args: Message = CommandArg()):
    """获取随机二次元图片"""
    # 解析API源参数
    arg_text = args.extract_plain_text().strip().lower()
    api_source = arg_text if arg_text in SUPPORTED_APIS else DEFAULT_API

    try:
        if api_source == "safebooru":
            # 使用 Safebooru API
            random_page = random.randint(0, 200)
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": 20,
                "tags": "rating:safe score:>=10",
                "pid": random_page
            }

            logger.info(f"[Safebooru] 请求随机图片，页码: {random_page}")

            response = await asyncio.to_thread(
                requests.get,
                SAFEBOORU_API,
                params=params,
                timeout=15
            )
            logger.info(f"[Safebooru] API响应状态码: {response.status_code}")

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()
            if not isinstance(data, list) or len(data) == 0:
                await random_pic.finish("❌ 没有找到图片")

            post = random.choice(data)
            img_url = post.get('file_url') or post.get('image')

            if not img_url:
                await random_pic.finish("❌ 图片链接无效")

            post_id = post.get('id', '')
            score = post.get('score', 0)

            msg = f"🎨 Safebooru 随机图片\n🆔 ID: {post_id}\n⭐ 评分: {score}"

        elif api_source == "lolicon":
            # 使用 Lolicon API
            payload = {
                "r18": 0,
                "num": 1,
                "size": ["original", "regular"]
            }

            logger.info("[Lolicon] 请求随机图片")

            response = await asyncio.to_thread(
                requests.post,
                LOLICON_API,
                json=payload,
                timeout=15
            )
            logger.info(f"[Lolicon] API响应状态码: {response.status_code}")

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            result = response.json()
            data = result.get('data', [])

            if not data or len(data) == 0:
                await random_pic.finish("❌ 没有找到图片")

            post = data[0]
            urls = post.get('urls', {})
            img_url = urls.get('original') or urls.get('regular')

            if not img_url:
                await random_pic.finish("❌ 图片链接无效")

            pid = post.get('pid', '')
            title = post.get('title', '')
            author = post.get('author', '')

            msg = f"🎨 Lolicon 随机图片\n🆔 PID: {pid}\n📝 {title}\n👤 {author}"

        elif api_source == "danbooru":
            # 使用 Danbooru API - 使用随机页码代替 order:random
            random_page = random.randint(1, 1000)
            params = {
                "tags": "rating:safe",
                "limit": 20,
                "page": random_page
            }

            logger.info(f"[Danbooru] 请求随机图片，页码: {random_page}")

            response = await asyncio.to_thread(
                requests.get,
                DANBOORU_API,
                params=params,
                timeout=15
            )
            logger.info(f"[Danbooru] API响应状态码: {response.status_code}")

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()
            if not data or len(data) == 0:
                await random_pic.finish("❌ 没有找到图片")

            post = random.choice(data)
            img_url = post.get('file_url') or post.get('large_file_url')

            if not img_url:
                await random_pic.finish("❌ 图片链接无效")

            tags = post.get('tag_string', '').split()[:3]
            post_id = post.get('id', '')

            msg = f"🎨 Danbooru 随机图片\n🆔 ID: {post_id}"
            if tags:
                msg += f"\n🏷️ {', '.join(tags)}"

        else:
            # 使用 LoliAPI (默认)
            response = await asyncio.to_thread(
                requests.get,
                LOLI_API,
                timeout=15,
                allow_redirects=True
            )

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            img_url = response.url

            if not img_url:
                await random_pic.finish("❌ 图片链接无效")

            msg = "🎨 LoliAPI 随机图片"

        await random_pic.send(msg)
        # 先下载图片再发送，避免NapCat下载外部URL失败
        img_seg = await download_image_as_base64(img_url)
        if img_seg:
            await random_pic.finish(img_seg)
        else:
            await random_pic.finish(f"❌ 图片加载失败\n🔗 原图: {img_url}")

    except FinishedException:
        raise
    except requests.Timeout as e:
        logger.error(f"[美图] 请求超时: {e}")
        await random_pic.finish("❌ 请求超时，请稍后重试")
    except requests.RequestException as e:
        logger.error(f"[美图] 请求错误: {e}")
        await random_pic.finish(f"❌ 网络请求失败: {str(e)[:100]}")
    except Exception as e:
        logger.error(f"[美图] 获取图片失败: {e}")
        import traceback
        traceback.print_exc()
        await random_pic.finish(f"❌ 获取图片时出错: {str(e)[:100]}")


# 标签搜索图片
search_pic = on_command("搜图", aliases={"找图", "图片搜索"}, priority=5)


@search_pic.handle()
async def handle_search_pic(event: MessageEvent, args: Message = CommandArg()):
    """根据标签搜索图片"""
    # 频率限制检查（仅群聊）
    if isinstance(event, GroupMessageEvent):
        group_id = str(event.group_id)
        user_id = str(event.user_id)

        allowed, used, limit = check_rate_limit(group_id, user_id)
        if not allowed:
            remaining_time = rate_limit_data[group_id][user_id]["reset_time"] - datetime.now()
            minutes = int(remaining_time.total_seconds() / 60)
            await search_pic.finish(
                f"⏰ 搜图次数已用完\n"
                f"📊 已使用: {used}/{limit} 次\n"
                f"⏱️ 重置时间: {minutes}分钟后"
            )

    arg_text = args.extract_plain_text().strip()

    # 解析参数：关键词和API源
    parts = arg_text.split()
    if not parts:
        keyword = ""
        api_source = DEFAULT_API
    elif parts[-1].lower() in SUPPORTED_APIS:
        # 最后一个参数是API源
        api_source = parts[-1].lower()
        keyword = " ".join(parts[:-1])
    else:
        # 没有指定API源
        keyword = arg_text
        api_source = DEFAULT_API

    if not keyword:
        if api_source in ["safebooru", "danbooru"]:
            await search_pic.finish(
                "用法：/搜图 <标签>\n\n"
                "示例：\n"
                "/搜图 cat_girl\n"
                "/搜图 touhou\n"
                "/搜图 maid\n\n"
                "💡 使用英文标签，空格分隔多个标签"
            )
        elif api_source == "lolicon":
            await search_pic.finish(
                "用法：/搜图 <标签>\n\n"
                "示例：\n"
                "/搜图 猫耳\n"
                "/搜图 女孩子\n\n"
                "💡 支持中文或英文标签"
            )
        else:
            await search_pic.finish(
                "用法：/搜图 <关键词>\n\n"
                "💡 注意：当前使用LoliAPI，暂不支持标签搜索\n"
                "💡 将返回随机图片"
            )
        return

    try:
        if api_source == "safebooru":
            # 使用 Safebooru API - 支持关键词搜索 + 默认过滤
            random_page = random.randint(0, 100)
            search_tags = f"{keyword} rating:safe score:>=10"
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": 20,
                "tags": search_tags,
                "pid": random_page
            }

            response = await asyncio.to_thread(
                requests.get,
                SAFEBOORU_API,
                params=params,
                timeout=15
            )

            if response.status_code != 200:
                await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()
            if not isinstance(data, list) or len(data) == 0:
                await search_pic.finish(
                    f"❌ 没有找到包含 '{keyword}' 的图片\n\n"
                    "💡 试试其他标签"
                )

            post = random.choice(data)
            img_url = post.get('file_url') or post.get('image')

            if not img_url:
                await search_pic.finish("❌ 图片链接无效")

            post_id = post.get('id', '')
            score = post.get('score', 0)

            msg = f"🔍 搜索: {keyword}\n\n"
            msg += f"🆔 ID: {post_id}\n"
            msg += f"⭐ 评分: {score}"

        elif api_source == "lolicon":
            # 使用 Lolicon API - 支持标签搜索
            payload = {
                "r18": 0,
                "num": 1,
                "tag": [keyword],
                "size": ["original", "regular"]
            }

            response = await asyncio.to_thread(
                requests.post,
                LOLICON_API,
                json=payload,
                timeout=15
            )

            if response.status_code != 200:
                await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            result = response.json()
            data = result.get('data', [])

            if not data or len(data) == 0:
                await search_pic.finish(
                    f"❌ 没有找到包含 '{keyword}' 的图片\n\n"
                    "💡 试试其他标签"
                )

            post = data[0]
            urls = post.get('urls', {})
            img_url = urls.get('original') or urls.get('regular')

            if not img_url:
                await search_pic.finish("❌ 图片链接无效")

            pid = post.get('pid', '')
            title = post.get('title', '')
            author = post.get('author', '')
            tags = post.get('tags', [])[:5]

            msg = f"🔍 搜索: {keyword}\n\n"
            msg += f"🆔 PID: {pid}\n"
            msg += f"📝 {title}\n"
            msg += f"👤 {author}"
            if tags:
                msg += f"\n🏷️ {', '.join(tags)}"

        elif api_source == "danbooru":
            # 使用 Danbooru API 进行标签搜索 - 使用随机页码
            random_page = random.randint(1, 100)
            search_tags = f"{keyword} rating:safe"
            params = {
                "tags": search_tags,
                "limit": 20,
                "page": random_page
            }

            # 使用 requests 库（通过 asyncio.to_thread 异步调用）
            # 不设置headers，使用requests默认User-Agent
            response = await asyncio.to_thread(
                requests.get,
                DANBOORU_API,
                params=params,
                timeout=15
            )

            if response.status_code != 200:
                await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()
            if not data or len(data) == 0:
                await search_pic.finish(
                    f"❌ 没有找到包含 '{keyword}' 的图片\n\n"
                    "💡 试试其他标签或使用英文标签"
                )

            # 从获取的结果中随机选择一个
            post = random.choice(data)
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
            response = await asyncio.to_thread(
                requests.get,
                LOLI_API,
                timeout=15,
                allow_redirects=True
            )

            if response.status_code != 200:
                await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            img_url = response.url

            if not img_url:
                await search_pic.finish("❌ 图片链接无效")

            msg = f"🔍 搜索: {keyword}\n"
            msg += "💡 LoliAPI暂不支持标签搜索，返回随机图片"

        # 搜图成功，增加使用次数（仅群聊且有限制）
        if isinstance(event, GroupMessageEvent):
            group_id = str(event.group_id)
            user_id = str(event.user_id)
            if group_id in RATE_LIMIT_CONFIG:
                increment_usage(group_id, user_id)
                # 获取剩余次数
                _, used, limit = check_rate_limit(group_id, user_id)
                msg += f"\n\n💡 剩余次数: {limit - used}/{limit}"

        await search_pic.send(msg)
        # 先下载图片再发送，避免NapCat下载外部URL失败
        img_seg = await download_image_as_base64(img_url)
        if img_seg:
            await search_pic.finish(img_seg)
        else:
            await search_pic.finish(f"❌ 图片加载失败\n🔗 原图: {img_url}")

    except FinishedException:
        raise
    except requests.Timeout as e:
        logger.error(f"[搜图] 请求超时: {e}")
        await search_pic.finish("❌ 请求超时，请稍后重试")
    except requests.RequestException as e:
        logger.error(f"[搜图] 请求错误: {e}")
        await search_pic.finish(f"❌ 网络请求失败: {str(e)[:100]}")
    except Exception as e:
        logger.error(f"[搜图] 搜索图片失败: {e}")
        import traceback
        traceback.print_exc()
        await search_pic.finish(f"❌ 搜索图片时出错: {str(e)[:100]}")


# 多图模式
multi_pic = on_command("来点图", aliases={"多来点", "美图x3"}, priority=5)


@multi_pic.handle()
async def handle_multi_pic(event: MessageEvent, args: Message = CommandArg()):
    """获取多张随机图片（最多5张）"""
    # 解析参数：数量和API源
    arg_text = args.extract_plain_text().strip()
    parts = arg_text.split()

    num = 3  # 默认3张
    api_source = DEFAULT_API

    if not parts:
        pass  # 使用默认值
    elif len(parts) == 1:
        # 只有一个参数
        if parts[0].isdigit():
            num = min(int(parts[0]), 5)
        elif parts[0].lower() in SUPPORTED_APIS:
            api_source = parts[0].lower()
    elif len(parts) >= 2:
        # 两个参数：数量 + API源
        if parts[0].isdigit():
            num = min(int(parts[0]), 5)
        if parts[1].lower() in SUPPORTED_APIS:
            api_source = parts[1].lower()

    await multi_pic.send(f"📦 正在获取 {num} 张图片...")

    success_count = 0

    try:
        if api_source == "safebooru":
            # 使用 Safebooru API
            random_page = random.randint(0, 200)
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "limit": 20,
                "tags": "rating:safe score:>=10",
                "pid": random_page
            }

            response = await asyncio.to_thread(
                requests.get,
                SAFEBOORU_API,
                params=params,
                timeout=20
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    selected_posts = random.sample(data, min(num, len(data)))

                    for post in selected_posts:
                        try:
                            img_url = post.get('file_url') or post.get('image')
                            if img_url:
                                img_seg = await download_image_as_base64(img_url)
                                if img_seg:
                                    await multi_pic.send(img_seg)
                                    success_count += 1
                        except Exception as e:
                            logger.error(f"[来点图] 发送图片失败: {e}")
                            continue

        elif api_source == "lolicon":
            # 使用 Lolicon API - 一次请求多张
            payload = {
                "r18": 0,
                "num": num,
                "size": ["original", "regular"]
            }

            response = await asyncio.to_thread(
                requests.post,
                LOLICON_API,
                json=payload,
                timeout=20
            )

            if response.status_code == 200:
                result = response.json()
                data = result.get('data', [])

                for post in data[:num]:
                    try:
                        urls = post.get('urls', {})
                        img_url = urls.get('original') or urls.get('regular')
                        if img_url:
                            img_seg = await download_image_as_base64(img_url)
                            if img_seg:
                                await multi_pic.send(img_seg)
                                success_count += 1
                    except Exception as e:
                        logger.error(f"[来点图] 发送图片失败: {e}")
                        continue

        elif api_source == "danbooru":
            # 使用 Danbooru API - 使用随机页码
            random_page = random.randint(1, 1000)
            params = {
                "tags": "rating:safe",
                "limit": 20,
                "page": random_page
            }

            response = await asyncio.to_thread(
                requests.get,
                DANBOORU_API,
                params=params,
                timeout=20
            )

            if response.status_code == 200:
                data = response.json()
                # 从获取的20个结果中随机选择需要的数量
                selected_posts = random.sample(data, min(num, len(data))) if data else []

                for post in selected_posts:
                    try:
                        img_url = post.get('file_url') or post.get('large_file_url')
                        if img_url:
                            img_seg = await download_image_as_base64(img_url)
                            if img_seg:
                                await multi_pic.send(img_seg)
                                success_count += 1
                    except Exception as e:
                        logger.error(f"[来点图] 发送图片失败: {e}")
                        continue

        else:
            # 使用 LoliAPI
            for i in range(num):
                try:
                    response = await asyncio.to_thread(
                        requests.get,
                        LOLI_API,
                        timeout=20,
                        allow_redirects=True
                    )
                    if response.status_code == 200:
                        img_url = response.url
                        if img_url:
                            img_seg = await download_image_as_base64(str(img_url))
                            if img_seg:
                                await multi_pic.send(img_seg)
                                success_count += 1
                except Exception as e:
                    logger.error(f"[来点图] 发送第{i+1}张图片失败: {e}")
                    continue

    except Exception as e:
        logger.error(f"[来点图] 获取多图失败: {e}")

    if success_count > 0:
        await multi_pic.finish(f"✅ 成功发送 {success_count}/{num} 张图片")
    else:
        await multi_pic.finish("❌ 所有图片获取失败")
