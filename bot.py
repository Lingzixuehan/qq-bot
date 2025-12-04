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

# 加载插件
nonebot.load_from_toml("pyproject.toml")

# 也可以直接加载插件目录
nonebot.load_plugins("plugins")

if __name__ == "__main__":
    nonebot.run()
