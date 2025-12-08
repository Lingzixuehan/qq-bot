"""
Steam数据管理模块
用于管理绑定数据、Steam信息缓存、群组配置等
"""
import json
import time
from PIL import Image
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple

from .models import Player, ProcessedPlayer


class BindData:
    """绑定数据管理类"""

    def __init__(self, save_path: Path) -> None:
        self.content: Dict[str, List[Dict[str, str]]] = {}
        self._save_path = save_path

        if save_path.exists():
            self.content = json.loads(Path(save_path).read_text("utf-8"))
        else:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()

    def save(self) -> None:
        """保存到文件"""
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4, ensure_ascii=False)

    def add(self, parent_id: str, content: Dict[str, str]) -> None:
        """添加绑定"""
        if parent_id not in self.content:
            self.content[parent_id] = [content]
        else:
            self.content[parent_id].append(content)

    def remove(self, parent_id: str, user_id: str) -> None:
        """移除绑定"""
        if parent_id not in self.content:
            return
        for data in self.content[parent_id]:
            if data["user_id"] == user_id:
                self.content[parent_id].remove(data)
                break

    def update(self, parent_id: str, content: Dict[str, str]) -> None:
        """更新绑定"""
        self.content[parent_id] = content

    def get(self, parent_id: str, user_id: str) -> Optional[Dict[str, str]]:
        """获取指定用户的绑定"""
        if parent_id not in self.content:
            return None
        for data in self.content[parent_id]:
            if data["user_id"] == user_id:
                if not data.get("nickname"):
                    data["nickname"] = None
                return data
        return None

    def get_by_steam_id(
        self, parent_id: str, steam_id: str
    ) -> Optional[Dict[str, str]]:
        """通过Steam ID获取绑定"""
        if parent_id not in self.content:
            return None
        for data in self.content[parent_id]:
            if data["steam_id"] == steam_id:
                if not data.get("nickname"):
                    data["nickname"] = None
                return data
        return None

    def get_all(self, parent_id: str) -> List[str]:
        """获取群组内所有Steam ID"""
        if parent_id not in self.content:
            return []

        result = []
        for data in self.content[parent_id]:
            if data["steam_id"] not in result:
                result.append(data["steam_id"])

        return result

    def get_all_steam_id(self) -> List[str]:
        """获取所有Steam ID"""
        result = []
        for parent_id in self.content:
            for data in self.content[parent_id]:
                if data["steam_id"] not in result:
                    result.append(data["steam_id"])
        return result


