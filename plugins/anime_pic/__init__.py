"""
二次元美图插件
使用 Pybooru 包访问 Danbooru API 获取随机二次元图片，支持标签搜索
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import MessageEvent, MessageSegment
from nonebot.params import CommandArg
from nonebot.adapters.onebot.v11 import Message
from nonebot.exception import FinishedException
from pybooru import Danbooru
import asyncio
import random


# 初始化 Danbooru 客户端（无需认证即可读取）
client = Danbooru('danbooru')


# 随机美图
random_pic = on_command("美图", aliases={"二次元", "来张图"}, priority=5)


@random_pic.handle()
async def handle_random_pic(event: MessageEvent):
    """获取随机二次元图片"""
    try:
        # 在线程池中执行同步的 pybooru 调用
        posts = await asyncio.to_thread(
            client.post_list,
            tags='rating:safe order:random',  # 安全内容 + 随机排序
            limit=1
        )

        if not posts or len(posts) == 0:
            await random_pic.finish("❌ 没有找到图片")

        # 获取第一张图片
        post = posts[0]
        img_url = post.get('file_url')

        if not img_url:
            await random_pic.finish("❌ 图片链接无效")

        # 提取信息
        tags = post.get('tag_string', '').split()[:5]  # 前5个标签
        rating = post.get('rating', '')
        post_id = post.get('id', '')
        score = post.get('score', 0)

        # 评级说明
        rating_map = {'s': '安全', 'q': '问题', 'e': '限制'}
        rating_text = rating_map.get(rating, '未知')

        # 发送图片信息
        msg = f"🎨 Danbooru 随机图片\n"
        msg += f"🆔 ID: {post_id}\n"
        msg += f"⭐ 评分: {score}\n"
        msg += f"🔰 评级: {rating_text}\n"
        if tags:
            msg += f"🏷️ 标签: {', '.join(tags[:3])}"

        await random_pic.send(msg)
        await random_pic.finish(MessageSegment.image(img_url))

    except FinishedException:
        raise
    except Exception as e:
        print(f"获取图片失败: {e}")
        import traceback
        traceback.print_exc()
        await random_pic.finish("❌ 获取图片时出错，请稍后重试")


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
            "/搜图 maid\n"
            "/搜图 original\n\n"
            "💡 可以使用多个标签（空格分隔）\n"
            "💡 使用英文标签，用下划线连接多个单词\n"
            "💡 常用标签：maid, cat_girl, 1girl, original 等"
        )
        return

    try:
        # 处理标签（用空格分隔）
        search_tags = f"{keyword} rating:safe order:random"

        # 在线程池中执行
        posts = await asyncio.to_thread(
            client.post_list,
            tags=search_tags,
            limit=1
        )

        if not posts or len(posts) == 0:
            await search_pic.finish(
                f"❌ 没有找到包含 '{keyword}' 的图片\n\n"
                "💡 试试其他标签或使用英文标签"
            )

        # 获取图片
        post = posts[0]
        img_url = post.get('file_url')

        if not img_url:
            await search_pic.finish("❌ 图片链接无效")

        # 提取信息
        all_tags = post.get('tag_string', '').split()
        rating = post.get('rating', '')
        post_id = post.get('id', '')
        score = post.get('score', 0)

        rating_map = {'s': '安全', 'q': '问题', 'e': '限制'}
        rating_text = rating_map.get(rating, '未知')

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
    except Exception as e:
        print(f"搜索图片失败: {e}")
        import traceback
        traceback.print_exc()
        await search_pic.finish("❌ 搜索图片时出错，请稍后重试")


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

    success_count = 0

    try:
        # 在线程池中执行
        posts = await asyncio.to_thread(
            client.post_list,
            tags='rating:safe order:random',
            limit=num
        )

        if posts:
            for i, post in enumerate(posts[:num], 1):
                try:
                    img_url = post.get('file_url')
                    if img_url:
                        post_id = post.get('id', '')
                        score = post.get('score', 0)
                        await multi_pic.send(f"[{i}/{num}] 🎨 ID: {post_id} | ⭐ {score}")
                        await multi_pic.send(MessageSegment.image(img_url))
                        success_count += 1
                except Exception as e:
                    print(f"发送第{i}张图片失败: {e}")
                    continue

    except Exception as e:
        print(f"获取多图失败: {e}")
        import traceback
        traceback.print_exc()

    if success_count > 0:
        await multi_pic.finish(f"✅ 成功发送 {success_count}/{num} 张图片")
    else:
        await multi_pic.finish("❌ 所有图片获取失败，请稍后重试")
