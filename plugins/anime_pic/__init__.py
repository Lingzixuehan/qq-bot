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
            "size": ["regular"],  # 图片尺寸，使用regular更稳定
            "proxy": "i.pixiv.re"  # 使用反代服务器
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                print(f"API返回状态码: {response.status_code}")
                await random_pic.finish(f"❌ 获取图片失败，API返回状态码: {response.status_code}")
                return

            data = response.json()
            print(f"API响应: {data}")  # 调试日志

            if data.get("error"):
                error_msg = data.get("error")
                print(f"API错误: {error_msg}")
                await random_pic.finish(f"❌ API错误: {error_msg}")
                return

            pics = data.get("data", [])
            if not pics:
                await random_pic.finish("❌ 没有找到图片，请稍后重试")
                return

            pic = pics[0]

            # 提取图片信息
            title = pic.get("title", "未知")
            author = pic.get("author", "未知")
            pid = pic.get("pid", "")
            tags = pic.get("tags", [])
            urls = pic.get("urls", {})

            # 优先使用反代链接
            img_url = urls.get("regular")

            if not img_url:
                print("未找到图片URL")
                await random_pic.finish("❌ 图片链接获取失败")
                return

            print(f"图片URL: {img_url}")  # 调试日志

            # 构建消息
            msg = f"🎨 {title}\n"
            msg += f"👤 作者: {author}\n"
            if tags:
                msg += f"🏷️ 标签: {', '.join(tags[:5])}\n"
            msg += f"🆔 PID: {pid}\n"
            msg += f"\n💡 图片加载可能需要一些时间..."

            # 发送消息和图片
            try:
                await random_pic.send(msg)
                # 给图片URL一些时间加载
                await random_pic.finish(MessageSegment.image(img_url))
            except Exception as img_error:
                print(f"发送图片失败: {img_error}")
                await random_pic.finish(f"❌ 图片发送失败，可能网络问题\n\n你可以直接访问: https://pixiv.net/artworks/{pid}")

    except httpx.TimeoutException:
        print("请求超时")
        await random_pic.finish("❌ 请求超时，API可能响应较慢，请稍后重试")
    except Exception as e:
        print(f"获取随机图片失败: {e}")
        import traceback
        traceback.print_exc()
        await random_pic.finish(f"❌ 获取图片时出错: {str(e)}")


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
            "size": ["regular"],
            "proxy": "i.pixiv.re"
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)

            if response.status_code != 200:
                print(f"API返回状态码: {response.status_code}")
                await search_pic.finish(f"❌ 获取图片失败，API返回状态码: {response.status_code}")
                return

            data = response.json()
            print(f"搜索API响应: {data}")

            if data.get("error"):
                error_msg = data.get("error")
                print(f"API错误: {error_msg}")
                await search_pic.finish(f"❌ API错误: {error_msg}")
                return

            pics = data.get("data", [])
            if not pics:
                await search_pic.finish(f"❌ 没有找到包含 '{keyword}' 标签的图片\n\n💡 试试其他关键词：白毛、猫娘、原神等")
                return

            pic = pics[0]

            # 提取图片信息
            title = pic.get("title", "未知")
            author = pic.get("author", "未知")
            pid = pic.get("pid", "")
            tags = pic.get("tags", [])
            urls = pic.get("urls", {})
            img_url = urls.get("regular")

            if not img_url:
                print("未找到图片URL")
                await search_pic.finish("❌ 图片链接获取失败")
                return

            print(f"图片URL: {img_url}")

            # 构建消息
            msg = f"🔍 搜索: {keyword}\n\n"
            msg += f"🎨 {title}\n"
            msg += f"👤 作者: {author}\n"
            if tags:
                msg += f"🏷️ 标签: {', '.join(tags[:5])}\n"
            msg += f"🆔 PID: {pid}\n"
            msg += f"\n💡 图片加载可能需要一些时间..."

            # 发送图片
            try:
                await search_pic.send(msg)
                await search_pic.finish(MessageSegment.image(img_url))
            except Exception as img_error:
                print(f"发送图片失败: {img_error}")
                await search_pic.finish(f"❌ 图片发送失败\n\n直接访问: https://pixiv.net/artworks/{pid}")

    except httpx.TimeoutException:
        print("请求超时")
        await search_pic.finish("❌ 请求超时，请稍后重试")
    except Exception as e:
        print(f"搜索图片失败: {e}")
        import traceback
        traceback.print_exc()
        await search_pic.finish(f"❌ 搜索图片时出错: {str(e)}")


# 多图模式
multi_pic = on_command("来点图", aliases={"多来点", "美图x3"}, priority=5)


@multi_pic.handle()
async def handle_multi_pic(event: MessageEvent, args: Message = CommandArg()):
    """获取多张随机图片（最多3张）"""
    # 解析数量
    arg_text = args.extract_plain_text().strip()
    num = 3  # 默认3张

    if arg_text.isdigit():
        num = min(int(arg_text), 3)  # 降低到最多3张，避免请求过多

    try:
        url = "https://api.lolicon.app/setu/v2"
        params = {
            "r18": 0,
            "num": num,
            "size": ["regular"],
            "proxy": "i.pixiv.re"
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
            await multi_pic.send(f"📦 为你找到 {len(pics)} 张图片，正在发送...")

            success_count = 0
            for i, pic in enumerate(pics, 1):
                try:
                    title = pic.get("title", "未知")
                    author = pic.get("author", "未知")
                    urls = pic.get("urls", {})
                    img_url = urls.get("regular")

                    if img_url:
                        msg = f"[{i}/{len(pics)}] {title} - {author}"
                        await multi_pic.send(msg)
                        await multi_pic.send(MessageSegment.image(img_url))
                        success_count += 1
                except Exception as e:
                    print(f"发送第{i}张图片失败: {e}")
                    continue

            if success_count > 0:
                await multi_pic.finish(f"✅ 成功发送 {success_count}/{len(pics)} 张图片")
            else:
                await multi_pic.finish("❌ 所有图片发送失败")

    except httpx.TimeoutException:
        await multi_pic.finish("❌ 请求超时，请稍后重试")
    except Exception as e:
        print(f"获取多图失败: {e}")
        import traceback
        traceback.print_exc()
        await multi_pic.finish(f"❌ 获取图片时出错: {str(e)}")
