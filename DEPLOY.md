# QQ Bot 部署指南

本文档详细说明如何从零开始部署 QQ 机器人。

## 📋 部署流程

### 第一步：准备环境

#### 1.1 安装 Python

确保系统已安装 Python 3.8 或更高版本：

```bash
python3 --version
```

如果没有安装，请访问 [Python官网](https://www.python.org/) 下载安装。

#### 1.2 克隆项目

```bash
git clone <你的仓库地址>
cd qq-bot
```

#### 1.3 安装依赖

```bash
pip install -r requirements.txt
```

或使用虚拟环境（推荐）：

```bash
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

---

### 第二步：安装 NapCat

NapCat 是连接 QQ 和机器人的桥梁。

#### 2.1 下载 NapCat

访问 [NapCat GitHub](https://github.com/NapNeko/NapCatQQ) 下载最新版本。

**推荐方式：使用 Release 版本**

1. 前往 [Releases页面](https://github.com/NapNeko/NapCatQQ/releases)
2. 下载适合你系统的版本
3. 解压到任意目录

#### 2.2 配置 NapCat

在 NapCat 目录中找到配置文件（通常是 `config/onebot11.json`），参考 `napcat-config.example.json` 进行配置：

**关键配置项：**

```json
{
  "http": {
    "enable": true,
    "host": "127.0.0.1",
    "port": 3000,
    "enablePost": true,
    "postUrls": [
      "http://127.0.0.1:8080/onebot/v11/"
    ]
  }
}
```

**注意事项：**
- `postUrls` 中的 `127.0.0.1:8080` 必须和 Bot 的 `.env` 配置一致
- 端口 `8080` 是 Bot 监听的端口（在 `.env` 的 `PORT` 中设置）
- `3000` 是 NapCat 自己的端口，可以自定义

---

### 第三步：配置 Bot

#### 3.1 复制配置文件

```bash
cp .env.example .env
```

#### 3.2 修改 .env

使用文本编辑器打开 `.env` 文件：

```env
# Bot监听地址和端口
HOST=127.0.0.1
PORT=8080

# 日志级别
LOG_LEVEL=INFO

# 超级管理员QQ号（你的QQ号）
SUPERUSERS=["123456789"]

# 如果NapCat设置了token/secret，填写在这里
ONEBOT_ACCESS_TOKEN=""

# 命令前缀
COMMAND_START=["/", ""]
COMMAND_SEP=[" "]
```

**重要配置说明：**

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `PORT` | Bot监听端口，需与NapCat的postUrls一致 | `8080` |
| `SUPERUSERS` | 超级管理员QQ号列表 | `["123456789", "987654321"]` |
| `ONEBOT_ACCESS_TOKEN` | 访问令牌，需与NapCat的secret一致 | `"your_secret_token"` |

---

### 第四步：启动服务

#### 4.1 启动 Bot

在项目目录下运行：

```bash
python bot.py
```

正常启动会看到类似输出：

```
12-04 10:00:00 [INFO] nonebot | NoneBot is initializing...
12-04 10:00:00 [INFO] nonebot | Loaded adapters: OneBot V11
12-04 10:00:01 [INFO] uvicorn | Started server process
12-04 10:00:01 [INFO] uvicorn | Waiting for application startup.
12-04 10:00:01 [INFO] nonebot | Application startup complete.
12-04 10:00:01 [INFO] uvicorn | Uvicorn running on http://127.0.0.1:8080
```

#### 4.2 启动 NapCat

按照 NapCat 的文档启动服务：

1. 启动 NapCat
2. 会自动打开 QQ 登录界面
3. 使用你准备好的机器人 QQ 账号登录
4. 登录成功后，NapCat 会自动连接到 Bot

**验证连接成功：**

在 Bot 的控制台会看到：

```
[INFO] OneBot V11 | WebSocket connected from xxx
```

---

### 第五步：测试功能

#### 5.1 测试帮助命令

在 QQ 群中发送：

```
/help
```

如果机器人回复功能菜单，说明部署成功！

#### 5.2 测试其他功能

```
/签到
/抽老婆
回复某条消息后发送：/添加语录
```

---

## 🔧 进阶配置

### 使用 systemd 守护进程（Linux）

创建服务文件 `/etc/systemd/system/qqbot.service`：

```ini
[Unit]
Description=QQ Bot Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/qq-bot
ExecStart=/usr/bin/python3 /path/to/qq-bot/bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable qqbot
sudo systemctl start qqbot
sudo systemctl status qqbot
```

### 使用 PM2 守护进程（Node.js）

如果你有 Node.js 环境，可以使用 PM2：

```bash
npm install -g pm2
pm2 start bot.py --interpreter python3 --name qqbot
pm2 save
pm2 startup
```

---

## 🐛 故障排查

### 问题1：Bot 无法连接到 NapCat

**症状：** Bot 启动正常，但没有收到 NapCat 的连接

**解决方法：**
1. 检查 NapCat 的 `postUrls` 配置是否正确
2. 确认端口是否被占用：`netstat -tuln | grep 8080`
3. 检查防火墙是否阻止了连接
4. 查看 NapCat 的日志文件

### 问题2：命令没有响应

**症状：** 在群里发送命令，机器人不回复

**解决方法：**
1. 检查 Bot 是否正常连接（查看控制台日志）
2. 确认命令格式是否正确（支持 `/help` 和 `help` 两种格式）
3. 检查是否在群聊中使用（部分功能仅支持群聊）
4. 查看 Bot 日志是否有错误信息

### 问题3：Token 认证失败

**症状：** NapCat 提示 Token 错误

**解决方法：**
1. 确保 `.env` 中的 `ONEBOT_ACCESS_TOKEN` 和 NapCat 的 `secret` 一致
2. 如果不使用 Token，两边都留空
3. 重启 Bot 和 NapCat

### 问题4：数据库错误

**症状：** 提示数据库相关错误

**解决方法：**
1. 检查 `data/` 目录是否存在：`mkdir -p data`
2. 检查目录权限：`chmod 755 data`
3. 删除数据库重新初始化：`rm data/bot.db`

---

## 📊 监控和维护

### 查看日志

Bot 日志会输出到控制台，你可以重定向到文件：

```bash
python bot.py > logs/bot.log 2>&1
```

### 定期备份数据

备份数据库文件：

```bash
cp data/bot.db data/bot.db.backup
```

### 更新代码

```bash
git pull
pip install -r requirements.txt --upgrade
# 重启服务
```

---

## 🔐 安全建议

1. **不要泄露 Token**：`.env` 文件不要提交到公开仓库
2. **限制管理员权限**：只添加可信任的用户到 `SUPERUSERS`
3. **定期更新**：及时更新 NoneBot2 和插件到最新版本
4. **使用防火墙**：只允许本地回环地址访问 Bot 端口
5. **审查日志**：定期检查日志，发现异常及时处理

---

## 📞 获取帮助

- **NoneBot2 官方文档**：https://nonebot.dev/
- **NapCat 项目**：https://github.com/NapNeko/NapCatQQ
- **问题反馈**：在本项目提交 Issue

---

## ✅ 部署检查清单

完成部署后，请确认以下项目：

- [ ] Python 3.8+ 已安装
- [ ] 依赖已安装（`pip install -r requirements.txt`）
- [ ] `.env` 配置已正确填写
- [ ] NapCat 已下载并配置
- [ ] NapCat 配置中的 `postUrls` 与 Bot 端口一致
- [ ] Bot 已成功启动
- [ ] NapCat 已成功连接
- [ ] QQ 账号已登录
- [ ] 测试命令响应正常（`/help`）
- [ ] 数据库文件正常创建（`data/bot.db`）

全部完成后，你的 QQ Bot 就部署成功了！
