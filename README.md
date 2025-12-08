# QQ Bot 娱乐机器人

基于 **NoneBot2** + **NapCat** 的QQ群娱乐机器人，提供群友语录、群老婆、签到等趣味功能。

## ✨ 功能特性

### 📝 群友语录
- 记录群友的经典发言
- 随机展示语录
- 支持@指定用户查看Ta的语录
- 语录管理（删除等）

### 💕 群老婆系统
- 每日随机抽取群老婆
- 每天0点自动重置
- 避免重复抽取（同一天内）

### ✅ 签到系统
- 每日签到打卡
- 连续签到天数统计
- 签到排行榜

### 🔔 防撤回功能
- 自动监听群消息撤回事件
- 显示被撤回的消息内容
- 支持文本、图片、表情等多种消息类型
- 显示撤回者和撤回时间

### 🎲 投骰子系统
- 基础投骰子（1-10000面可选）
- 多骰子模式（支持 XdY 格式，如 3d6）
- 快捷命令（d6、d20、d100）
- 猜大小小游戏
- D&D风格大成功/大失败提示

### 📖 其他
- 完整的帮助菜单
- 命令支持带/或不带/前缀

## 🚀 快速开始

### 前置要求

1. **Python 3.8+**
2. **NapCat** - QQ协议端
3. **QQ账号** - 用作机器人的账号

### 安装步骤

#### 1. 安装依赖

```bash
# 克隆项目（如果需要）
git clone <your-repo-url>
cd qq-bot

# 安装Python依赖
pip install -r requirements.txt
```

#### 2. 配置环境变量

复制 `.env.example` 到 `.env`，并修改配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 修改为你的QQ号（超级管理员）
SUPERUSERS=["你的QQ号"]

# 如果NapCat设置了token，填写在这里
ONEBOT_ACCESS_TOKEN="你的token"
```

#### 3. 安装和配置 NapCat

**下载 NapCat：**
- 官方仓库：https://github.com/NapNeko/NapCatQQ
- 下载最新版本并按照官方文档安装

**配置 NapCat：**

编辑 NapCat 的配置文件，添加 HTTP 正向连接：

```json
{
  "http": {
    "enable": true,
    "host": "127.0.0.1",
    "port": 3000,
    "secret": "",
    "enableHeart": true,
    "enablePost": true,
    "postUrls": ["http://127.0.0.1:8080/onebot/v11/"]
  }
}
```

**重要配置说明：**
- `postUrls` 中的端口 `8080` 要和 `.env` 文件中的 `PORT` 一致
- 如果设置了 `secret`，需要在 `.env` 的 `ONEBOT_ACCESS_TOKEN` 中填写相同的值

#### 4. 启动机器人

```bash
# 方式1：直接运行
python bot.py

# 方式2：使用 nb 命令（如果安装了 nb-cli）
nb run
```

#### 5. 启动 NapCat

按照 NapCat 文档启动 QQ 客户端并登录你的机器人账号。

## 📱 使用命令

### 群友语录
```
/添加语录      # 回复一条消息后使用
/语录          # 随机展示语录
/语录 @某人    # 查看某人的语录
/删除语录      # 回复要删除的语录
/我的语录      # 查看自己有多少条语录
```

### 群老婆
```
/抽老婆        # 抽取今日老婆
/查老婆        # 查看今日老婆
```

### 签到
```
/签到          # 每日签到
/签到信息      # 查看签到记录
/签到排行      # 查看排行榜
```

### 防撤回
```
自动功能       # 无需命令，自动监听撤回事件
               # 当有人撤回消息时，机器人会自动发送被撤回的内容
```

### 投骰子
```
/roll          # 投一个6面骰子
/roll 20       # 投一个20面骰子
/roll 3d6      # 投3个6面骰子并求和
/roll 5d10 详细 # 显示每个骰子的点数

# 快捷命令
/d6            # 投一个6面骰子
/d20           # 投一个20面骰子（带大成功/大失败提示）
/d100          # 投一个100面骰子（带幸运提示）

