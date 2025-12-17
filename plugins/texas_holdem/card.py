"""
德州扑克牌类
"""
import random
from typing import List


class TexasCard:
    """德州扑克牌类"""

    SUITS = ["♥", "♦", "♣", "♠"]
    RANKS = ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]

    # 用于比较大小的数值 (2=2, 3=3, ..., T=10, J=11, Q=12, K=13, A=14)
    RANK_VALUES = {
        "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
        "T": 10, "J": 11, "Q": 12, "K": 13, "A": 14
    }

    def __init__(self, num: int):
        """
        初始化扑克牌

        Args:
            num: 0-51 的数字，代表一张牌
        """
        self.suit = self.SUITS[num // 13]
        self.rank_index = num % 13
        self.rank = self.RANKS[self.rank_index]
        self.value = self.RANK_VALUES[self.rank]

    def __str__(self) -> str:
        """返回牌的字符串表示"""
        return f"{self.suit}{self.rank}"

    def __repr__(self) -> str:
        """返回牌的调试字符串"""
        return f"TexasCard({self.suit}{self.rank})"

    def __eq__(self, other) -> bool:
        """判断两张牌是否相同"""
        if not isinstance(other, TexasCard):
            return False
        return self.suit == other.suit and self.rank == other.rank

    def __hash__(self):
        """哈希值，用于集合操作"""
        return hash((self.suit, self.rank))


class TexasDeck:
    """德州扑克牌堆类（52张）"""

    def __init__(self):
        """初始化一副牌（52张）"""
        self.cards: List[TexasCard] = [TexasCard(i) for i in range(52)]
        self.shuffle()

    def shuffle(self):
        """洗牌"""
        random.shuffle(self.cards)

    def deal(self) -> TexasCard:
        """
        发一张牌

        Returns:
            发出的牌
        """
        if not self.cards:
            raise RuntimeError("牌堆已空，无法继续发牌")
        return self.cards.pop()

    def remaining(self) -> int:
        """返回剩余牌数"""
        return len(self.cards)


class CommunityCards:
    """公共牌管理类"""

    def __init__(self):
        """初始化空公共牌"""
        self.cards: List[TexasCard] = []

    def add_flop(self, cards: List[TexasCard]):
        """
        添加翻牌（3张）

        Args:
            cards: 3张牌的列表
        """
        if len(cards) != 3:
            raise ValueError("翻牌必须是3张牌")
        if len(self.cards) != 0:
            raise RuntimeError("已经发过翻牌了")
        self.cards.extend(cards)

    def add_turn(self, card: TexasCard):
        """
        添加转牌（1张）

        Args:
            card: 转牌
        """
        if len(self.cards) != 3:
            raise RuntimeError("必须先发翻牌")
        self.cards.append(card)

    def add_river(self, card: TexasCard):
        """
        添加河牌（1张）

        Args:
            card: 河牌
        """
        if len(self.cards) != 4:
            raise RuntimeError("必须先发转牌")
        self.cards.append(card)

    def get_cards(self) -> List[TexasCard]:
        """获取所有公共牌"""
        return self.cards.copy()

    def __str__(self) -> str:
        """返回公共牌的字符串表示"""
        if not self.cards:
            return "暂无公共牌"
        return " ".join(str(card) for card in self.cards)

    def __len__(self) -> int:
        """返回公共牌数量"""
        return len(self.cards)
