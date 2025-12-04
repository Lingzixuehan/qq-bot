"""
二次元美图插件
使用多个API源获取二次元图片
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message, MessageSegment
from nonebot.params import CommandArg
import httpx
import random
import json


# 随机美图
random_pic = on_command("美图", aliases={"来张图", "随机图片", "二次元"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片 - 使用多个API源"""
    # API源列表
    apis = [
        {
            "name": "搏天API",
            "url": "https://api.btstu.cn/sjbz/api.php",
            "params": {"lx": "dongman", "format": "json"}
        },
        {
            "name": "保罗API",
            "url": "https://api.paugram.com/wallpaper/",
            "params": {"source": "pixiv"}
        },
        {
            "name": "Dmoe API",
            "url": "https://www.dmoe.cc/random.php",
            "params": {"return": "json"}
        }
    ]

    # 尝试每个API
    for api in apis:
        try:
            print(f"尝试使用 {api['name']}...")

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(api["url"], params=api.get("params", {}))

                if response.status_code != 200:
                    print(f"{api['name']} 返回状态码: {response.status_code}")
                    continue

                # 根据不同API处理响应
                if api["name"] == "搏天API":
                    try:
                        data = response.json()
                        img_url = data.get("imgurl")
                        if img_url:
                            await random_pic.send("🎨 随机二次元美图")
                            await random_pic.finish(MessageSegment.image(img_url))
                            return
                    except:
                        # 如果JSON解析失败，可能直接返回了图片
                        pass

                elif api["name"] == "保罗API":
                    try:
                        data = response.json()
                        img_url = data.get("url")
                        if img_url:
                            await random_pic.send("🎨 随机二次元美图")
                            await random_pic.finish(MessageSegment.image(img_url))
                            return
                    except:
                        pass

                elif api["name"] == "Dmoe API":
                    try:
                        data = response.json()
                        img_url = data.get("imgurl")
                        if img_url:
                            await random_pic.send("🎨 随机二次元美图")
                            await random_pic.finish(MessageSegment.image(img_url))
                            return
                    except:
                        pass

        except Exception as e:
            print(f"{api['name']} 失败: {e}")
            continue

    # 所有API都失败
    await random_pic.finish("❌ 所有图片源都无法访问，请稍后重试")


# 关键词搜索图片（注：由于API限制，实际返回随机图片）
search_pic = on_command("搜图", aliases={"找图", "图片搜索"}, priority=5)


@search_pic.handle()
async def handle_search_pic(event: MessageEvent, args: Message = CommandArg()):
    """搜索二次元图片（使用多个API源）"""
    keyword = args.extract_plain_text().strip()

    if not keyword:
        await search_pic.finish(
            "用法：/搜图 <关键词>\n\n"
            "示例：/搜图 二次元\n\n"
            "💡 由于API限制，将返回随机二次元图片"
        )
        return

    # 使用与随机美图相同的API列表
    apis = [
        {
            "name": "搏天API",
            "url": "https://api.btstu.cn/sjbz/api.php",
            "params": {"lx": "dongman", "format": "json"}
        },
        {
            "name": "保罗API",
            "url": "https://api.paugram.com/wallpaper/",
            "params": {"source": "pixiv"}
        },
        {
            "name": "Dmoe API",
            "url": "https://www.dmoe.cc/random.php",
            "params": {"return": "json"}
        }
    ]

    # 尝试每个API
    for api in apis:
        try:
            print(f"尝试使用 {api['name']}...")

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(api["url"], params=api.get("params", {}))

                if response.status_code != 200:
                    print(f"{api['name']} 返回状态码: {response.status_code}")
                    continue

                # 根据不同API处理响应
                if api["name"] == "搏天API":
                    try:
                        data = response.json()
                        img_url = data.get("imgurl")
                        if img_url:
                            await search_pic.send(f"🔍 搜索: {keyword}\n🎨 随机二次元美图")
                            await search_pic.finish(MessageSegment.image(img_url))
                            return
                    except:
                        pass

                elif api["name"] == "保罗API":
                    try:
                        data = response.json()
                        img_url = data.get("url")
                        if img_url:
                            await search_pic.send(f"🔍 搜索: {keyword}\n🎨 随机二次元美图")
                            await search_pic.finish(MessageSegment.image(img_url))
                            return
                    except:
                        pass

                elif api["name"] == "Dmoe API":
                    try:
                        data = response.json()
                        img_url = data.get("imgurl")
                        if img_url:
                            await search_pic.send(f"🔍 搜索: {keyword}\n🎨 随机二次元美图")
                            await search_pic.finish(MessageSegment.image(img_url))
                            return
                    except:
                        pass

        except Exception as e:
            print(f"{api['name']} 失败: {e}")
            continue

    # 所有API都失败
    await search_pic.finish("❌ 所有图片源都无法访问，请稍后重试")


# 多图模式
multi_pic = on_command("来点图", aliases={"多来点", "美图x3"}, priority=5)


@multi_pic.handle()
async def handle_multi_pic(event: MessageEvent, args: Message = CommandArg()):
    """获取多张随机图片（最多3张）"""
    # 解析数量
    arg_text = args.extract_plain_text().strip()
    num = 3  # 默认3张

    if arg_text.isdigit():
        num = min(int(arg_text), 3)  # 最多3张，避免请求过多

    # API列表
    apis = [
        {
            "name": "搏天API",
            "url": "https://api.btstu.cn/sjbz/api.php",
            "params": {"lx": "dongman", "format": "json"}
        },
        {
            "name": "保罗API",
            "url": "https://api.paugram.com/wallpaper/",
            "params": {"source": "pixiv"}
        },
        {
            "name": "Dmoe API",
            "url": "https://www.dmoe.cc/random.php",
            "params": {"return": "json"}
        }
    ]

    await multi_pic.send(f"📦 正在获取 {num} 张图片...")

    success_count = 0
    for i in range(num):
        # 对每张图片尝试所有API
        img_sent = False
        for api in apis:
            if img_sent:
                break
            try:
                async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                    response = await client.get(api["url"], params=api.get("params", {}))

                    if response.status_code != 200:
                        continue

                    # 根据不同API处理响应
                    img_url = None
                    if api["name"] == "搏天API":
                        try:
                            data = response.json()
                            img_url = data.get("imgurl")
                        except:
                            pass
                    elif api["name"] == "保罗API":
                        try:
                            data = response.json()
                            img_url = data.get("url")
                        except:
                            pass
                    elif api["name"] == "Dmoe API":
                        try:
                            data = response.json()
                            img_url = data.get("imgurl")
                        except:
                            pass

                    if img_url:
                        try:
                            await multi_pic.send(f"[{i+1}/{num}] 🎨 二次元美图")
                            await multi_pic.send(MessageSegment.image(img_url))
                            success_count += 1
                            img_sent = True
                        except Exception as e:
                            print(f"发送第{i+1}张图片失败: {e}")

            except Exception as e:
                print(f"{api['name']} 第{i+1}张图片失败: {e}")
                continue

    if success_count > 0:
        await multi_pic.finish(f"✅ 成功发送 {success_count}/{num} 张图片")
    else:
        await multi_pic.finish("❌ 所有图片发送失败，请稍后重试")
