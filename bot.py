#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QQ Bot 主程序
基于 NoneBot2 + NapCat
"""
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

# 初始化 NoneBot
nonebot.init()

# 注册适配器
driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)

# 加载插件（只加载一次）
nonebot.load_plugins("plugins")

# 数据库初始化（在插件加载后注册）
@driver.on_startup
async def startup():
    """启动时初始化数据库"""
    from plugins.common.database import init_db
    await init_db()

if __name__ == "__main__":
    nonebot.run()
