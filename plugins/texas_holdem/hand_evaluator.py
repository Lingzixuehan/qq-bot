"""
德州扑克手牌评估器
"""
from enum import IntEnum
from typing import List, Tuple
from itertools import combinations
from collections import Counter
from .card import TexasCard


class HandRank(IntEnum):
    """牌型枚举（从小到大）"""
    HIGH_CARD = 1       # 高牌
    ONE_PAIR = 2        # 一对
    TWO_PAIR = 3        # 两对
    THREE_OF_KIND = 4   # 三条
    STRAIGHT = 5        # 顺子
    FLUSH = 6           # 同花
    FULL_HOUSE = 7      # 葫芦
    FOUR_OF_KIND = 8    # 四条
    STRAIGHT_FLUSH = 9  # 同花顺
    ROYAL_FLUSH = 10    # 皇家同花顺


class HandEvaluator:
    """手牌评估器"""

    # 牌型中文名称
    RANK_NAMES = {
        HandRank.HIGH_CARD: "高牌",
        HandRank.ONE_PAIR: "一对",
        HandRank.TWO_PAIR: "两对",
        HandRank.THREE_OF_KIND: "三条",
        HandRank.STRAIGHT: "顺子",
        HandRank.FLUSH: "同花",
        HandRank.FULL_HOUSE: "葫芦",
        HandRank.FOUR_OF_KIND: "四条",
        HandRank.STRAIGHT_FLUSH: "同花顺",
        HandRank.ROYAL_FLUSH: "皇家同花顺",
    }

    @staticmethod
    def evaluate_best_hand(hole_cards: List[TexasCard], community_cards: List[TexasCard]) -> Tuple[HandRank, List[int], List[TexasCard]]:
        """
        从7张牌中评估最佳的5张牌组合

        Args:
            hole_cards: 手牌（2张）
            community_cards: 公共牌（5张）

        Returns:
            (牌型, 比较值列表, 最佳5张牌)
        """
        all_cards = hole_cards + community_cards

        if len(all_cards) < 5:
            raise ValueError("至少需要5张牌才能评估")

        best_rank = None
        best_values = None
        best_cards = None

        # 从所有牌中选出5张的所有组合
        for five_cards in combinations(all_cards, 5):
            rank, values = HandEvaluator._evaluate_five_cards(list(five_cards))

            # 比较并保留最好的组合
            if best_rank is None or HandEvaluator._compare_hands(rank, values, best_rank, best_values) > 0:
                best_rank = rank
                best_values = values
                best_cards = list(five_cards)

        return best_rank, best_values, best_cards

    @staticmethod
    def _evaluate_five_cards(cards: List[TexasCard]) -> Tuple[HandRank, List[int]]:
        """
        评估5张牌的牌型

        Args:
            cards: 5张牌

        Returns:
            (牌型, 比较值列表)
        """
        if len(cards) != 5:
            raise ValueError("必须是5张牌")

        # 检查同花顺和皇家同花顺
        if HandEvaluator._is_flush(cards):
            straight_high = HandEvaluator._is_straight(cards)
            if straight_high is not None:
                # 皇家同花顺：A K Q J T
                if straight_high == 14:
                    return HandRank.ROYAL_FLUSH, [14]
                # 同花顺
                return HandRank.STRAIGHT_FLUSH, [straight_high]

        # 统计每个点数的数量
        rank_counts = Counter(card.value for card in cards)
        counts = sorted(rank_counts.values(), reverse=True)
        rank_order = sorted(rank_counts.keys(), key=lambda x: (rank_counts[x], x), reverse=True)

        # 四条
        if counts == [4, 1]:
            four_kind = [r for r in rank_order if rank_counts[r] == 4][0]
            kicker = [r for r in rank_order if rank_counts[r] == 1][0]
            return HandRank.FOUR_OF_KIND, [four_kind, kicker]

        # 葫芦
        if counts == [3, 2]:
            three_kind = [r for r in rank_order if rank_counts[r] == 3][0]
            pair = [r for r in rank_order if rank_counts[r] == 2][0]
            return HandRank.FULL_HOUSE, [three_kind, pair]

        # 同花
        if HandEvaluator._is_flush(cards):
            sorted_values = sorted([card.value for card in cards], reverse=True)
            return HandRank.FLUSH, sorted_values

        # 顺子
        straight_high = HandEvaluator._is_straight(cards)
        if straight_high is not None:
            return HandRank.STRAIGHT, [straight_high]

        # 三条
        if counts == [3, 1, 1]:
            three_kind = [r for r in rank_order if rank_counts[r] == 3][0]
            kickers = sorted([r for r in rank_order if rank_counts[r] == 1], reverse=True)
            return HandRank.THREE_OF_KIND, [three_kind] + kickers

        # 两对
        if counts == [2, 2, 1]:
            pairs = sorted([r for r in rank_order if rank_counts[r] == 2], reverse=True)
            kicker = [r for r in rank_order if rank_counts[r] == 1][0]
            return HandRank.TWO_PAIR, pairs + [kicker]

        # 一对
        if counts == [2, 1, 1, 1]:
            pair = [r for r in rank_order if rank_counts[r] == 2][0]
            kickers = sorted([r for r in rank_order if rank_counts[r] == 1], reverse=True)
            return HandRank.ONE_PAIR, [pair] + kickers

        # 高牌
        sorted_values = sorted([card.value for card in cards], reverse=True)
        return HandRank.HIGH_CARD, sorted_values

    @staticmethod
    def _is_flush(cards: List[TexasCard]) -> bool:
        """判断是否是同花"""
        suits = [card.suit for card in cards]
        return len(set(suits)) == 1

    @staticmethod
    def _is_straight(cards: List[TexasCard]) -> int | None:
        """
        判断是否是顺子

        Returns:
            顺子的最高牌值，如果不是顺子则返回None
        """
        values = sorted([card.value for card in cards], reverse=True)

        # 标准顺子检测
        if values[0] - values[4] == 4 and len(set(values)) == 5:
            return values[0]

        # 特殊情况：A-2-3-4-5（最小顺子，A当作1）
        if values == [14, 5, 4, 3, 2]:
            return 5  # 这种顺子的"最高牌"是5

        return None

    @staticmethod
    def _compare_hands(rank1: HandRank, values1: List[int], rank2: HandRank, values2: List[int]) -> int:
        """
        比较两手牌的大小

        Returns:
            1: hand1 > hand2
            0: hand1 == hand2
            -1: hand1 < hand2
        """
        # 先比较牌型
        if rank1 > rank2:
            return 1
        if rank1 < rank2:
            return -1

        # 牌型相同，比较比较值
        for v1, v2 in zip(values1, values2):
            if v1 > v2:
                return 1
            if v1 < v2:
                return -1

        # 完全相同
        return 0

    @staticmethod
    def compare_hands(hand1: Tuple[HandRank, List[int]], hand2: Tuple[HandRank, List[int]]) -> int:
        """
        比较两手牌的大小（公开接口）

        Args:
            hand1: (牌型, 比较值列表)
            hand2: (牌型, 比较值列表)

        Returns:
            1: hand1 > hand2
            0: hand1 == hand2
            -1: hand1 < hand2
        """
        return HandEvaluator._compare_hands(hand1[0], hand1[1], hand2[0], hand2[1])

    @staticmethod
    def get_hand_description(rank: HandRank, values: List[int], cards: List[TexasCard] = None) -> str:
        """
        获取手牌的描述

        Args:
            rank: 牌型
            values: 比较值列表
            cards: 牌列表（用于显示）

        Returns:
            手牌描述字符串
        """
        rank_name = HandEvaluator.RANK_NAMES.get(rank, "未知")

        # 如果有牌，显示牌面
        cards_str = ""
        if cards:
            cards_str = f" ({' '.join(str(card) for card in cards)})"

        # 根据不同牌型添加详细说明
        if rank == HandRank.ROYAL_FLUSH:
            return f"🌟 {rank_name}{cards_str}"
        elif rank == HandRank.STRAIGHT_FLUSH:
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            high_card = rank_names.get(values[0], str(values[0]))
            return f"💎 {rank_name}({high_card}高){cards_str}"
        elif rank == HandRank.FOUR_OF_KIND:
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            four = rank_names.get(values[0], str(values[0]))
            return f"🎯 {rank_name}({four}){cards_str}"
        elif rank == HandRank.FULL_HOUSE:
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            three = rank_names.get(values[0], str(values[0]))
            two = rank_names.get(values[1], str(values[1]))
            return f"🏠 {rank_name}({three}带{two}){cards_str}"
        elif rank == HandRank.FLUSH:
            return f"🌊 {rank_name}{cards_str}"
        elif rank == HandRank.STRAIGHT:
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            high_card = rank_names.get(values[0], str(values[0]))
            return f"📈 {rank_name}({high_card}高){cards_str}"
        elif rank == HandRank.THREE_OF_KIND:
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            three = rank_names.get(values[0], str(values[0]))
            return f"🎲 {rank_name}({three}){cards_str}"
        elif rank == HandRank.TWO_PAIR:
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            pair1 = rank_names.get(values[0], str(values[0]))
            pair2 = rank_names.get(values[1], str(values[1]))
            return f"👥 {rank_name}({pair1}和{pair2}){cards_str}"
        elif rank == HandRank.ONE_PAIR:
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            pair = rank_names.get(values[0], str(values[0]))
            return f"🎴 {rank_name}({pair}){cards_str}"
        else:  # HIGH_CARD
            rank_names = {14: "A", 13: "K", 12: "Q", 11: "J", 10: "T"}
            high = rank_names.get(values[0], str(values[0]))
            return f"🃏 {rank_name}({high}){cards_str}"