# 小游戏
/猜大小 大     # 猜大小游戏（4-6为大，1-3为小）
/猜大小 小
```

### 帮助
```
/help          # 显示帮助菜单
/帮助
/菜单
```

## 📁 项目结构

```
qq-bot/
├── bot.py                  # 主程序入口
├── .env                    # 配置文件
├── requirements.txt        # Python依赖
├── pyproject.toml         # 项目配置
├── data/                  # 数据存储目录
│   └── bot.db            # SQLite数据库
└── plugins/              # 插件目录
    ├── common/           # 公共模块
    │   └── database.py   # 数据库操作
    ├── quote/            # 群友语录插件
    ├── waifu/            # 群老婆插件
    ├── checkin/          # 签到插件
    ├── anti_recall/      # 防撤回插件
    ├── dice/             # 投骰子插件
    └── help/             # 帮助插件
```

## 🔧 开发指南

### 添加新插件

1. 在 `plugins/` 目录下创建新的插件文件夹
2. 创建 `__init__.py` 文件
3. 使用 NoneBot2 的装饰器编写插件逻辑

示例：

```python
from nonebot import on_command
from nonebot.adapters.onebot.v11 import GroupMessageEvent

hello = on_command("hello", priority=5)

@hello.handle()
async def handle_hello(event: GroupMessageEvent):
    await hello.finish("Hello World!")
```

### 数据库操作

所有数据库操作都在 `plugins/common/database.py` 中定义。使用 SQLite + aiosqlite 实现异步数据库操作。

## 🐛 常见问题

### 1. 机器人没有响应

- 检查 NapCat 是否正常运行
- 检查 `.env` 中的端口配置是否和 NapCat 一致
- 查看控制台日志是否有错误信息

### 2. 连接失败

- 确保 NapCat 的 `postUrls` 配置正确
- 检查防火墙是否阻止了连接
- 确认 `ONEBOT_ACCESS_TOKEN` 配置正确

### 3. 数据库错误

- 确保 `data/` 目录存在且有写入权限
- 首次运行会自动创建数据库

### 4. 提交 PR 时提示 “This branch has conflicts that must be resolved”

当远程分支存在新的提交而当前分支未同步时，GitHub 会提示存在合并冲突。解决方法如下：

1. 拉取最新主分支代码：

   ```bash
   git fetch origin
   git checkout main
   git pull
   ```

2. 切回工作分支并与主分支对齐（任选其一）：

   - 方式 A：合并主分支

     ```bash
     git checkout work
     git merge origin/main
     ```

   - 方式 B：在主分支上变基

     ```bash
     git checkout work
     git rebase origin/main
     ```

3. 按提示手动解决冲突：

   - 打开包含 `<<<<<<<`、`=======`、`>>>>>>>` 标记的文件
   - 保留需要的最终内容，删除冲突标记

4. 解决后提交并推送：

   ```bash
   git add .
   git commit -m "fix: resolve merge conflicts"
   git push -f   # 如果使用了 rebase 需要强推
   ```

完成以上步骤后重新打开或刷新 PR，冲突提示会消失。

## 📝 更新日志

### v1.2.0 (2024-12-04)
- 新增投骰子功能
- 支持基础投骰子（/roll）
- 支持自定义面数和多骰子模式（XdY格式）
- 添加快捷命令（/d6、/d20、/d100）
- 添加猜大小小游戏
- D&D风格大成功/大失败提示

### v1.1.0 (2024-12-04)
- 新增防撤回功能
- 自动监听并显示被撤回的消息
- 支持文本、图片、表情等多种消息类型
- 显示撤回者和撤回时间信息

### v1.0.0 (2024-12-04)
- 实现群友语录功能
- 实现群老婆系统
- 实现签到系统
- 添加帮助菜单

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🔗 相关链接

- [NoneBot2 文档](https://nonebot.dev/)
- [NapCat 项目](https://github.com/NapNeko/NapCatQQ)
- [OneBot 标准](https://onebot.dev/)

## ⚠️ 免责声明

本项目仅供学习交流使用，请勿用于非法用途。使用本项目所产生的一切后果由使用者自行承担。
