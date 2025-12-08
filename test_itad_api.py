"""
ITAD API 诊断工具
用于测试ITAD API的配置和返回数据
"""
import asyncio
import httpx
from pathlib import Path

# 读取.env文件获取API Key
def load_itad_key():
    """从.env文件读取ITAD API Key"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("ITAD_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return key
    return ""

ITAD_API_KEY = load_itad_key()
ITAD_BASE_URL = "https://api.isthereanydeal.com"

async def test_itad_api():
    """测试ITAD API"""

    print("=" * 60)
    print("ITAD API 诊断工具")
    print("=" * 60)

    # 1. 检查API Key
    print("\n1. 检查ITAD API Key配置...")
    if not ITAD_API_KEY:
        print("❌ ITAD_API_KEY 未配置！")
        print("   请在.env文件中添加：ITAD_API_KEY=\"your_api_key\"")
        print("   申请地址：https://isthereanydeal.com/apps/")
        return
    else:
        print(f"✅ ITAD_API_KEY 已配置: {ITAD_API_KEY[:8]}...")

    # 2. 测试游戏（博德之门3）
    test_appid = 1086940  # 博德之门3
    print(f"\n2. 测试游戏查询 (AppID: {test_appid} - 博德之门3)...")

    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Lookup game ID
        print("\n   Step 1: 查询游戏ID...")
        lookup_url = f"{ITAD_BASE_URL}/games/lookup/v1"
        lookup_params = {
            "key": ITAD_API_KEY,
            "shop": "steam",
            "game_id": f"app/{test_appid}"
        }

        try:
            response = await client.get(lookup_url, params=lookup_params)
            print(f"   状态码: {response.status_code}")

            if response.status_code != 200:
                print(f"   ❌ API调用失败: {response.text}")
                return

            lookup_data = response.json()
            print(f"   返回数据: {lookup_data}")

            if not lookup_data or "game" not in lookup_data:
                print("   ❌ 未找到游戏信息")
                return

            gid = lookup_data["game"]["id"]
            print(f"   ✅ 游戏ID: {gid}")

        except Exception as e:
            print(f"   ❌ 异常: {e}")
            return

        # Step 2: Get prices and historical low
        print("\n   Step 2: 获取价格和史低信息...")
        prices_url = f"{ITAD_BASE_URL}/games/prices/v3"
        prices_params = {
            "key": ITAD_API_KEY,
            "country": "CN",
            "shops": 61  # Steam shop ID
        }

        try:
            response = await client.post(
                prices_url,
                params=prices_params,
                json=[gid],
                headers={"Content-Type": "application/json"}
            )
            print(f"   状态码: {response.status_code}")

            if response.status_code != 200:
                print(f"   ❌ API调用失败: {response.text}")
                return

            prices_data = response.json()
            print(f"   返回数据长度: {len(prices_data)}")

            if not prices_data or len(prices_data) == 0:
                print("   ❌ 未返回价格数据")
                return

            game_data = prices_data[0]
            print(f"\n   完整返回数据：")
            print(f"   {game_data}")

            # 提取史低信息
            print(f"\n   Step 3: 解析史低信息...")
            history_low = game_data.get("historyLow", {})
            print(f"   historyLow 数据: {history_low}")

            # 检查各个时间段
            for period in ["m3", "y1", "all"]:
                if period in history_low:
                    print(f"   - {period}: {history_low[period]}")

            # 尝试提取史低价格
            lowest_price = None
            lowest_currency = None
            lowest_timestamp = None

            # 方法1：按优先级提取
            for period in ["m3", "y1", "all"]:
                if period in history_low and history_low[period]:
                    low_data = history_low[period]
                    if "amount" in low_data:
                        lowest_price = low_data["amount"]
                        lowest_currency = low_data.get("currency", "CNY")
                        lowest_timestamp = low_data.get("timestamp")
                        print(f"\n   ✅ 找到史低价格 ({period}):")
                        print(f"      价格: {lowest_currency} {lowest_price}")
                        print(f"      时间戳: {lowest_timestamp}")
                        break

            if lowest_price is None:
                print("\n   ❌ 未找到史低价格")

            # 提取当前价格
            print(f"\n   Step 4: 解析当前价格...")
            deals = game_data.get("deals", [])
            print(f"   deals 数量: {len(deals)}")

            for deal in deals:
                shop = deal.get("shop", {})
                if shop.get("id") == 61:  # Steam
                    price_data = deal.get("price", {})
                    current_price = price_data.get("amount")
                    current_currency = price_data.get("currency")
                    print(f"   ✅ 当前Steam价格: {current_currency} {current_price}")
                    break

        except Exception as e:
            print(f"   ❌ 异常: {e}")
            import traceback
            traceback.print_exc()
            return

    print("\n" + "=" * 60)
    print("诊断完成！")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_itad_api())
