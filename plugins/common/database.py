"""
数据库工具模块
使用 SQLite 存储数据
"""
import aiosqlite
from pathlib import Path
from typing import List, Optional, Tuple
import json

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "bot.db"


async def init_db():
    """初始化数据库表"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 群友语录表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 签到表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                user_name TEXT NOT NULL,
                checkin_date DATE NOT NULL,
                continuous_days INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, user_id, checkin_date)
            )
        """)

        # 群老婆表（每日重置）
        await db.execute("""
            CREATE TABLE IF NOT EXISTS waifu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                waifu_id TEXT NOT NULL,
                waifu_name TEXT NOT NULL,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(group_id, user_id, date)
            )
        """)

        # Steam账号绑定表
        await db.execute("""
            CREATE TABLE IF NOT EXISTS steam_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                qq_id TEXT NOT NULL UNIQUE,
                steam_id TEXT NOT NULL,
                steam_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


class QuoteDB:
    """群友语录数据库操作"""

    @staticmethod
    async def add_quote(group_id: str, user_id: str, user_name: str, content: str) -> bool:
        """添加语录"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT INTO quotes (group_id, user_id, user_name, content) VALUES (?, ?, ?, ?)",
                    (group_id, user_id, user_name, content)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"添加语录失败: {e}")
            return False

    @staticmethod
    async def get_random_quote(group_id: str, user_id: Optional[str] = None) -> Optional[dict]:
        """获取随机语录"""
        async with aiosqlite.connect(DB_PATH) as db:
            if user_id:
                cursor = await db.execute(
                    "SELECT user_id, user_name, content FROM quotes WHERE group_id = ? AND user_id = ? ORDER BY RANDOM() LIMIT 1",
                    (group_id, user_id)
                )
            else:
                cursor = await db.execute(
                    "SELECT user_id, user_name, content FROM quotes WHERE group_id = ? ORDER BY RANDOM() LIMIT 1",
                    (group_id,)
                )
            row = await cursor.fetchone()
            if row:
                return {"user_id": row[0], "user_name": row[1], "content": row[2]}
            return None

    @staticmethod
    async def delete_quote(group_id: str, user_id: str, content: str) -> bool:
        """删除语录"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "DELETE FROM quotes WHERE group_id = ? AND user_id = ? AND content = ? LIMIT 1",
                    (group_id, user_id, content)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"删除语录失败: {e}")
            return False

    @staticmethod
    async def get_user_quote_count(group_id: str, user_id: str) -> int:
        """获取用户语录数量"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM quotes WHERE group_id = ? AND user_id = ?",
                (group_id, user_id)
            )
            row = await cursor.fetchone()
            return row[0] if row else 0


class CheckinDB:
    """签到数据库操作"""

    @staticmethod
    async def checkin(group_id: str, user_id: str, user_name: str) -> Tuple[bool, int]:
        """
        签到
        返回: (是否成功, 连续签到天数)
        """
        from datetime import date, timedelta

        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            # 检查今天是否已签到
            cursor = await db.execute(
                "SELECT id FROM checkins WHERE group_id = ? AND user_id = ? AND checkin_date = ?",
                (group_id, user_id, today)
            )
            if await cursor.fetchone():
                return False, 0

            # 检查昨天是否签到
            cursor = await db.execute(
                "SELECT continuous_days FROM checkins WHERE group_id = ? AND user_id = ? AND checkin_date = ?",
                (group_id, user_id, yesterday)
            )
            row = await cursor.fetchone()
            continuous_days = (row[0] + 1) if row else 1

            # 插入今天的签到记录
            await db.execute(
                "INSERT INTO checkins (group_id, user_id, user_name, checkin_date, continuous_days) VALUES (?, ?, ?, ?, ?)",
                (group_id, user_id, user_name, today, continuous_days)
            )
            await db.commit()

            return True, continuous_days

    @staticmethod
    async def get_user_checkin_info(group_id: str, user_id: str) -> Optional[dict]:
        """获取用户签到信息"""
        from datetime import date
        today = date.today().isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT continuous_days, checkin_date FROM checkins WHERE group_id = ? AND user_id = ? ORDER BY checkin_date DESC LIMIT 1",
                (group_id, user_id)
            )
            row = await cursor.fetchone()
            if row:
                return {
                    "continuous_days": row[0],
                    "is_today": row[1] == today
                }
            return None

    @staticmethod
    async def get_group_checkin_rank(group_id: str, limit: int = 10) -> List[dict]:
        """获取群签到排行榜"""
        from datetime import date
        today = date.today().isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                """SELECT user_id, user_name, continuous_days
                   FROM checkins
                   WHERE group_id = ? AND checkin_date = ?
                   ORDER BY continuous_days DESC
                   LIMIT ?""",
                (group_id, today, limit)
            )
            rows = await cursor.fetchall()
            return [{"user_id": r[0], "user_name": r[1], "days": r[2]} for r in rows]


