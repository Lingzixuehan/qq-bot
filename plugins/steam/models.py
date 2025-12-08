"""
Steam数据模型定义
"""
from typing import TypedDict, List, Optional


class Player(TypedDict, total=False):
    """Steam玩家基本信息"""
    steamid: str
    communityvisibilitystate: int
    profilestate: int
    personaname: str
    profileurl: str
    avatar: str
    avatarmedium: str
    avatarfull: str
    avatarhash: str
    lastlogoff: int
    personastate: int
    realname: str
    primaryclanid: str
    timecreated: int
    personastateflags: int
    gameextrainfo: Optional[str]  # 当前游戏名称
    gameid: Optional[str]  # 当前游戏ID


class ProcessedPlayer(Player):
    """处理后的玩家信息（包含游戏开始时间）"""
    game_start_time: Optional[int]  # Unix时间戳


class PlayerSummariesResponse(TypedDict):
    """Steam API玩家摘要响应"""
    players: List[Player]


class PlayerSummaries(TypedDict):
    """Steam API玩家摘要完整响应"""
    response: PlayerSummariesResponse


class PlayerSummariesProcessedResponse(TypedDict):
    """处理后的玩家摘要响应"""
    players: List[ProcessedPlayer]


class Achievements(TypedDict):
    """成就信息"""
    name: str
    image: bytes


class GameData(TypedDict):
    """游戏数据"""
    game_name: str
    play_time: str
    last_played: str
    game_image: bytes
    achievements: List[Achievements]
    completed_achievement_number: int
    total_achievement_number: int


class PlayerData(TypedDict):
    """完整的玩家数据"""
    steamid: str
    player_name: str
    background: bytes
    avatar: bytes
    description: str
    recent_2_week_play_time: str
    game_data: List[GameData]


class DrawPlayerStatusData(TypedDict):
    """绘制玩家状态所需的数据"""
    game_name: str
    game_time: str
    last_play_time: str
    game_header: bytes
    achievements: List[Achievements]
    completed_achievement_number: int
    total_achievement_number: int
