#!/usr/bin/env python3
import requests
import httpx
import asyncio

print("测试 requests vs httpx 对 Danbooru API 的访问")
print("="*60)

url = "https://danbooru.donmai.us/posts.json"
params = {"tags": "rating:safe", "limit": 1, "page": 100}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json'
}

print("\n1️⃣ 测试 requests 库...")
try:
    r = requests.get(url, params=params, headers=headers, timeout=10)
    print(f"✅ requests: 状态码 {r.status_code}")
except Exception as e:
    print(f"❌ requests: 失败 - {e}")

print("\n2️⃣ 测试 httpx 同步模式...")
try:
    with httpx.Client(timeout=10, follow_redirects=True, headers=headers) as client:
        r = client.get(url, params=params)
        print(f"✅ httpx (sync): 状态码 {r.status_code}")
except Exception as e:
    print(f"❌ httpx (sync): 失败 - {e}")

print("\n3️⃣ 测试 httpx 异步模式（Bot使用的方式）...")
async def test_httpx_async():
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, headers=headers) as client:
            r = await client.get(url, params=params)
            print(f"✅ httpx (async): 状态码 {r.status_code}")
    except Exception as e:
        print(f"❌ httpx (async): 失败 - {e}")

asyncio.run(test_httpx_async())

print("\n4️⃣ 测试 httpx 禁用 HTTP/2...")
async def test_httpx_http1_only():
    try:
        async with httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers=headers,
            http2=False  # 禁用 HTTP/2
        ) as client:
            r = await client.get(url, params=params)
            print(f"✅ httpx (HTTP/1.1 only): 状态码 {r.status_code}")
    except Exception as e:
        print(f"❌ httpx (HTTP/1.1 only): 失败 - {e}")

asyncio.run(test_httpx_http1_only())

print("\n" + "="*60)
print("测试完成！")