class WaifuDB:
    """群老婆数据库操作"""

    @staticmethod
    async def set_waifu(group_id: str, user_id: str, waifu_id: str, waifu_name: str) -> bool:
        """设置今日老婆"""
        from datetime import date
        today = date.today().isoformat()

        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO waifu (group_id, user_id, waifu_id, waifu_name, date) VALUES (?, ?, ?, ?, ?)",
                    (group_id, user_id, waifu_id, waifu_name, today)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"设置群老婆失败: {e}")
            return False

    @staticmethod
    async def get_waifu(group_id: str, user_id: str) -> Optional[dict]:
        """获取今日老婆"""
        from datetime import date
        today = date.today().isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT waifu_id, waifu_name FROM waifu WHERE group_id = ? AND user_id = ? AND date = ?",
                (group_id, user_id, today)
            )
            row = await cursor.fetchone()
            if row:
                return {"waifu_id": row[0], "waifu_name": row[1]}
            return None

    @staticmethod
    async def check_waifu_taken(group_id: str, waifu_id: str) -> Optional[str]:
        """检查老婆是否已被抢走"""
        from datetime import date
        today = date.today().isoformat()

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id FROM waifu WHERE group_id = ? AND waifu_id = ? AND date = ?",
                (group_id, waifu_id, today)
            )
            row = await cursor.fetchone()
            return row[0] if row else None


class SteamDB:
    """Steam账号绑定数据库操作"""

    @staticmethod
    async def bind_steam(qq_id: str, steam_id: str, steam_name: str = None) -> bool:
        """绑定Steam账号"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "INSERT OR REPLACE INTO steam_bindings (qq_id, steam_id, steam_name, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                    (qq_id, steam_id, steam_name)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"绑定Steam账号失败: {e}")
            return False

    @staticmethod
    async def unbind_steam(qq_id: str) -> bool:
        """解绑Steam账号"""
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute(
                    "DELETE FROM steam_bindings WHERE qq_id = ?",
                    (qq_id,)
                )
                await db.commit()
                return True
        except Exception as e:
            print(f"解绑Steam账号失败: {e}")
            return False

    @staticmethod
    async def get_steam_binding(qq_id: str) -> Optional[dict]:
        """获取Steam绑定信息"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT steam_id, steam_name FROM steam_bindings WHERE qq_id = ?",
                (qq_id,)
            )
            row = await cursor.fetchone()
            if row:
                return {"steam_id": row[0], "steam_name": row[1]}
            return None

    @staticmethod
    async def get_all_bindings() -> List[dict]:
        """获取所有Steam绑定信息"""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT qq_id, steam_id, steam_name FROM steam_bindings ORDER BY created_at"
            )
            rows = await cursor.fetchall()
            return [{"qq_id": r[0], "steam_id": r[1], "steam_name": r[2]} for r in rows]
