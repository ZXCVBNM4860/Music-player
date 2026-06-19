# Netease Downloader

网易云音乐下载器，基于 PyQt6 + NeteaseCloudMusicApi Enhanced。

> A NetEase Cloud Music downloader built with PyQt6 and NeteaseCloudMusicApi Enhanced.

## ⚠️ 免责声明 / Disclaimer

本项目仅供学习交流使用，请勿用于商业用途。

> This project is for educational and personal use only. Do not use it for commercial purposes.

- 本项目**不支持**下载 VIP 专属、付费专辑及任何受版权保护的内容
- 对于 VIP 内容，仅返回 30 秒试听片段
- 下载内容请于 24 小时内删除
- 请遵守当地法律法规及平台用户协议
- 使用本项目产生的任何法律责任由用户自行承担

> - This project **does not** support downloading VIP-exclusive, paid albums, or any copyrighted content.
> - For VIP content, the API only returns a 30-second preview.
> - Please delete downloaded content within 24 hours.
> - Please comply with local laws and platform terms of service.
> - Users bear all legal responsibility arising from the use of this project.

## 功能 / Features

- 搜索歌曲、歌单、MV / Search songs, playlists, and MVs
- 单曲/歌单/MV 下载 / Download single songs, playlists, and MVs
- 支持 MP3（128k/320k）和 FLAC 格式选择 / Support MP3 (128k/320k) and FLAC quality selection
- 五线程并发下载 / 5-thread concurrent downloading
- 断点续传 / Resume interrupted downloads
- 下载历史记录 / Download history tracking
- 预览播放 / Preview playback
- 内置 AI 助手（DeepSeek）/ Built-in AI assistant (DeepSeek)
- 中英文实时切换 / Real-time Chinese/English language switching

## 系统要求 / System Requirements

- Windows 10/11
- Python 3.10+
- [NeteaseCloudMusicApi Enhanced](https://github.com/...) 服务（需自行部署）

> [NeteaseCloudMusicApi Enhanced](https://github.com/...) service (self-hosted)

## 安装 / Installation

### 1. 克隆仓库 / Clone the repository

```bash
git clone https://github.com/yourusername/netease_downloader.git
cd netease_downloader
```

### 2. 安装依赖 / Install dependencies

```bash
pip install -r requirements.txt
```

### 3. 启动 API 服务 / Start the API service

先启动 NeteaseCloudMusicApi 服务：

> Start the NeteaseCloudMusicApi service first:

```bash
# 在 API 服务目录 / In the API service directory
npm start
```

### 4. 运行程序 / Run the application

```bash
python main.py
```

## 打包 / Build

```bash
pyinstaller --onefile --noconsole --add-data "language;language" --hidden-import PyQt6.QtMultimedia --hidden-import PyQt6.QtMultimediaWidgets main.py
```

打包后的文件位于 `dist/NetEaseDownloader.exe`。

> The packaged file is located at `dist/NetEaseDownloader.exe`.

## 许可证 / License

MIT
