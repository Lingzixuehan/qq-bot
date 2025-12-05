"""
二次元美图插件
使用 LoliAPI 获取随机二次元图片
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException
import httpx


# API 配置
LOLI_API = "https://www.loliapi.com/bg/"


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            # LoliAPI 默认会重定向到图片URL
            response = await client.get(LOLI_API)

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            # 获取最终的图片URL（经过重定向后）
            img_url = str(response.url)

            if not img_url:
                await random_pic.finish("❌ 图片链接无效")

        # 发送图片
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


# 标签搜索图片（LoliAPI不支持标签，返回随机图片）
search_pic = on_command("搜图", aliases={"找图", "图片搜索"}, priority=5)


@search_pic.handle()
async def handle_search_pic(event: MessageEvent, args: Message = CommandArg()):
    """根据标签搜索图片（LoliAPI不支持标签搜索，返回随机图片）"""
    keyword = args.extract_plain_text().strip()

    if not keyword:
        await search_pic.finish(
            "用法：/搜图 <关键词>\n\n"
            "💡 注意：当前使用LoliAPI，暂不支持标签搜索\n"
            "💡 将返回随机图片"
        )
        return

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            response = await client.get(LOLI_API)

            if response.status_code != 200:
                await search_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            img_url = str(response.url)

            if not img_url:
                await search_pic.finish("❌ 图片链接无效")

        # 发送信息
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
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    success_count = 0

    try:
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
