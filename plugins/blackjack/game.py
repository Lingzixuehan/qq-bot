"""
21点游戏逻辑
"""
import random
from typing import Dict, Optional
from .card import Deck, Hand
from .points_manager import points_manager


class BlackjackGame:
    """21点游戏类"""

    def __init__(self, group_id: str, creator_id: str, creator_name: str, bet: int):
        """
        初始化游戏

        Args:
            group_id: 群号
            creator_id: 创建者QQ号
            creator_name: 创建者昵称
            bet: 赌注
        """
        self.group_id = group_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.player_id: Optional[str] = None
        self.player_name: Optional[str] = None
        self.bet = bet
        self.deck = Deck()

        # 手牌
        self.creator_hand = Hand()
        self.player_hand = Hand()

        # 游戏状态
        self.started = False
        self.finished = False
        self.winner: Optional[str] = None

    def start(self, player_id: str, player_name: str) -> str:
        """
        开始游戏（有玩家接受）

        Args:
            player_id: 玩家QQ号
            player_name: 玩家昵称

        Returns:
            开始游戏的消息
        """
        self.player_id = player_id
        self.player_name = player_name
        self.started = True

        # 发初始牌（每人两张）
        self.creator_hand.add_card(self.deck.deal())
        self.player_hand.add_card(self.deck.deal())
        self.creator_hand.add_card(self.deck.deal())
        self.player_hand.add_card(self.deck.deal())

        # 检查是否有人直接黑杰克
        msg = f"🎮 游戏开始！\n"
        msg += f"━━━━━━━━━━━━━━\n"
        msg += f"庄家【{self.creator_name}】：{self.creator_hand.cards[0]} ?\n"
        msg += f"闲家【{self.player_name}】：{self.player_hand} ({self.player_hand.get_value()}点)\n"
        msg += f"━━━━━━━━━━━━━━\n"

        if self.player_hand.is_blackjack():
            if self.creator_hand.is_blackjack():
                msg += "🎊 双方都是黑杰克！平局！"
                self.finished = True
                self.winner = "draw"
            else:
                msg += f"🎊 {self.player_name} 黑杰克！闲家获胜！"
                self.finished = True
                self.winner = self.player_id
        elif self.creator_hand.is_blackjack():
            msg += f"🎊 {self.creator_name} 黑杰克！庄家获胜！"
            self.finished = True
            self.winner = self.creator_id
        else:
            msg += f"💡 {self.player_name} 请选择：/叫牌 或 /停牌"

        return msg

    def hit(self) -> str:
        """
        玩家叫牌

        Returns:
            叫牌结果消息
        """
        if self.finished:
            return "游戏已结束！"

        # 玩家抽一张牌
        card = self.deck.deal()
        self.player_hand.add_card(card)

        msg = f"🎴 {self.player_name} 叫牌：{card}\n"
        msg += f"━━━━━━━━━━━━━━\n"
        msg += f"庄家【{self.creator_name}】：{self.creator_hand.cards[0]} ?\n"
        msg += f"闲家【{self.player_name}】：{self.player_hand} ({self.player_hand.get_value()}点)\n"
        msg += f"━━━━━━━━━━━━━━\n"

        if self.player_hand.is_bust():
            msg += f"💥 爆牌了！庄家【{self.creator_name}】获胜！"
            self.finished = True
            self.winner = self.creator_id
        elif self.player_hand.get_value() == 21:
            msg += "🎯 21点！自动停牌"
            return msg + "\n\n" + self.stand()
        else:
            msg += f"💡 请选择：/叫牌 或 /停牌"

        return msg

    def stand(self) -> str:
        """
        玩家停牌，庄家开始补牌

        Returns:
            结果消息
        """
        if self.finished:
            return "游戏已结束！"

        # 庄家补牌逻辑：点数小于17必须叫牌
        while self.creator_hand.get_value() < 17:
            self.creator_hand.add_card(self.deck.deal())

        # 显示最终结果
        msg = f"🎲 最终结果\n"
        msg += f"━━━━━━━━━━━━━━\n"
        msg += f"庄家【{self.creator_name}】：{self.creator_hand} ({self.creator_hand.get_value()}点)\n"
        msg += f"闲家【{self.player_name}】：{self.player_hand} ({self.player_hand.get_value()}点)\n"
        msg += f"━━━━━━━━━━━━━━\n"

        creator_value = self.creator_hand.get_value()
        player_value = self.player_hand.get_value()

        # 判断胜负
        if self.creator_hand.is_bust():
            msg += f"💥 庄家爆牌！闲家【{self.player_name}】获胜！"
            self.winner = self.player_id
        elif player_value > creator_value:
            msg += f"🎉 闲家【{self.player_name}】获胜！"
            self.winner = self.player_id
        elif player_value < creator_value:
            msg += f"🎉 庄家【{self.creator_name}】获胜！"
            self.winner = self.creator_id
        else:
            msg += "🤝 平局！"
            self.winner = "draw"

        self.finished = True
        return msg

    def settle(self) -> str:
        """
        结算积分

        Returns:
            结算消息
        """
        if not self.finished or self.winner is None:
            return ""

        # 计算奖励积分（基础赌注 + 随机奖励0-10%）
        bonus_rate = random.randint(0, 10) / 100
        bonus = int(self.bet * bonus_rate)
        total_win = self.bet + bonus

        msg = "\n💰 积分结算\n"
        msg += f"━━━━━━━━━━━━━━\n"

        if self.winner == "draw":
            # 平局，退还赌注
            msg += "平局，赌注退还"
        elif self.winner == self.creator_id:
            # 庄家赢
            points_manager.add_points(self.group_id, self.creator_id, total_win)
            points_manager.add_points(self.group_id, self.player_id, -self.bet)
            msg += f"🏆 {self.creator_name} +{total_win} 积分\n"
            msg += f"💸 {self.player_name} -{self.bet} 积分"
            if bonus > 0:
                msg += f"\n🎁 胜利奖励：+{bonus} 积分"
        else:
            # 玩家赢
            points_manager.add_points(self.group_id, self.player_id, total_win)
            points_manager.add_points(self.group_id, self.creator_id, -self.bet)
            msg += f"🏆 {self.player_name} +{total_win} 积分\n"
            msg += f"💸 {self.creator_name} -{self.bet} 积分"
            if bonus > 0:
                msg += f"\n🎁 胜利奖励：+{bonus} 积分"

        return msg


