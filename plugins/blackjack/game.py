"""
21点游戏逻辑 - 支持多人模式
"""
import random
from typing import Dict, List, Optional, Tuple
from .card import Deck, Hand
from .points_manager import points_manager


class Player:
    """玩家类"""

    def __init__(self, user_id: str, user_name: str):
        self.user_id = user_id
        self.user_name = user_name
        self.hand = Hand()
        self.finished = False  # 是否已完成操作


class BlackjackGame:
    """21点游戏类 - 支持多人"""

    def __init__(self, group_id: str, creator_id: str, creator_name: str, bet: int, max_players: int = 1):
        """
        初始化游戏

        Args:
            group_id: 群号
            creator_id: 创建者QQ号（庄家）
            creator_name: 创建者昵称
            bet: 赌注
            max_players: 最大玩家数（不包括庄家）
        """
        self.group_id = group_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.bet = bet
        self.max_players = max_players
        self.deck = Deck()

        # 庄家手牌
        self.creator_hand = Hand()

        # 玩家列表
        self.players: List[Player] = []

        # 游戏状态
        self.started = False
        self.finished = False
        self.current_player_idx = 0  # 当前操作的玩家索引

    def add_player(self, player_id: str, player_name: str) -> Tuple[bool, str]:
        """
        添加玩家

        Args:
            player_id: 玩家QQ号
            player_name: 玩家昵称

        Returns:
            (是否成功, 消息)
        """
        if len(self.players) >= self.max_players:
            return False, "游戏已满员！"

        if player_id == self.creator_id:
            return False, "庄家不能参与游戏！"

        # 检查是否已经加入
        for player in self.players:
            if player.user_id == player_id:
                return False, "你已经加入了这个游戏！"

        player = Player(player_id, player_name)
        self.players.append(player)

        # 如果满员，自动开始游戏
        if len(self.players) == self.max_players:
            return True, self.start()
        else:
            return True, f"{player_name} 加入游戏！({len(self.players)}/{self.max_players})"

    def start(self) -> str:
        """
        开始游戏

        Returns:
            开始游戏的消息
        """
        self.started = True

        # 发初始牌（庄家和每个玩家各两张）
        self.creator_hand.add_card(self.deck.deal())
        for player in self.players:
            player.hand.add_card(self.deck.deal())

        self.creator_hand.add_card(self.deck.deal())
        for player in self.players:
            player.hand.add_card(self.deck.deal())

        # 显示初始状态
        msg = f"🎮 游戏开始！\n"
        msg += f"━━━━━━━━━━━━━━\n"
        msg += f"庄家【{self.creator_name}】：{self.creator_hand.cards[0]} ?\n"
        msg += f"━━━━━━━━━━━━━━\n"

        # 检查是否有人黑杰克
        creator_blackjack = self.creator_hand.is_blackjack()
        blackjack_players = []

        for i, player in enumerate(self.players):
            value = player.hand.get_value()
            msg += f"玩家{i+1}【{player.user_name}】：{player.hand} ({value}点)"
            if player.hand.is_blackjack():
                msg += " 🎊黑杰克！"
                blackjack_players.append(player)
            msg += "\n"

        msg += f"━━━━━━━━━━━━━━\n"

        # 如果庄家黑杰克，游戏直接结束
        if creator_blackjack:
            msg += f"🎊 庄家【{self.creator_name}】黑杰克！\n"
            self.finished = True
            for player in self.players:
                player.finished = True
        # 如果有玩家黑杰克但庄家没有，标记这些玩家完成
        elif blackjack_players:
            for player in blackjack_players:
                player.finished = True
            current = self.players[self.current_player_idx]
            msg += f"💡 轮到 [AT:{current.user_id}] 【{current.user_name}】\n请选择：/叫牌 或 /停牌"
        else:
            current = self.players[self.current_player_idx]
            msg += f"💡 轮到 [AT:{current.user_id}] 【{current.user_name}】\n请选择：/叫牌 或 /停牌"

        return msg

    def get_current_player(self) -> Optional[Player]:
        """
        获取当前操作的玩家

        Returns:
            当前玩家或None
        """
        if self.finished or not self.started:
            return None

        # 跳过已完成的玩家
        while self.current_player_idx < len(self.players):
            player = self.players[self.current_player_idx]
            if not player.finished:
                return player
            self.current_player_idx += 1

        return None

    def hit(self, user_id: str) -> str:
        """
        玩家叫牌

        Args:
            user_id: 用户ID

        Returns:
            叫牌结果消息
        """
        current_player = self.get_current_player()
        if not current_player:
            return "现在不是你的回合！"

        if current_player.user_id != user_id:
            return "现在不是你的回合！"

        # 抽一张牌
        card = self.deck.deal()
        current_player.hand.add_card(card)

        msg = f"🎴 {current_player.user_name} 叫牌：{card}\n"
        msg += f"当前手牌：{current_player.hand} ({current_player.hand.get_value()}点)\n"

        if current_player.hand.is_bust():
            msg += f"💥 爆牌了！\n"
            current_player.finished = True
            self.current_player_idx += 1

            # 检查是否所有玩家都完成
            if self._all_players_finished():
                msg += "\n" + self._dealer_play()
            else:
                next_player = self.get_current_player()
                if next_player:
                    msg += f"━━━━━━━━━━━━━━\n💡 轮到 [AT:{next_player.user_id}] 【{next_player.user_name}】\n请选择：/叫牌 或 /停牌"
        elif current_player.hand.get_value() == 21:
            msg += "🎯 21点！自动停牌\n"
            current_player.finished = True
            self.current_player_idx += 1

            # 检查是否所有玩家都完成
            if self._all_players_finished():
                msg += "\n" + self._dealer_play()
            else:
                next_player = self.get_current_player()
                if next_player:
                    msg += f"━━━━━━━━━━━━━━\n💡 轮到 [AT:{next_player.user_id}] 【{next_player.user_name}】\n请选择：/叫牌 或 /停牌"

        return msg

    def stand(self, user_id: str) -> str:
        """
        玩家停牌

        Args:
            user_id: 用户ID

        Returns:
            停牌结果消息
        """
        current_player = self.get_current_player()
        if not current_player:
            return "现在不是你的回合！"

        if current_player.user_id != user_id:
            return "现在不是你的回合！"

        msg = f"✋ {current_player.user_name} 停牌\n"
        current_player.finished = True
        self.current_player_idx += 1

        # 检查是否所有玩家都完成
        if self._all_players_finished():
            msg += self._dealer_play()
        else:
            next_player = self.get_current_player()
            if next_player:
                msg += f"━━━━━━━━━━━━━━\n💡 轮到 [AT:{next_player.user_id}] 【{next_player.user_name}】\n请选择：/叫牌 或 /停牌"

        return msg

    def _all_players_finished(self) -> bool:
        """检查所有玩家是否都完成了操作"""
        return all(player.finished for player in self.players)

    def _dealer_play(self) -> str:
        """
        庄家补牌

        Returns:
            庄家补牌和最终结果消息
        """
        # 庄家补牌逻辑：点数小于17必须叫牌
        while self.creator_hand.get_value() < 17:
            self.creator_hand.add_card(self.deck.deal())

        # 显示最终结果
        msg = f"\n🎲 最终结果\n"
        msg += f"━━━━━━━━━━━━━━\n"
        msg += f"庄家【{self.creator_name}】：{self.creator_hand} ({self.creator_hand.get_value()}点)"
        if self.creator_hand.is_bust():
            msg += " 💥爆牌"
        msg += "\n"
        msg += f"━━━━━━━━━━━━━━\n"

        creator_value = self.creator_hand.get_value()

        for i, player in enumerate(self.players):
            value = player.hand.get_value()
            msg += f"玩家{i+1}【{player.user_name}】：{player.hand} ({value}点)"

            # 判断胜负
            if player.hand.is_bust():
                msg += " ❌爆牌，庄家胜"
            elif self.creator_hand.is_bust():
                msg += " ✅庄家爆牌，玩家胜"
            elif value > creator_value:
                msg += " ✅玩家胜"
            elif value < creator_value:
                msg += " ❌庄家胜"
            else:
                msg += " 🤝平局"
            msg += "\n"

        self.finished = True
        return msg

    def settle(self) -> str:
        """
        结算积分

        Returns:
            结算消息
        """
        if not self.finished:
            return ""

        msg = "\n💰 积分结算\n"
        msg += f"━━━━━━━━━━━━━━\n"

        creator_value = self.creator_hand.get_value()
        creator_bust = self.creator_hand.is_bust()

        total_creator_change = 0

        for player in self.players:
            player_value = player.hand.get_value()
            player_bust = player.hand.is_bust()

            # 计算奖励积分（基础赌注 + 随机奖励0-10%）
            bonus_rate = random.randint(0, 10) / 100
            bonus = int(self.bet * bonus_rate)
            total_win = self.bet + bonus

            # 判断胜负并结算
            if player_bust:
                # 玩家爆牌，庄家赢
                points_manager.add_points(self.group_id, player.user_id, -self.bet)
                total_creator_change += self.bet
                msg += f"💸 {player.user_name} -{self.bet} 积分\n"
            elif creator_bust:
                # 庄家爆牌，玩家赢
                points_manager.add_points(self.group_id, player.user_id, total_win)
                total_creator_change -= total_win
                msg += f"🏆 {player.user_name} +{total_win} 积分"
                if bonus > 0:
                    msg += f" (奖励+{bonus})"
                msg += "\n"
            elif player_value > creator_value:
                # 玩家赢
                points_manager.add_points(self.group_id, player.user_id, total_win)
                total_creator_change -= total_win
                msg += f"🏆 {player.user_name} +{total_win} 积分"
                if bonus > 0:
                    msg += f" (奖励+{bonus})"
                msg += "\n"
            elif player_value < creator_value:
                # 庄家赢
                points_manager.add_points(self.group_id, player.user_id, -self.bet)
                total_creator_change += self.bet
                msg += f"💸 {player.user_name} -{self.bet} 积分\n"
            # 平局，不扣分

        # 更新庄家积分
        if total_creator_change != 0:
            points_manager.add_points(self.group_id, self.creator_id, total_creator_change)
            if total_creator_change > 0:
                msg += f"━━━━━━━━━━━━━━\n🏆 庄家 {self.creator_name} +{total_creator_change} 积分"
            else:
                msg += f"━━━━━━━━━━━━━━\n💸 庄家 {self.creator_name} {total_creator_change} 积分"

        return msg


# 全局游戏管理
class GameManager:
    """游戏管理器"""

    def __init__(self):
        """初始化游戏管理器"""
        self.games: Dict[str, Dict[int, BlackjackGame]] = {}
        self.next_game_id: Dict[str, int] = {}

    def create_game(self, group_id: str, creator_id: str, creator_name: str, bet: int, max_players: int = 1) -> int:
        """
        创建游戏

        Args:
            group_id: 群号
            creator_id: 创建者QQ号
            creator_name: 创建者昵称
            bet: 赌注
            max_players: 最大玩家数

        Returns:
            游戏ID
        """
        if group_id not in self.games:
            self.games[group_id] = {}
            self.next_game_id[group_id] = 1

        game_id = self.next_game_id[group_id]
        self.games[group_id][game_id] = BlackjackGame(group_id, creator_id, creator_name, bet, max_players)
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
                if game.creator_id == user_id:
                    return game
                for player in game.players:
                    if player.user_id == user_id:
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
