"""
德州扑克游戏逻辑
"""
import asyncio
from enum import IntEnum
from typing import Dict, List, Optional, Tuple, Callable
from .card import TexasCard, TexasDeck, CommunityCards
from .hand_evaluator import HandEvaluator
from ..blackjack.points_manager import points_manager


class BettingRound(IntEnum):
    """下注轮次"""
    PRE_FLOP = 1    # 翻牌前
    FLOP = 2        # 翻牌
    TURN = 3        # 转牌
    RIVER = 4       # 河牌
    SHOWDOWN = 5    # 摊牌


class TexasPlayer:
    """德州扑克玩家"""

    def __init__(self, user_id: str, user_name: str, chips: int):
        self.user_id = user_id
        self.user_name = user_name
        self.hole_cards: List[TexasCard] = []  # 手牌（2张）
        self.chips = chips                      # 当前筹码
        self.bet_this_round = 0                # 本轮下注额
        self.total_bet = 0                     # 总下注额
        self.folded = False                    # 是否弃牌
        self.all_in = False                    # 是否全下
        self.acted_this_round = False          # 本轮是否已操作


class TexasHoldemGame:
    """德州扑克游戏类"""

    def __init__(self, group_id: str, creator_id: str, creator_name: str,
                 buy_in: int, small_blind: int, big_blind: int, max_players: int = 6):
        """
        初始化游戏

        Args:
            group_id: 群号
            creator_id: 创建者QQ号
            creator_name: 创建者昵称
            buy_in: 买入金额
            small_blind: 小盲注
            big_blind: 大盲注
            max_players: 最大玩家数（2-9）
        """
        self.group_id = group_id
        self.creator_id = creator_id
        self.creator_name = creator_name
        self.buy_in = buy_in
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.max_players = min(max_players, 9)  # 最多9人

        # 游戏状态
        self.players: List[TexasPlayer] = []
        self.deck = TexasDeck()
        self.community_cards = CommunityCards()
        self.pot = 0                           # 底池
        self.current_bet = 0                   # 当前需要跟注的金额
        self.current_round = BettingRound.PRE_FLOP
        self.current_player_idx = 0            # 当前操作玩家索引
        self.dealer_button = 0                 # 庄家按钮位置
        self.started = False
        self.finished = False

        # 超时相关
        self.timeout_task: Optional[asyncio.Task] = None
        self.timeout_callback: Optional[Callable] = None
        self.timeout_duration = 30

    def add_player(self, user_id: str, user_name: str) -> Tuple[bool, str]:
        """
        添加玩家

        Args:
            user_id: 玩家QQ号
            user_name: 玩家昵称

        Returns:
            (是否成功, 消息)
        """
        if self.started:
            return False, "游戏已经开始了！"

        if len(self.players) >= self.max_players:
            return False, "游戏已满员！"

        # 检查是否已经加入
        for player in self.players:
            if player.user_id == user_id:
                return False, "你已经加入了这个游戏！"

        # 检查积分是否足够
        points = points_manager.get_points(self.group_id, user_id)
        if points < self.buy_in:
            return False, f"积分不足！需要 {self.buy_in} 积分，当前只有 {points} 积分。"

        # 扣除积分，转换为筹码
        points_manager.add_points(self.group_id, user_id, -self.buy_in)

        player = TexasPlayer(user_id, user_name, self.buy_in)
        self.players.append(player)

        return True, f"{user_name} 加入游戏！({len(self.players)}/{self.max_players})"

    def start_game(self) -> str:
        """
        开始游戏

        Returns:
            开始游戏的消息
        """
        if self.started:
            return "游戏已经开始了！"

        if len(self.players) < 2:
            return "至少需要2名玩家才能开始游戏！"

        self.started = True

        # 发手牌
        for _ in range(2):
            for player in self.players:
                player.hole_cards.append(self.deck.deal())

        # 设置盲注
        sb_idx = (self.dealer_button + 1) % len(self.players)
        bb_idx = (self.dealer_button + 2) % len(self.players)

        # 小盲注
        sb_player = self.players[sb_idx]
        sb_amount = min(self.small_blind, sb_player.chips)
        sb_player.chips -= sb_amount
        sb_player.bet_this_round = sb_amount
        sb_player.total_bet = sb_amount
        if sb_player.chips == 0:
            sb_player.all_in = True

        # 大盲注
        bb_player = self.players[bb_idx]
        bb_amount = min(self.big_blind, bb_player.chips)
        bb_player.chips -= bb_amount
        bb_player.bet_this_round = bb_amount
        bb_player.total_bet = bb_amount
        if bb_player.chips == 0:
            bb_player.all_in = True

        self.pot = sb_amount + bb_amount
        self.current_bet = bb_amount

        # 从大盲后一位开始行动
        if len(self.players) == 2:
            # 两人局，小盲先行动
            self.current_player_idx = sb_idx
        else:
            # 多人局，从大盲后一位开始
            self.current_player_idx = (bb_idx + 1) % len(self.players)

        # 构建消息
        msg = "🎮 德州扑克游戏开始！\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += f"💰 买入：{self.buy_in} | 小盲：{self.small_blind} | 大盲：{self.big_blind}\n"
        msg += f"👥 玩家数：{len(self.players)}\n"
        msg += "━━━━━━━━━━━━━━\n"

        for i, player in enumerate(self.players):
            role = ""
            if i == self.dealer_button:
                role = " 🎯庄家"
            elif i == sb_idx:
                role = f" 💵小盲({sb_amount})"
            elif i == bb_idx:
                role = f" 💵大盲({bb_amount})"

            msg += f"玩家{i+1}【{player.user_name}】筹码:{player.chips}{role}\n"

        msg += "━━━━━━━━━━━━━━\n"
        msg += f"🃏 公共牌：暂无\n"
        msg += f"💰 底池：{self.pot}\n"
        msg += "━━━━━━━━━━━━━━\n"

        current = self.players[self.current_player_idx]
        to_call = self.current_bet - current.bet_this_round
        msg += f"💡 轮到 [AT:{current.user_id}] 【{current.user_name}】\n"
        msg += f"当前需跟注：{to_call}\n"
        msg += "可用命令：/弃牌 /跟注 /加注 [金额] /allin"
        if to_call == 0:
            msg += " /过牌"

        # 启动超时计时
        self.start_timeout()

        return msg

    def get_current_player(self) -> Optional[TexasPlayer]:
        """获取当前操作的玩家"""
        if self.finished or not self.started:
            return None

        # 找到下一个需要操作的玩家
        checked = 0
        while checked < len(self.players):
            player = self.players[self.current_player_idx]
            if not player.folded and not player.all_in:
                return player
            self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
            checked += 1

        return None

    def fold(self, user_id: str) -> str:
        """
        玩家弃牌

        Args:
            user_id: 用户ID

        Returns:
            操作结果消息
        """
        current = self.get_current_player()
        if not current or current.user_id != user_id:
            return "现在不是你的回合！"

        self.cancel_timeout()

        current.folded = True
        msg = f"【{current.user_name}】弃牌\n"

        # 检查是否只剩一人
        if self._check_only_one_left():
            msg += self._end_game_one_winner()
        else:
            msg += self._next_action()

        return msg

    def check(self, user_id: str) -> str:
        """
        玩家过牌

        Args:
            user_id: 用户ID

        Returns:
            操作结果消息
        """
        current = self.get_current_player()
        if not current or current.user_id != user_id:
            return "现在不是你的回合！"

        # 检查是否可以过牌
        to_call = self.current_bet - current.bet_this_round
        if to_call > 0:
            return f"当前需跟注 {to_call}，不能过牌！请使用 /跟注 或 /弃牌"

        self.cancel_timeout()

        current.acted_this_round = True
        msg = f"【{current.user_name}】过牌\n"
        msg += self._next_action()

        return msg

    def call(self, user_id: str) -> str:
        """
        玩家跟注

        Args:
            user_id: 用户ID

        Returns:
            操作结果消息
        """
        current = self.get_current_player()
        if not current or current.user_id != user_id:
            return "现在不是你的回合！"

        self.cancel_timeout()

        to_call = self.current_bet - current.bet_this_round
        if to_call <= 0:
            return "无需跟注，请使用 /过牌"

        # 计算实际跟注金额（可能筹码不足）
        call_amount = min(to_call, current.chips)
        current.chips -= call_amount
        current.bet_this_round += call_amount
        current.total_bet += call_amount
        current.acted_this_round = True
        self.pot += call_amount

        if current.chips == 0:
            current.all_in = True
            msg = f"【{current.user_name}】全下跟注 {call_amount}！\n"
        else:
            msg = f"【{current.user_name}】跟注 {call_amount}\n"

        msg += self._next_action()

        return msg

    def raise_bet(self, user_id: str, raise_amount: int) -> str:
        """
        玩家加注

        Args:
            user_id: 用户ID
            raise_amount: 加注金额（总下注额，不是增加额）

        Returns:
            操作结果消息
        """
        current = self.get_current_player()
        if not current or current.user_id != user_id:
            return "现在不是你的回合！"

        # 检查加注金额是否有效
        to_call = self.current_bet - current.bet_this_round
        min_raise = self.current_bet + self.big_blind

        if raise_amount <= self.current_bet:
            return f"加注金额必须大于当前下注额 {self.current_bet}！"

        total_needed = raise_amount - current.bet_this_round
        if total_needed > current.chips:
            return f"筹码不足！你只有 {current.chips} 筹码。使用 /allin 全下。"

        if raise_amount < min_raise and total_needed < current.chips:
            return f"加注金额至少为 {min_raise}！"

        self.cancel_timeout()

        # 执行加注
        current.chips -= total_needed
        current.bet_this_round = raise_amount
        current.total_bet += total_needed
        current.acted_this_round = True
        self.pot += total_needed
        self.current_bet = raise_amount

        # 重置其他玩家的行动状态（需要重新跟注）
        for player in self.players:
            if player != current and not player.folded and not player.all_in:
                player.acted_this_round = False

        if current.chips == 0:
            current.all_in = True
            msg = f"【{current.user_name}】全下 {raise_amount}！\n"
        else:
            msg = f"【{current.user_name}】加注到 {raise_amount}\n"

        msg += self._next_action()

        return msg

    def all_in(self, user_id: str) -> str:
        """
        玩家全下

        Args:
            user_id: 用户ID

        Returns:
            操作结果消息
        """
        current = self.get_current_player()
        if not current or current.user_id != user_id:
            return "现在不是你的回合！"

        if current.chips == 0:
            return "你已经全下了！"

        self.cancel_timeout()

        # 全下所有筹码
        all_in_amount = current.chips
        new_total_bet = current.bet_this_round + all_in_amount

        current.chips = 0
        current.bet_this_round = new_total_bet
        current.total_bet += all_in_amount
        current.all_in = True
        current.acted_this_round = True
        self.pot += all_in_amount

        # 如果全下金额超过当前下注，更新当前下注并重置其他玩家状态
        if new_total_bet > self.current_bet:
            self.current_bet = new_total_bet
            for player in self.players:
                if player != current and not player.folded and not player.all_in:
                    player.acted_this_round = False

        msg = f"【{current.user_name}】全下 {all_in_amount}！(总下注 {new_total_bet})\n"
        msg += self._next_action()

        return msg

    def _next_action(self) -> str:
        """
        移动到下一个玩家或下一轮

        Returns:
            状态消息
        """
        # 检查本轮是否结束
        if self._is_round_finished():
            return self._next_round()

        # 移动到下一个玩家
        self.current_player_idx = (self.current_player_idx + 1) % len(self.players)
        current = self.get_current_player()

        if not current:
            # 所有人都全下或弃牌，直接进入下一轮
            return self._next_round()

        # 显示当前玩家信息
        to_call = self.current_bet - current.bet_this_round
        msg = f"💡 轮到 [AT:{current.user_id}] 【{current.user_name}】\n"
        msg += f"当前需跟注：{to_call}\n"
        msg += "可用命令：/弃牌 /跟注 /加注 [金额] /allin"
        if to_call == 0:
            msg += " /过牌"

        self.start_timeout()

        return msg

    def _is_round_finished(self) -> bool:
        """检查当前轮是否结束"""
        active_players = [p for p in self.players if not p.folded and not p.all_in]

        # 只剩0-1个活跃玩家
        if len(active_players) <= 1:
            return True

        # 所有活跃玩家都已操作且下注相同
        for player in active_players:
            if not player.acted_this_round:
                return False
            if player.bet_this_round != self.current_bet:
                return False

        return True

    def _next_round(self) -> str:
        """
        进入下一轮

        Returns:
            下一轮的消息
        """
        self.cancel_timeout()

        # 重置玩家状态
        for player in self.players:
            player.bet_this_round = 0
            player.acted_this_round = False

        self.current_bet = 0

        # 进入下一阶段
        if self.current_round == BettingRound.PRE_FLOP:
            # 发翻牌
            self.current_round = BettingRound.FLOP
            flop = [self.deck.deal(), self.deck.deal(), self.deck.deal()]
            self.community_cards.add_flop(flop)

            msg = "━━━━━━━━━━━━━━\n"
            msg += f"🃏 翻牌：{self.community_cards}\n"
            msg += f"💰 底池：{self.pot}\n"
            msg += "━━━━━━━━━━━━━━\n"

        elif self.current_round == BettingRound.FLOP:
            # 发转牌
            self.current_round = BettingRound.TURN
            turn = self.deck.deal()
            self.community_cards.add_turn(turn)

            msg = "━━━━━━━━━━━━━━\n"
            msg += f"🃏 转牌：{self.community_cards}\n"
            msg += f"💰 底池：{self.pot}\n"
            msg += "━━━━━━━━━━━━━━\n"

        elif self.current_round == BettingRound.TURN:
            # 发河牌
            self.current_round = BettingRound.RIVER
            river = self.deck.deal()
            self.community_cards.add_river(river)

            msg = "━━━━━━━━━━━━━━\n"
            msg += f"🃏 河牌：{self.community_cards}\n"
            msg += f"💰 底池：{self.pot}\n"
            msg += "━━━━━━━━━━━━━━\n"

        elif self.current_round == BettingRound.RIVER:
            # 摊牌
            return self._showdown()

        else:
            return "游戏已结束！"

        # 从小盲位置开始（如果还在游戏中）
        sb_idx = (self.dealer_button + 1) % len(self.players)
        self.current_player_idx = sb_idx
        current = self.get_current_player()

        if not current:
            # 所有人都全下或弃牌，继续发牌
            return msg + self._next_round()

        to_call = self.current_bet - current.bet_this_round
        msg += f"💡 轮到 [AT:{current.user_id}] 【{current.user_name}】\n"
        msg += f"当前需跟注：{to_call}\n"
        msg += "可用命令：/弃牌 /加注 [金额] /allin /过牌"

        self.start_timeout()

        return msg

    def _check_only_one_left(self) -> bool:
        """检查是否只剩一个玩家"""
        active_players = [p for p in self.players if not p.folded]
        return len(active_players) == 1

    def _end_game_one_winner(self) -> str:
        """
        只剩一个玩家时结束游戏

        Returns:
            结算消息
        """
        self.cancel_timeout()
        self.finished = True

        winner = next(p for p in self.players if not p.folded)
        winner.chips += self.pot

        msg = "━━━━━━━━━━━━━━\n"
        msg += f"🎊 【{winner.user_name}】获胜！（其他玩家已弃牌）\n"

        # 显示当前公共牌（如果有）
        if len(self.community_cards) > 0:
            # 判断游戏进行到哪个阶段
            stage = ""
            if len(self.community_cards) == 3:
                stage = "（翻牌圈）"
            elif len(self.community_cards) == 4:
                stage = "（转牌圈）"
            elif len(self.community_cards) == 5:
                stage = "（河牌圈）"

            msg += f"🃏 公共牌：{self.community_cards}{stage}\n"

        msg += f"💰 赢得底池：{self.pot}\n"
        msg += "━━━━━━━━━━━━━━\n"
        msg += self._settle_game()

        return msg

    def _showdown(self) -> str:
        """
        摊牌比大小

        Returns:
            摊牌结果消息
        """
        self.cancel_timeout()
        self.finished = True

        # 获取所有未弃牌的玩家
        active_players = [p for p in self.players if not p.folded]

        # 评估每个玩家的手牌
        player_hands = []
        for player in active_players:
            rank, values, best_cards = HandEvaluator.evaluate_best_hand(
                player.hole_cards,
                self.community_cards.get_cards()
            )
            player_hands.append((player, rank, values, best_cards))

        # 排序（最好的在前）
        player_hands.sort(key=lambda x: (x[1], x[2]), reverse=True)

        # 显示所有玩家的手牌
        msg = "━━━━━━━━━━━━━━\n"
        msg += "🎴 摊牌！\n"
        msg += f"🃏 公共牌：{self.community_cards}\n"
        msg += "━━━━━━━━━━━━━━\n"

        for player, rank, values, best_cards in player_hands:
            hand_desc = HandEvaluator.get_hand_description(rank, values, best_cards)
            hole_str = " ".join(str(card) for card in player.hole_cards)
            msg += f"【{player.user_name}】\n"
            msg += f"  手牌：{hole_str}\n"
            msg += f"  牌型：{hand_desc}\n"

        msg += "━━━━━━━━━━━━━━\n"

        # 分配底池（简化版：暂不处理边池）
        winners = [player_hands[0]]
        for i in range(1, len(player_hands)):
            if player_hands[i][1] == winners[0][1] and player_hands[i][2] == winners[0][2]:
                winners.append(player_hands[i])
            else:
                break

        # 平分底池
        win_amount = self.pot // len(winners)
        remainder = self.pot % len(winners)

        if len(winners) == 1:
            winner = winners[0][0]
            winner.chips += self.pot
            msg += f"🎊 【{winner.user_name}】获胜！\n"
            msg += f"💰 赢得底池：{self.pot}\n"
        else:
            msg += f"🤝 平局！{len(winners)} 位玩家平分底池\n"
            for i, (player, _, _, _) in enumerate(winners):
                amount = win_amount + (1 if i < remainder else 0)
                player.chips += amount
                msg += f"【{player.user_name}】获得 {amount}\n"

        msg += "━━━━━━━━━━━━━━\n"
        msg += self._settle_game()

        return msg

    def _settle_game(self) -> str:
        """
        结算游戏，将筹码转回积分

        Returns:
            结算消息
        """
        msg = "📊 最终结算：\n"

        for player in self.players:
            points_manager.add_points(self.group_id, player.user_id, player.chips)
            profit = player.chips - self.buy_in
            if profit > 0:
                msg += f"【{player.user_name}】+{profit} (总积分: {points_manager.get_points(self.group_id, player.user_id)})\n"
            elif profit < 0:
                msg += f"【{player.user_name}】{profit} (总积分: {points_manager.get_points(self.group_id, player.user_id)})\n"
            else:
                msg += f"【{player.user_name}】±0 (总积分: {points_manager.get_points(self.group_id, player.user_id)})\n"

        return msg

    def get_game_status(self) -> str:
        """
        获取当前游戏状态

        Returns:
            游戏状态消息
        """
        if not self.started:
            msg = "游戏尚未开始\n"
            msg += f"当前玩家：{len(self.players)}/{self.max_players}\n"
            for i, player in enumerate(self.players):
                msg += f"  {i+1}. {player.user_name}\n"
            return msg

        msg = "━━━━━━━━━━━━━━\n"
        msg += f"🃏 公共牌：{self.community_cards}\n"
        msg += f"💰 底池：{self.pot}\n"
        msg += "━━━━━━━━━━━━━━\n"

        for i, player in enumerate(self.players):
            status = ""
            if player.folded:
                status = " [已弃牌]"
            elif player.all_in:
                status = " [全下]"
            elif i == self.current_player_idx:
                status = " [当前]"

            msg += f"【{player.user_name}】筹码:{player.chips} | 本轮下注:{player.bet_this_round}{status}\n"

        return msg

    def start_timeout(self):
        """启动超时计时"""
        if self.timeout_callback:
            self.timeout_task = asyncio.create_task(self._timeout_handler())

    def cancel_timeout(self):
        """取消超时计时"""
        if self.timeout_task:
            self.timeout_task.cancel()
            self.timeout_task = None

    async def _timeout_handler(self):
        """超时处理器"""
        try:
            await asyncio.sleep(self.timeout_duration)
            if self.timeout_callback:
                await self.timeout_callback(self.group_id, self.get_current_player().user_id)
        except asyncio.CancelledError:
            pass

    def auto_fold(self, user_id: str) -> str:
        """
        自动弃牌（超时）

        Args:
            user_id: 用户ID

        Returns:
            操作结果消息
        """
        current = self.get_current_player()
        if not current or current.user_id != user_id:
            return ""

        return f"⏰ 【{current.user_name}】超时自动弃牌\n" + self.fold(user_id)