# 全局游戏管理
class GameManager:
    """游戏管理器"""

    def __init__(self):
        """初始化游戏管理器"""
        self.games: Dict[str, Dict[int, BlackjackGame]] = {}
        self.next_game_id: Dict[str, int] = {}

    def create_game(self, group_id: str, creator_id: str, creator_name: str, bet: int) -> int:
        """
        创建游戏

        Args:
            group_id: 群号
            creator_id: 创建者QQ号
            creator_name: 创建者昵称
            bet: 赌注

        Returns:
            游戏ID
        """
        if group_id not in self.games:
            self.games[group_id] = {}
            self.next_game_id[group_id] = 1

        game_id = self.next_game_id[group_id]
        self.games[group_id][game_id] = BlackjackGame(group_id, creator_id, creator_name, bet)
        self.next_game_id[group_id] += 1

        return game_id

    def get_game(self, group_id: str, game_id: int) -> Optional[BlackjackGame]:
        """
        获取游戏

        Args:
            group_id: 群号
            game_id: 游戏ID

        Returns:
            游戏对象或None
        """
        return self.games.get(group_id, {}).get(game_id)

    def get_player_game(self, group_id: str, user_id: str) -> Optional[BlackjackGame]:
        """
        获取用户正在进行的游戏

        Args:
            group_id: 群号
            user_id: 用户QQ号

        Returns:
            游戏对象或None
        """
        for game in self.games.get(group_id, {}).values():
            if game.started and not game.finished:
                if game.creator_id == user_id or game.player_id == user_id:
                    return game
        return None

    def remove_game(self, group_id: str, game_id: int):
        """
        移除游戏

        Args:
            group_id: 群号
            game_id: 游戏ID
        """
        if group_id in self.games and game_id in self.games[group_id]:
            del self.games[group_id][game_id]

    def get_waiting_games(self, group_id: str) -> list:
        """
        获取等待中的游戏列表

        Args:
            group_id: 群号

        Returns:
            [(game_id, game), ...]
        """
        if group_id not in self.games:
            return []

        return [
            (gid, game)
            for gid, game in self.games[group_id].items()
            if not game.started and not game.finished
        ]


# 全局游戏管理器实例
game_manager = GameManager()
