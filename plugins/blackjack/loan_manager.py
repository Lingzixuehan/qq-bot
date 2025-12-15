"""
借贷管理系统
管理积分借贷、利息计算和还款
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from nonebot.log import logger

from .points_manager import points_manager

# 数据文件路径
DATA_DIR = Path("data/blackjack")
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOAN_FILE = DATA_DIR / "loans.json"
LOAN_REQUESTS_FILE = DATA_DIR / "loan_requests.json"


class LoanManager:
    """借贷管理器"""

    def __init__(self):
        """初始化借贷管理器"""
        self.loans: Dict[str, Dict[str, dict]] = self._load_loans()
        self.loan_requests: Dict[str, Dict[str, dict]] = self._load_loan_requests()
        # loans结构: {group_id: {borrower_id: {lender_id, principal, interest_rate, games_played, total_interest}}}
        # loan_requests结构: {group_id: {borrower_id: {lender_id, amount}}}

    def _load_loans(self) -> Dict[str, Dict[str, dict]]:
        """
        加载借贷数据

        Returns:
            {group_id: {borrower_id: {...}}}
        """
        if LOAN_FILE.exists():
            try:
                with open(LOAN_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载借贷数据失败: {e}")
                return {}
        return {}

    def _save_loans(self):
        """保存借贷数据"""
        try:
            with open(LOAN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.loans, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存借贷数据失败: {e}")

    def _load_loan_requests(self) -> Dict[str, Dict[str, dict]]:
        """
        加载借贷请求数据

        Returns:
            {group_id: {borrower_id: {...}}}
        """
        if LOAN_REQUESTS_FILE.exists():
            try:
                with open(LOAN_REQUESTS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载借贷请求数据失败: {e}")
                return {}
        return {}

    def _save_loan_requests(self):
        """保存借贷请求数据"""
        try:
            with open(LOAN_REQUESTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.loan_requests, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存借贷请求数据失败: {e}")

    def create_request(self, group_id: str, borrower_id: str, lender_id: str, amount: int) -> Tuple[bool, str]:
        """
        创建借贷请求

        Args:
            group_id: 群号
            borrower_id: 借款人QQ号
            lender_id: 出借人QQ号
            amount: 借款金额

        Returns:
            (是否成功, 消息)
        """
        # 检查是否已有未还清的贷款
        if group_id in self.loans and borrower_id in self.loans[group_id]:
            return False, "❌ 你还有未还清的贷款，无法再次借款！"

        # 检查是否已有待处理的请求
        if group_id in self.loan_requests and borrower_id in self.loan_requests[group_id]:
            return False, "❌ 你已有待处理的借贷请求！"

        # 检查金额是否有效
        if amount <= 0:
            return False, "❌ 借款金额必须大于0！"

        # 创建借贷请求
        if group_id not in self.loan_requests:
            self.loan_requests[group_id] = {}

        interest_rate = 0.1  # 固定10%利率
        total_interest = int(amount * interest_rate)

        self.loan_requests[group_id][borrower_id] = {
            "lender_id": lender_id,
            "amount": amount,
            "interest_rate": interest_rate,
            "total_interest": total_interest
        }

        self._save_loan_requests()

        return True, (
            f"✅ 借贷请求已发送！\n"
            f"━━━━━━━━━━━━━━\n"
            f"借款金额：{amount} 积分\n"
            f"利率：{int(interest_rate * 100)}%\n"
            f"利息：{total_interest} 积分\n"
            f"还款金额：{amount + total_interest} 积分\n"
            f"还款期限：5局游戏后自动扣除\n"
            f"💡 等待对方使用 /同意借贷 @你 来同意"
        )

    def approve_request(self, group_id: str, lender_id: str, borrower_id: str) -> Tuple[bool, str]:
        """
        同意借贷请求

        Args:
            group_id: 群号
            lender_id: 出借人QQ号
            borrower_id: 借款人QQ号

        Returns:
            (是否成功, 消息)
        """
        # 检查请求是否存在
        if group_id not in self.loan_requests or borrower_id not in self.loan_requests[group_id]:
            return False, "❌ 没有找到该借贷请求！"

        request = self.loan_requests[group_id][borrower_id]

        # 检查是否是正确的出借人
        if request["lender_id"] != lender_id:
            return False, "❌ 该借贷请求不是向你发起的！"

        amount = request["amount"]

        # 检查出借人积分是否足够
        lender_points = points_manager.get_points(group_id, lender_id)
        if lender_points < amount:
            return False, f"❌ 你的积分不足！\n当前积分：{lender_points}\n需要：{amount}"

        # 检查借款人是否已有未还清的贷款（再次检查）
        if group_id in self.loans and borrower_id in self.loans[group_id]:
            # 删除请求
            del self.loan_requests[group_id][borrower_id]
            if not self.loan_requests[group_id]:
                del self.loan_requests[group_id]
            self._save_loan_requests()
            return False, "❌ 借款人已有未还清的贷款！"

        # 创建借贷记录
        if group_id not in self.loans:
            self.loans[group_id] = {}

        self.loans[group_id][borrower_id] = {
            "lender_id": lender_id,
            "principal": amount,
            "interest_rate": request["interest_rate"],
            "total_interest": request["total_interest"],
            "games_played": 0,
            "repayment_due": 5  # 5局后还款
        }

        # 转账
        points_manager.add_points(group_id, lender_id, -amount)
        points_manager.add_points(group_id, borrower_id, amount)

        # 删除请求
        del self.loan_requests[group_id][borrower_id]
        if not self.loan_requests[group_id]:
            del self.loan_requests[group_id]

        self._save_loans()
        self._save_loan_requests()

        return True, (
            f"✅ 借贷成功！\n"
            f"━━━━━━━━━━━━━━\n"
            f"借款金额：{amount} 积分\n"
            f"利率：{int(request['interest_rate'] * 100)}%\n"
            f"利息：{request['total_interest']} 积分\n"
            f"还款金额：{amount + request['total_interest']} 积分\n"
            f"还款期限：5局游戏后自动扣除"
        )

    def cancel_request(self, group_id: str, borrower_id: str) -> Tuple[bool, str]:
        """
        取消借贷请求

        Args:
            group_id: 群号
            borrower_id: 借款人QQ号

        Returns:
            (是否成功, 消息)
        """
        # 检查请求是否存在
        if group_id not in self.loan_requests or borrower_id not in self.loan_requests[group_id]:
            return False, "❌ 你没有待处理的借贷请求！"

        # 删除请求
        del self.loan_requests[group_id][borrower_id]
        if not self.loan_requests[group_id]:
            del self.loan_requests[group_id]

        self._save_loan_requests()

        return True, "✅ 借贷请求已取消！"

    def has_loan(self, group_id: str, user_id: str) -> bool:
        """
        检查用户是否有未还清的贷款

        Args:
            group_id: 群号
            user_id: 用户QQ号

        Returns:
            是否有贷款
        """
        return group_id in self.loans and user_id in self.loans[group_id]

    def increment_games_played(self, group_id: str, user_id: str):
        """
        增加用户已玩游戏局数

        Args:
            group_id: 群号
            user_id: 用户QQ号
        """
        if not self.has_loan(group_id, user_id):
            return

        loan = self.loans[group_id][user_id]
        loan["games_played"] += 1

        logger.info(f"用户 {user_id} 在群 {group_id} 完成第 {loan['games_played']} 局游戏")

        # 检查是否到期
        if loan["games_played"] >= loan["repayment_due"]:
            self._force_repayment(group_id, user_id)
        else:
            self._save_loans()

    def _force_repayment(self, group_id: str, user_id: str):
        """
        强制还款

        Args:
            group_id: 群号
            user_id: 借款人QQ号
        """
        if not self.has_loan(group_id, user_id):
            return

        loan = self.loans[group_id][user_id]
        lender_id = loan["lender_id"]
        repayment_amount = loan["principal"] + loan["total_interest"]

        # 扣除借款人积分
        points_manager.add_points(group_id, user_id, -repayment_amount)

        # 增加债权人积分
        points_manager.add_points(group_id, lender_id, repayment_amount)

        # 删除借贷记录
        del self.loans[group_id][user_id]
        if not self.loans[group_id]:
            del self.loans[group_id]

        self._save_loans()

        logger.info(
            f"用户 {user_id} 在群 {group_id} 强制还款 {repayment_amount} 积分给 {lender_id}"
        )

    def get_loan_info(self, group_id: str, user_id: str) -> Optional[str]:
        """
        获取借贷信息

        Args:
            group_id: 群号
            user_id: 用户QQ号

        Returns:
            借贷信息字符串或None
        """
        if not self.has_loan(group_id, user_id):
            return None

        loan = self.loans[group_id][user_id]
        remaining_games = loan["repayment_due"] - loan["games_played"]
        repayment_amount = loan["principal"] + loan["total_interest"]

        return (
            f"📋 借贷信息\n"
            f"━━━━━━━━━━━━━━\n"
            f"借款金额：{loan['principal']} 积分\n"
            f"利息：{loan['total_interest']} 积分（{int(loan['interest_rate'] * 100)}%）\n"
            f"还款金额：{repayment_amount} 积分\n"
            f"已完成：{loan['games_played']}/{loan['repayment_due']} 局\n"
            f"剩余：{remaining_games} 局游戏后自动扣除"
        )


# 全局借贷管理器实例
loan_manager = LoanManager()
