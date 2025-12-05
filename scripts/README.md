# 二次元图片下载工具

本工具用于批量下载二次元图片到本地，支持图片压缩和元数据管理。

## 功能特性

- ✅ 从多个API源下载图片（Lolicon、搏天API、保罗API、Dmoe）
- ✅ 自动压缩图片节省存储空间（JPEG质量85，最大分辨率1920x1920）
- ✅ 抓取图片元数据（标题、作者、标签等）
- ✅ 元数据保存到CSV文件便于检索
- ✅ API自动fallback机制，确保下载成功率

## 使用方法

### 1. 基本用法

下载10张图片（默认）：
```bash
python scripts/download_anime_pics.py
```

下载50张图片：
```bash
python scripts/download_anime_pics.py 50
```

下载100张图片：
```bash
python scripts/download_anime_pics.py 100
```

### 2. 指定API源

只使用Lolicon API：
```bash
python scripts/download_anime_pics.py 20 --api Lolicon
```

只使用搏天API：
```bash
python scripts/download_anime_pics.py 20 --api 搏天API
```

可选的API源：
- `Lolicon` - Lolicon API（需要稳定网络）
- `搏天API` - 搏天API
- `保罗API` - 保罗API
- `Dmoe` - Dmoe API

### 3. 文件存储

- **图片文件**：保存在 `data/anime_pics/` 目录
- **元数据**：保存在 `data/anime_pics.csv` 文件

CSV文件包含以下字段：
- `filename` - 文件名
- `title` - 图片标题
- `author` - 作者
- `tags` - 标签（逗号分隔）
- `source` - 来源API
- `source_id` - 源ID（如Pixiv的PID）
- `download_time` - 下载时间
- `width` - 宽度
- `height` - 高度
- `file_size` - 文件大小（字节）

## 配置说明

你可以在脚本中修改以下配置：

```python
COMPRESS_QUALITY = 85  # JPEG压缩质量 (1-100)
MAX_SIZE = (1920, 1920)  # 最大分辨率
```

## 压缩机制

下载的图片会自动进行以下优化：

1. **格式转换**：将RGBA/透明图片转换为RGB格式
2. **尺寸限制**：超过1920x1920的图片会等比例缩小
3. **质量压缩**：使用JPEG格式保存，质量85（平衡质量和大小）
4. **优化选项**：启用JPEG优化选项进一步减小文件

压缩后的图片通常比原图小50%-80%，同时保持良好的视觉质量。

## Bot使用

下载图片后，bot会自动从本地图片库发送图片：

```
/美图              # 随机获取一张图片
/搜图 白毛         # 搜索包含"白毛"标签的图片
/来点图 5          # 获取5张随机图片
/图片库            # 查看图片库统计
```

## 注意事项

1. 首次使用需要先下载图片，建议下载至少50张以获得较好体验
2. Lolicon API可能需要稳定的网络环境，如果失败会自动尝试其他API
3. 下载过程中每张图片之间有2秒间隔，避免请求过快
4. 压缩后的图片无法恢复原图，如需原图请调整压缩质量为100

## 示例输出

```
🚀 开始批量下载 50 张图片...
📁 保存目录: /path/to/data/anime_pics
📊 元数据文件: /path/to/data/anime_pics.csv
🔧 压缩质量: 85, 最大尺寸: (1920, 1920)
------------------------------------------------------------

[1/50]
🔄 尝试使用 Lolicon...
📥 下载图片: 某个标题
💾 保存图片: 20231201_120000_abc123def456.jpg
✅ 成功! 1920x1080, 245.3KB, 标签: 白毛,猫娘,可爱

[2/50]
...

====================================================================
📊 下载完成! 成功: 48, 失败: 2
📁 图片保存在: /path/to/data/anime_pics
📄 元数据保存在: /path/to/data/anime_pics.csv
```

## 故障排查

**问题：所有API都失败**
- 检查网络连接
- 尝试指定单个API源测试
- 检查API服务是否正常

**问题：下载的图片质量不好**
- 调整 `COMPRESS_QUALITY` 参数（建议85-95）
- 增大 `MAX_SIZE` 限制

**问题：CSV文件格式错误**
- 删除 `data/anime_pics.csv` 文件，脚本会自动重新创建
