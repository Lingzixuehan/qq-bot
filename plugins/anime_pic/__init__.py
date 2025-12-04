"""
二次元美图插件
使用Lolicon API获取二次元图片
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
import httpx
import random


# 随机美图
random_pic = on_command("美图", aliases={"来张图", "随机图片", "二次元"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片"""
    try:
        # 调用Lolicon API
        url = "https://api.lolicon.app/setu/v2"
        params = {
            "r18": 0,  # 0=全年龄, 1=R18, 2=混合
            "num": 1,  # 返回数量
            "size": ["regular"]  # 图片尺寸
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                await random_pic.finish("❌ 获取图片失败，请稍后重试")
                return

            data = response.json()

            if data.get("error"):
                await random_pic.finish(f"❌ API错误: {data.get('error')}")
                return

            pics = data.get("data", [])
            if not pics:
                await random_pic.finish("❌ 没有找到图片")
                return

            pic = pics[0]

            # 提取图片信息
            title = pic.get("title", "未知")
            author = pic.get("author", "未知")
            pid = pic.get("pid", "")
            tags = pic.get("tags", [])
            urls = pic.get("urls", {})
            img_url = urls.get("regular") or urls.get("original")

            if not img_url:
                await random_pic.finish("❌ 图片链接获取失败")
                return

            # 构建消息
            msg = f"🎨 {title}\n"
            msg += f"👤 作者: {author}\n"
            msg += f"🏷️ 标签: {', '.join(tags[:5])}\n"
            msg += f"🆔 PID: {pid}"

            # 发送图片
            await random_pic.send(msg)
            await random_pic.finish(MessageSegment.image(img_url))

    except httpx.TimeoutException:
        await random_pic.finish("❌ 请求超时，请稍后重试")
    except Exception as e:
        print(f"获取随机图片失败: {e}")
        await random_pic.finish("❌ 获取图片时出错，请稍后重试")


# 关键词搜索图片
search_pic = on_command("搜图", aliases={"找图", "图片搜索"}, priority=5)


@search_pic.handle()
async def handle_search_pic(event: MessageEvent, args: Message = CommandArg()):
    """根据关键词搜索二次元图片"""
    keyword = args.extract_plain_text().strip()

    if not keyword:
        await search_pic.finish(
            "用法：/搜图 <关键词>\n\n"
            "示例：\n"
            "/搜图 白毛\n"
            "/搜图 猫娘\n"
            "/搜图 萝莉\n\n"
            "💡 支持中文和英文标签"
        )
        return

    try:
        # 调用Lolicon API
        url = "https://api.lolicon.app/setu/v2"
        params = {
            "r18": 0,
            "num": 1,
            "tag": keyword,  # 关键词搜索
            "size": ["regular"]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                await search_pic.finish("❌ 获取图片失败，请稍后重试")
                return

            data = response.json()

            if data.get("error"):
                await search_pic.finish(f"❌ API错误: {data.get('error')}")
                return

            pics = data.get("data", [])
            if not pics:
                await search_pic.finish(f"❌ 没有找到包含 '{keyword}' 标签的图片，试试其他关键词吧")
                return

            pic = pics[0]

            # 提取图片信息
            title = pic.get("title", "未知")
            author = pic.get("author", "未知")
            pid = pic.get("pid", "")
            tags = pic.get("tags", [])
            urls = pic.get("urls", {})
            img_url = urls.get("regular") or urls.get("original")

            if not img_url:
                await search_pic.finish("❌ 图片链接获取失败")
                return

            # 构建消息
            msg = f"🔍 搜索: {keyword}\n\n"
            msg += f"🎨 {title}\n"
            msg += f"👤 作者: {author}\n"
            msg += f"🏷️ 标签: {', '.join(tags[:5])}\n"
            msg += f"🆔 PID: {pid}"

            # 发送图片
            await search_pic.send(msg)
            await search_pic.finish(MessageSegment.image(img_url))

    except httpx.TimeoutException:
        await search_pic.finish("❌ 请求超时，请稍后重试")
    except Exception as e:
        print(f"搜索图片失败: {e}")
        await search_pic.finish("❌ 搜索图片时出错，请稍后重试")


# 多图模式
multi_pic = on_command("来点图", aliases={"多来点", "美图x3"}, priority=5)


@multi_pic.handle()
async def handle_multi_pic(event: MessageEvent, args: Message = CommandArg()):
    """获取多张随机图片（最多3张）"""
    # 解析数量
    arg_text = args.extract_plain_text().strip()
    num = 3  # 默认3张

    if arg_text.isdigit():
        num = min(int(arg_text), 5)  # 最多5张

    try:
        url = "https://api.lolicon.app/setu/v2"
        params = {
            "r18": 0,
            "num": num,
            "size": ["regular"]
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                await multi_pic.finish("❌ 获取图片失败，请稍后重试")
                return

            data = response.json()

            if data.get("error"):
                await multi_pic.finish(f"❌ API错误: {data.get('error')}")
                return

            pics = data.get("data", [])
            if not pics:
                await multi_pic.finish("❌ 没有找到图片")
                return

            # 发送多张图片
            await multi_pic.send(f"📦 为你找到 {len(pics)} 张图片~")

            for i, pic in enumerate(pics, 1):
                title = pic.get("title", "未知")
                author = pic.get("author", "未知")
                urls = pic.get("urls", {})
                img_url = urls.get("regular") or urls.get("original")

                if img_url:
                    msg = f"[{i}/{len(pics)}] {title} - {author}"
                    await multi_pic.send(msg)
                    await multi_pic.send(MessageSegment.image(img_url))

            await multi_pic.finish()

    except httpx.TimeoutException:
        await multi_pic.finish("❌ 请求超时，请稍后重试")
    except Exception as e:
        print(f"获取多图失败: {e}")
        await multi_pic.finish("❌ 获取图片时出错，请稍后重试")
