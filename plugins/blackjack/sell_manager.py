"""
卖身管理系统
管理玩家卖身申请和处理
"""
import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from nonebot.log import logger

from .points_manager import points_manager

# 数据文件路径
DATA_DIR = Path("data/blackjack")
DATA_DIR.mkdir(parents=True, exist_ok=True)
SELL_FILE = DATA_DIR / "sell_requests.json"


class SellManager:
    """卖身管理器"""

    def __init__(self):
        """初始化卖身管理器"""
        self.requests: Dict[str, dict] = self._load_requests()
        # requests结构: {request_id: {group_id, seller_id, buyer_id, amount, title}}

    def _load_requests(self) -> Dict[str, dict]:
        """
        加载卖身申请数据

        Returns:
            {request_id: {...}}
        """
        if SELL_FILE.exists():
            try:
                with open(SELL_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载卖身申请数据失败: {e}")
                return {}
        return {}

    def _save_requests(self):
        """保存卖身申请数据"""
        try:
            with open(SELL_FILE, "w", encoding="utf-8") as f:
                json.dump(self.requests, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存卖身申请数据失败: {e}")

    def create_request(
        self, group_id: str, seller_id: str, buyer_id: str, amount: int, title: str
    ) -> Tuple[bool, str]:
        """
        创建卖身申请

        Args:
            group_id: 群号
            seller_id: 卖身者QQ号
            buyer_id: 买家QQ号
            amount: 金额
            title: 称号（如"小狗"、"奴隶"等）

        Returns:
            (是否成功, 消息)
        """
        # 检查卖身者积分是否低于-500
        seller_points = points_manager.get_points(group_id, seller_id)
        if seller_points >= -500:
            return False, f"❌ 只有积分低于-500的玩家才能卖身！\n当前积分：{seller_points}"

        # 检查买家积分是否足够
        buyer_points = points_manager.get_points(group_id, buyer_id)
        if buyer_points < amount:
            return False, f"❌ 买家积分不足！\n当前积分：{buyer_points}\n需要：{amount}"

        # 检查是否已有待处理的申请
        request_id = f"{group_id}_{seller_id}"
        if request_id in self.requests:
            return False, "❌ 你已有待处理的卖身申请！"

        # 创建申请
        self.requests[request_id] = {
            "group_id": group_id,
            "seller_id": seller_id,
            "buyer_id": buyer_id,
            "amount": amount,
            "title": title,
        }

        self._save_requests()

        return True, (
            f"✅ 卖身申请已发送！\n"
            f"━━━━━━━━━━━━━━\n"
            f"金额：{amount} 积分\n"
            f"称号：{title}\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 等待买家同意"
        )

    def approve_request(self, group_id: str, buyer_id: str, seller_id: str) -> Tuple[bool, str, Optional[dict]]:
        """
        同意卖身申请

        Args:
            group_id: 群号
            buyer_id: 买家QQ号
            seller_id: 卖身者QQ号

        Returns:
            (是否成功, 消息, 申请详情)
        """
        request_id = f"{group_id}_{seller_id}"

        # 检查申请是否存在
        if request_id not in self.requests:
            return False, "❌ 没有找到对应的卖身申请！", None

        request = self.requests[request_id]

        # 检查买家是否匹配
        if request["buyer_id"] != buyer_id:
            return False, "❌ 这不是向你发起的卖身申请！", None

        # 再次检查买家积分
        buyer_points = points_manager.get_points(group_id, buyer_id)
        if buyer_points < request["amount"]:
            return False, f"❌ 你的积分不足！\n当前积分：{buyer_points}\n需要：{request['amount']}", None

        # 转账
        points_manager.add_points(group_id, buyer_id, -request["amount"])
        points_manager.add_points(group_id, seller_id, request["amount"])

        # 删除申请
        del self.requests[request_id]
        self._save_requests()

        return True, (
            f"✅ 卖身交易完成！\n"
            f"━━━━━━━━━━━━━━\n"
            f"转账金额：{request['amount']} 积分\n"
            f"称号：{request['title']}\n"
            f"━━━━━━━━━━━━━━\n"
            f"💡 即将修改群昵称"
        ), request

    def cancel_request(self, group_id: str, seller_id: str) -> Tuple[bool, str]:
        """
        取消卖身申请

        Args:
            group_id: 群号
            seller_id: 卖身者QQ号

        Returns:
            (是否成功, 消息)
        """
        request_id = f"{group_id}_{seller_id}"

        if request_id not in self.requests:
            return False, "❌ 没有找到待处理的卖身申请！"

        del self.requests[request_id]
        self._save_requests()

        return True, "✅ 已取消卖身申请"

    def get_request(self, group_id: str, seller_id: str) -> Optional[dict]:
        """
        获取卖身申请

        Args:
            group_id: 群号
            seller_id: 卖身者QQ号

        Returns:
            申请详情或None
        """
        request_id = f"{group_id}_{seller_id}"
        return self.requests.get(request_id)


# 全局卖身管理器实例
sell_manager = SellManager()
