"""公共模块"""
from functools import wraps
from typing import Set
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import GroupMessageEvent

# 读取配置
driver = get_driver()
config = driver.config

# 允许使用游戏和趣味功能的群列表
FUN_ALLOWED_GROUPS: Set[str] = {
    gid.strip()
    for gid in str(getattr(config, "fun_allowed_groups", "") or "").split(",")
    if gid.strip()
}


def require_fun_group():
    """
    装饰器：要求命令只能在指定的群内使用（游戏和趣味功能）
    如果配置为空，则允许所有群使用
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 查找 GroupMessageEvent
            event = None
            for arg in args:
                if isinstance(arg, GroupMessageEvent):
                    event = arg
                    break

            if event is None:
                # 如果没有找到 GroupMessageEvent，直接执行
                return await func(*args, **kwargs)

            # 如果没有配置白名单，允许所有群
            if not FUN_ALLOWED_GROUPS:
                return await func(*args, **kwargs)

            # 检查当前群是否在白名单中
            group_id = str(event.group_id)
            if group_id not in FUN_ALLOWED_GROUPS:
                # 不在白名单中，不执行命令（静默忽略）
                return

            # 在白名单中，正常执行
            return await func(*args, **kwargs)

        return wrapper
    return decorator