class GameManager:
    """游戏管理器"""

    def __init__(self):
        # {group_id: {game_id: TexasHoldemGame}}
        self.games: Dict[str, Dict[int, TexasHoldemGame]] = {}
        self.next_game_id = 1

    def create_game(self, group_id: str, creator_id: str, creator_name: str,
                    buy_in: int, small_blind: int, big_blind: int, max_players: int = 6) -> Tuple[bool, int, str]:
        """
        创建游戏

        Returns:
            (是否成功, 游戏ID, 消息)
        """
        if group_id not in self.games:
            self.games[group_id] = {}

        game_id = self.next_game_id
        self.next_game_id += 1

        game = TexasHoldemGame(group_id, creator_id, creator_name, buy_in, small_blind, big_blind, max_players)
        self.games[group_id][game_id] = game

        # 创建者自动加入
        success, msg = game.add_player(creator_id, creator_name)
        if not success:
            del self.games[group_id][game_id]
            return False, 0, msg

        return True, game_id, f"德州扑克游戏创建成功！游戏ID: {game_id}\n{msg}\n其他玩家使用 /加入德扑 {game_id} 加入游戏\n创建者使用 /开始德扑 {game_id} 开始游戏"

    def get_game(self, group_id: str, game_id: int) -> Optional[TexasHoldemGame]:
        """获取游戏"""
        return self.games.get(group_id, {}).get(game_id)

    def get_player_game(self, group_id: str, user_id: str) -> Optional[TexasHoldemGame]:
        """获取玩家当前参与的游戏"""
        for game in self.games.get(group_id, {}).values():
            for player in game.players:
                if player.user_id == user_id and not game.finished:
                    return game
        return None

    def remove_game(self, group_id: str, game_id: int):
        """移除游戏"""
        if group_id in self.games and game_id in self.games[group_id]:
            del self.games[group_id][game_id]

    def get_waiting_games(self, group_id: str) -> List[Tuple[int, TexasHoldemGame]]:
        """获取等待中的游戏列表"""
        games = []
        for game_id, game in self.games.get(group_id, {}).items():
            if not game.started:
                games.append((game_id, game))
        return games

    def get_active_games_count(self, group_id: str) -> int:
        """获取活跃游戏数量（等待中+进行中，不包括已结束）"""
        count = 0
        for game in self.games.get(group_id, {}).values():
            if not game.finished:
                count += 1
        return count


# 全局游戏管理器实例
game_manager = GameManager()
