#!/usr/bin/env python3
import requests

# 先测试不带密钥
print("测试不带密钥...")
try:
    r = requests.get("https://danbooru.donmai.us/posts.json?tags=1girl&limit=1", timeout=10)
    print(f"状态码: {r.status_code}")
    if r.status_code == 200:
        print("✅ 可以访问，不用API密钥也能用")
        print(f"响应数据: {r.text[:200]}")
        data = r.json()
        if data:
            print(f"\n找到 {len(data)} 个结果")
            post = data[0]
            print(f"图片ID: {post.get('id')}")
            print(f"评分: {post.get('score')}")
            print(f"文件URL: {post.get('file_url', 'N/A')[:80]}")
    else:
        print(f"❌ 访问失败，状态码: {r.status_code}")
        print(f"响应: {r.text[:200]}")
except Exception as e:
    print(f"❌ 请求出错: {e}")

print("\n" + "="*50)

# 测试随机图片
print("\n测试随机图片（不带标签）...")
try:
    r = requests.get("https://danbooru.donmai.us/posts.json?limit=1&random=true", timeout=10)
    print(f"状态码: {r.status_code}")
    if r.status_code == 200:
        print("✅ 随机访问成功")
        data = r.json()
        if data:
            post = data[0]
            print(f"图片ID: {post.get('id')}")
            print(f"文件URL: {post.get('file_url', 'N/A')[:80]}")
except Exception as e:
    print(f"❌ 请求出错: {e}")
