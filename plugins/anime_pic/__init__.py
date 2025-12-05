"""
二次元美图插件
使用 dmoe.cc API 获取随机二次元图片
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException
import httpx


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片"""
    try:
        api_url = "https://www.dmoe.cc/random.php"
        params = {"return": "json"}

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            response = await client.get(api_url, params=params)

            if response.status_code != 200:
                await random_pic.finish(f"❌ 获取图片失败，状态码: {response.status_code}")

            data = response.json()

            # 检查返回状态
            if data.get("code") != "200":
                await random_pic.finish(f"❌ API返回错误: {data.get('code')}")

            img_url = data.get("imgurl")
            width = data.get("width", "未知")
            height = data.get("height", "未知")

            if not img_url:
                await random_pic.finish("❌ 未获取到图片链接")

        # 发送图片信息和图片（在 try 块外，避免捕获 finish 的异常）
        msg = f"🎨 随机二次元美图\n📐 尺寸: {width}x{height}"
        await random_pic.send(msg)
        await random_pic.finish(MessageSegment.image(img_url))

    except FinishedException:
        # NoneBot2 的 finish() 异常，需要重新抛出让框架处理
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

    api_url = "https://www.dmoe.cc/random.php"
    params = {"return": "json"}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }

    success_count = 0

    for i in range(num):
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
                response = await client.get(api_url, params=params)

                if response.status_code == 200:
                    data = response.json()

                    if data.get("code") == "200":
                        img_url = data.get("imgurl")
                        if img_url:
                            await multi_pic.send(f"[{i+1}/{num}] 🎨")
                            await multi_pic.send(MessageSegment.image(img_url))
                            success_count += 1
        except Exception as e:
            print(f"获取第{i+1}张图片失败: {e}")
            continue

    if success_count > 0:
        await multi_pic.finish(f"✅ 成功发送 {success_count}/{num} 张图片")
    else:
        await multi_pic.finish("❌ 所有图片获取失败")