class SteamInfoData:
    """Steam信息缓存管理类"""

    def __init__(self, save_path: Path) -> None:
        self.content: List[ProcessedPlayer] = []
        self._save_path = save_path

        if save_path.exists():
            self.content = json.loads(save_path.read_text("utf-8"))
            if isinstance(self.content, dict):
                self.content = []
            self.save()
        else:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()

    def save(self) -> None:
        """保存到文件"""
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4, ensure_ascii=False)

    def update(self, player: ProcessedPlayer) -> None:
        """更新玩家信息"""
        self.content.append(player)

    def update_by_players(self, players: List[Player]):
        """通过玩家列表批量更新"""
        # 将Player转换为ProcessedPlayer
        processed_players = []
        for player in players:
            old_player = self.get_player(player["steamid"])

            # 创建ProcessedPlayer
            processed_player: ProcessedPlayer = {**player, "game_start_time": None}  # type: ignore

            if old_player is None:
                if player.get("gameextrainfo") is not None:
                    processed_player["game_start_time"] = int(time.time())
                else:
                    processed_player["game_start_time"] = None
                processed_players.append(processed_player)
            else:
                if (
                    player.get("gameextrainfo") is not None
                    and old_player.get("gameextrainfo") is None
                ):
                    # 游戏开始
                    processed_player["game_start_time"] = int(time.time())
                elif (
                    player.get("gameextrainfo") is None
                    and old_player.get("gameextrainfo") is not None
                ):
                    # 游戏结束
                    processed_player["game_start_time"] = None
                elif (
                    player.get("gameextrainfo") is not None
                    and old_player.get("gameextrainfo") is not None
                ):
                    if player.get("gameextrainfo") != old_player.get("gameextrainfo"):
                        # 游戏切换
                        processed_player["game_start_time"] = int(time.time())
                    else:
                        # 游戏继续
                        processed_player["game_start_time"] = old_player.get("game_start_time")
                else:
                    processed_player["game_start_time"] = None
                processed_players.append(processed_player)

        self.content = processed_players

    def get_player(self, steam_id: str) -> Optional[ProcessedPlayer]:
        """获取指定玩家信息"""
        for player in self.content:
            if player["steamid"] == steam_id:
                return player
        return None

    def get_players(self, steam_ids: List[str]) -> List[ProcessedPlayer]:
        """获取多个玩家信息"""
        result = []
        for player in self.content:
            if player["steamid"] in steam_ids:
                result.append(player)
        return result

    def compare(
        self, old_players: List[ProcessedPlayer], new_players: List[ProcessedPlayer]
    ) -> List[Dict[str, Any]]:
        """比较新旧玩家状态，返回变化列表"""
        result = []

        for player in new_players:
            for old_player in old_players:
                if player["steamid"] == old_player["steamid"]:
                    if player.get("gameextrainfo") != old_player.get("gameextrainfo"):
                        if (
                            player.get("gameextrainfo") is not None
                            and old_player.get("gameextrainfo") is not None
                        ):
                            result.append(
                                {
                                    "type": "change",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
                        elif old_player.get("gameextrainfo") is not None:
                            result.append(
                                {
                                    "type": "stop",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
                        elif player.get("gameextrainfo") is not None:
                            result.append(
                                {
                                    "type": "start",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
                        else:
                            result.append(
                                {
                                    "type": "error",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
        return result


class ParentData:
    """群组数据管理类"""

    def __init__(self, save_path: Path) -> None:
        self.content: Dict[str, str] = {}  # parent_id: name
        self._save_path = save_path

        if not save_path.exists():
            save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()
        else:
            self.content = json.loads(save_path.read_text("utf-8"))

    def save(self) -> None:
        """保存到文件"""
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4, ensure_ascii=False)

    def update(self, parent_id: str, avatar: Image.Image, name: str) -> None:
        """更新群组信息"""
        self.content[parent_id] = name
        self.save()
        # 保存头像
        avatar_path = self._save_path.parent / f"{parent_id}.png"
        avatar.save(avatar_path)

    def get(self, parent_id: str) -> Tuple[Image.Image, str]:
        """获取群组信息"""
        if parent_id not in self.content:
            # 返回默认头像
            default_avatar_path = Path(__file__).parent / "res/unknown_avatar.jpg"
            return (
                Image.open(default_avatar_path),
                parent_id,
            )
        avatar_path = self._save_path.parent / f"{parent_id}.png"
        return Image.open(avatar_path), self.content[parent_id]


class DisableParentData:
    """禁用播报的群组管理类"""

    def __init__(self, save_path: Path) -> None:
        self.content: List[str] = []
        self._save_path = save_path

        if save_path.exists():
            self.content = json.loads(save_path.read_text("utf-8"))
        else:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()

    def save(self) -> None:
        """保存到文件"""
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4, ensure_ascii=False)

    def add(self, parent_id: str) -> None:
        """添加禁用群组"""
        if parent_id not in self.content:
            self.content.append(parent_id)
            self.save()

    def remove(self, parent_id: str) -> None:
        """移除禁用群组"""
        if parent_id in self.content:
            self.content.remove(parent_id)
            self.save()

    def is_disabled(self, parent_id: str) -> bool:
        """检查群组是否禁用播报"""
        return parent_id in self.content


class SubscriptionData:
    """订阅信息管理类"""

    def __init__(self, save_path: Path) -> None:
        self.content: Dict[str, List[str]] = {"freebie": [], "discount": []}
        self._save_path = save_path

        if save_path.exists():
            try:
                data = json.loads(save_path.read_text("utf-8"))
                if isinstance(data, dict):
                    self.content.update({k: v for k, v in data.items() if isinstance(v, list)})
            except Exception:
                # 数据异常则覆盖
                self.content = {"freebie": [], "discount": []}
                self.save()
        else:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()

    def save(self) -> None:
        """保存订阅数据"""
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4, ensure_ascii=False)

    def add(self, parent_id: str, category: str) -> None:
        """添加订阅"""
        if category not in self.content:
            self.content[category] = []
        if parent_id not in self.content[category]:
            self.content[category].append(parent_id)
            self.save()

    def remove(self, parent_id: str, category: str) -> None:
        """移除订阅"""
        if category not in self.content:
            return
        if parent_id in self.content[category]:
            self.content[category].remove(parent_id)
            self.save()

    def get(self, category: str) -> List[str]:
        """获取订阅列表"""
        return self.content.get(category, [])
