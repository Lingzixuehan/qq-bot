#!/usr/bin/env python3
import requests
import random

print("测试Danbooru图片下载流程...")
print("="*60)

try:
    # 1. 获取帖子列表
    print("\n步骤1: 获取帖子列表（使用随机页码，避免order:random超时）...")
    api_url = "https://danbooru.donmai.us/posts.json"
    random_page = random.randint(1, 1000)
    params = {
        "tags": "rating:safe",
        "limit": 20,
        "page": random_page
    }
    print(f"使用随机页码: {random_page}")

    r = requests.get(api_url, params=params, timeout=15)
    print(f"API状态码: {r.status_code}")

    if r.status_code != 200:
        print(f"❌ API访问失败: {r.text[:200]}")
        exit(1)

    posts = r.json()
    print(f"✅ 成功获取 {len(posts)} 个帖子")

    # 2. 下载图片
    print("\n步骤2: 从结果中随机选择3张图片下载...")
    image_data_list = []
    count = 3

    # 随机选择3个帖子
    selected_posts = random.sample(posts, min(count, len(posts))) if posts else []
    print(f"随机选择了 {len(selected_posts)} 个帖子")

    for idx, post in enumerate(selected_posts, 1):
        print(f"\n--- 处理第 {idx} 张图片 ---")
        print(f"帖子ID: {post.get('id')}")
        print(f"评分: {post.get('score')}")
        print(f"标签: {post.get('tag_string', '')[:100]}...")

        try:
            download_url = None
            for key in ['file_url', 'large_file_url', 'medium_file_url']:
                if key in post and post[key]:
                    url_full = post[key]
                    if not url_full.startswith('http'):
                        url_full = f"https://danbooru.donmai.us{url_full}"
                    download_url = url_full
                    print(f"找到URL ({key}): {download_url[:80]}...")
                    break

            if not download_url:
                print("⚠️  未找到可用的图片URL，跳过")
                continue

            print(f"开始下载...")
            img_response = requests.get(download_url, timeout=30)
            print(f"下载状态码: {img_response.status_code}")

            if img_response.status_code == 200:
                image_data = img_response.content
                image_data_list.append(image_data)
                print(f"✅ 下载成功，大小: {len(image_data)} bytes ({len(image_data)/1024:.1f} KB)")
            else:
                print(f"❌ 下载失败: {img_response.status_code}")

        except Exception as e:
            print(f"❌ 下载出错: {e}")
            continue

    # 3. 总结
    print("\n" + "="*60)
    print(f"总结: 成功下载 {len(image_data_list)}/{count} 张图片")

    if image_data_list:
        print("✅ 下载流程正常！")
        for idx, data in enumerate(image_data_list, 1):
            print(f"  图片{idx}: {len(data)/1024:.1f} KB")
    else:
        print("❌ 没有成功下载任何图片")

except Exception as e:
    print(f"\n❌ 程序出错: {e}")
    import traceback
    traceback.print_exc()
