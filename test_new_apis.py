#!/usr/bin/env python3
import requests
import random

print("测试新的二次元图片API")
print("="*60)

# 1. 测试 Safebooru API
print("\n1️⃣ 测试 Safebooru API...")
print("-"*60)
try:
    # Safebooru 使用Gelbooru的API格式
    safebooru_url = "https://safebooru.org/index.php"
    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": 1,
        "limit": 10,
        "tags": "rating:safe score:>=10",  # 默认过滤
        "pid": random.randint(0, 100)  # 随机页码
    }

    print(f"请求URL: {safebooru_url}")
    print(f"参数: {params}")

    r = requests.get(safebooru_url, params=params, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        print(f"✅ 成功获取数据")

        if isinstance(data, list):
            print(f"返回 {len(data)} 个结果")
            if data:
                post = data[0]
                print(f"\n示例图片:")
                print(f"  ID: {post.get('id')}")
                print(f"  评分: {post.get('score')}")
                print(f"  标签: {post.get('tags', '')[:100]}...")
                # Safebooru的图片URL字段
                img_url = post.get('file_url') or post.get('image')
                print(f"  图片URL: {img_url[:80] if img_url else 'N/A'}...")
        else:
            print(f"数据格式: {type(data)}")
            print(f"数据内容: {str(data)[:200]}")
    else:
        print(f"❌ 失败: {r.text[:200]}")

except Exception as e:
    print(f"❌ 错误: {e}")

# 2. 测试 Lolicon API
print("\n\n2️⃣ 测试 Lolicon API...")
print("-"*60)
try:
    lolicon_url = "https://api.lolicon.app/setu/v2"
    params = {
        "r18": 0,  # 不要R18
        "num": 1,  # 返回1张
        "size": ["original", "regular"]  # 图片尺寸
    }

    print(f"请求URL: {lolicon_url}")
    print(f"参数: {params}")

    r = requests.post(lolicon_url, json=params, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        print(f"✅ 成功获取数据")
        print(f"错误信息: {data.get('error')}")

        setu_data = data.get('data', [])
        print(f"返回 {len(setu_data)} 个结果")

        if setu_data:
            post = setu_data[0]
            print(f"\n示例图片:")
            print(f"  PID: {post.get('pid')}")
            print(f"  标题: {post.get('title')}")
            print(f"  作者: {post.get('author')}")
            print(f"  标签: {post.get('tags', [])[:5]}")
            urls = post.get('urls', {})
            print(f"  原图URL: {urls.get('original', 'N/A')[:80]}...")
    else:
        print(f"❌ 失败: {r.text[:200]}")

except Exception as e:
    print(f"❌ 错误: {e}")

# 3. 测试 Safebooru 带关键词搜索
print("\n\n3️⃣ 测试 Safebooru 带关键词搜索...")
print("-"*60)
try:
    params = {
        "page": "dapi",
        "s": "post",
        "q": "index",
        "json": 1,
        "limit": 5,
        "tags": "touhou rating:safe score:>=10",  # 搜索东方Project
        "pid": 0
    }

    print(f"搜索标签: touhou")

    r = requests.get(safebooru_url, params=params, timeout=10)
    print(f"状态码: {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        if isinstance(data, list) and data:
            print(f"✅ 找到 {len(data)} 个结果")
            print(f"第一个结果ID: {data[0].get('id')}")
        else:
            print(f"⚠️  未找到结果或格式异常")
    else:
        print(f"❌ 失败")

except Exception as e:
    print(f"❌ 错误: {e}")

print("\n" + "="*60)
print("测试完成！")
