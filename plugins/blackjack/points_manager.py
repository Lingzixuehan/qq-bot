"""
积分管理系统
使用 JSON 文件进行数据持久化
"""
import json
import os
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Tuple
from nonebot.log import logger

# 数据文件路径
DATA_DIR = Path("data/blackjack")
DATA_DIR.mkdir(parents=True, exist_ok=True)
POINTS_FILE = DATA_DIR / "points.json"
SIGN_FILE = DATA_DIR / "sign_records.json"


class PointsManager:
    """积分管理器"""

    def __init__(self):
        """初始化积分管理器"""
        self.points_data: Dict[str, Dict[str, int]] = self._load_points()
        self.sign_data: Dict[str, Dict[str, dict]] = self._load_sign_records()

    def _load_points(self) -> Dict[str, Dict[str, int]]:
        """
        加载积分数据

        Returns:
            {group_id: {user_id: points}}
        """
        if POINTS_FILE.exists():
            try:
                with open(POINTS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载积分数据失败: {e}")
                return {}
        return {}

    def _save_points(self):
        """保存积分数据"""
        try:
            with open(POINTS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.points_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存积分数据失败: {e}")

    def _load_sign_records(self) -> Dict[str, Dict[str, dict]]:
        """
        加载签到记录

        Returns:
            {group_id: {user_id: {last_sign_date, total_count, continuous_count}}}
        """
        if SIGN_FILE.exists():
            try:
                with open(SIGN_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"加载签到记录失败: {e}")
                return {}
        return {}

    def _save_sign_records(self):
        """保存签到记录"""
        try:
            with open(SIGN_FILE, "w", encoding="utf-8") as f:
                json.dump(self.sign_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存签到记录失败: {e}")

    def get_points(self, group_id: str, user_id: str) -> int:
        """
        获取用户积分

        Args:
            group_id: 群号
            user_id: 用户QQ号

        Returns:
            积分数量
        """
        # 如果用户不存在，初始化为500积分
        if group_id not in self.points_data:
            self.points_data[group_id] = {}

        if user_id not in self.points_data[group_id]:
            self.points_data[group_id][user_id] = 500
            self._save_points()
            logger.info(f"用户 {user_id} 在群 {group_id} 获得初始积分 500")

        return self.points_data[group_id][user_id]

    def add_points(self, group_id: str, user_id: str, points: int):
        """
        增加用户积分

        Args:
            group_id: 群号
            user_id: 用户QQ号
            points: 增加的积分
        """
        # 先调用 get_points 确保用户已初始化（会自动设置为500）
        current_points = self.get_points(group_id, user_id)

        self.points_data[group_id][user_id] = current_points + points
        self._save_points()

    def set_points(self, group_id: str, user_id: str, points: int):
        """
        设置用户积分

        Args:
            group_id: 群号
            user_id: 用户QQ号
            points: 积分数量
        """
        if group_id not in self.points_data:
            self.points_data[group_id] = {}
        self.points_data[group_id][user_id] = points
        self._save_points()

    def has_enough_points(self, group_id: str, user_id: str, required: int) -> bool:
        """
        检查用户积分是否足够

        Args:
            group_id: 群号
            user_id: 用户QQ号
            required: 需要的积分

        Returns:
            是否足够
        """
        return self.get_points(group_id, user_id) >= required

    def get_rank(self, group_id: str, limit: int = 10) -> List[Tuple[str, int]]:
        """
        获取积分排行榜

        Args:
            group_id: 群号
            limit: 返回数量

        Returns:
            [(user_id, points), ...] 按积分降序排列
        """
        if group_id not in self.points_data:
            return []

        ranked = sorted(
            self.points_data[group_id].items(),
            key=lambda x: x[1],
            reverse=True
        )
        return ranked[:limit]

    def sign_in(self, group_id: str, user_id: str) -> Tuple[bool, int, str]:
        """
        用户签到

        Args:
            group_id: 群号
            user_id: 用户QQ号

        Returns:
            (是否签到成功, 获得积分, 消息)
        """
        today = date.today().isoformat()

        # 初始化签到记录
        if group_id not in self.sign_data:
            self.sign_data[group_id] = {}
        if user_id not in self.sign_data[group_id]:
            self.sign_data[group_id][user_id] = {
                "last_sign_date": None,
                "total_count": 0,
                "continuous_count": 0
            }

        record = self.sign_data[group_id][user_id]

        # 检查今天是否已签到
        if record["last_sign_date"] == today:
            return False, 0, "你今天已经签到过了！"

        # 计算获得的积分（随机1-20分，带概率）
        import random
        rand = random.random()
        if rand < 0.5:  # 50% 概率
            earned_points = random.randint(1, 5)
        elif rand < 0.8:  # 30% 概率
            earned_points = random.randint(6, 10)
        elif rand < 0.95:  # 15% 概率
            earned_points = random.randint(11, 15)
        else:  # 5% 概率
            earned_points = random.randint(16, 20)

        # 检查连续签到
        yesterday = (datetime.now().date() - __import__("datetime").timedelta(days=1)).isoformat()
        if record["last_sign_date"] == yesterday:
            record["continuous_count"] += 1
        else:
            record["continuous_count"] = 1

        # 连续签到奖励（每连续5天额外+5分）
        bonus = (record["continuous_count"] // 5) * 5
        total_earned = earned_points + bonus

        # 更新记录
        record["last_sign_date"] = today
        record["total_count"] += 1
        self._save_sign_records()

        # 添加积分
        self.add_points(group_id, user_id, total_earned)

        msg = f"签到成功！获得 {earned_points} 积分"
        if bonus > 0:
            msg += f" + 连续签到奖励 {bonus} 积分"
        msg += f"\n连续签到：{record['continuous_count']} 天"
        msg += f"\n当前积分：{self.get_points(group_id, user_id)}"

        return True, total_earned, msg


# 全局积分管理器实例
points_manager = PointsManager()
