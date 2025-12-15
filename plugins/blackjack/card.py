"""
扑克牌类
"""
import random
from typing import List


class Card:
    """扑克牌类"""

    SUITS = ["♥", "♦", "♣", "♠"]
    RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

    def __init__(self, num: int):
        """
        初始化扑克牌

        Args:
            num: 0-51 的数字，代表一张牌
        """
        self.suit = self.SUITS[num // 13]
        self.rank_index = num % 13
        self.rank = self.RANKS[self.rank_index]

    def __str__(self) -> str:
        """返回牌的字符串表示"""
        return f"{self.suit}{self.rank}"

    def get_value(self) -> int:
        """
        获取牌的点数

        Returns:
            点数值（A=1, 2-10=面值, J/Q/K=10）
        """
        if self.rank == "A":
            return 1  # A初始为1，后续计算时可能变为11
        elif self.rank in ["J", "Q", "K"]:
            return 10
        else:
            return int(self.rank)


class Deck:
    """牌堆类"""

    def __init__(self):
        """初始化一副牌（52张）"""
        self.cards: List[Card] = [Card(i) for i in range(52)]
        self.shuffle()

    def shuffle(self):
        """洗牌"""
        random.shuffle(self.cards)

    def deal(self) -> Card:
        """
        发一张牌

        Returns:
            发出的牌
        """
        if not self.cards:
            # 如果牌发完了，重新洗牌
            self.cards = [Card(i) for i in range(52)]
            self.shuffle()
        return self.cards.pop()


class Hand:
    """手牌类"""

    def __init__(self):
        """初始化空手牌"""
        self.cards: List[Card] = []

    def add_card(self, card: Card):
        """添加一张牌"""
        self.cards.append(card)

    def get_value(self) -> int:
        """
        计算手牌总点数

        Returns:
            总点数（考虑A的最优值）
        """
        value = sum(card.get_value() for card in self.cards)
        aces = sum(1 for card in self.cards if card.rank == "A")

        # 尝试将A当作11来计算，只要不爆牌
        while aces > 0 and value + 10 <= 21:
            value += 10
            aces -= 1

        return value

    def is_blackjack(self) -> bool:
        """
        判断是否是黑杰克（两张牌21点）

        Returns:
            是否是黑杰克
        """
        return len(self.cards) == 2 and self.get_value() == 21

    def is_bust(self) -> bool:
        """
        判断是否爆牌

        Returns:
            是否爆牌
        """
        return self.get_value() > 21

    def __str__(self) -> str:
        """返回手牌的字符串表示"""
        return " ".join(str(card) for card in self.cards)
