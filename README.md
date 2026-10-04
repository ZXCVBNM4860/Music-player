# Music Player

一个基于 PyQt6 + NeteaseCloudMusicApi Enhanced 的网易云音乐下载器与播放器。

A NetEase Cloud Music downloader and player built with PyQt6 and NeteaseCloudMusicApi Enhanced.

## 免责声明 / Disclaimer

本项目仅供学习交流使用，请勿用于商业用途。

This project is for educational and personal use only. Do not use it for commercial purposes.

- 本项目**不支持**下载 VIP 专属、付费专辑及任何受版权保护的内容
- This project **does not** support downloading VIP-exclusive, paid albums, or any copyrighted content.
- 对于 VIP 内容，API 仅返回 30 秒试听片段
- For VIP content, the API only returns a 30-second preview.
- 下载内容请于 24 小时内删除
- Please delete downloaded content within 24 hours.
- 请遵守当地法律法规及平台用户协议
- Please comply with local laws and platform terms of service.
- 使用本项目产生的任何法律责任由用户自行承担
- Users bear all legal responsibility arising from the use of this project.

## 功能 / Features

### 下载 / Download

- **搜索发现** — 搜索歌曲、歌单、MV
- **Search** — Search songs, playlists and MVs
- **歌单浏览** — 查看歌单完整曲目列表，单首试听或下载
- **Playlist browsing** — View full track list, preview or download individually
- **本地下载** — 单曲、歌单、MV 下载，可选 MP3（128k/192k/320k）或 FLAC
- **Local download** — Download songs, playlists and MVs in MP3 (128k/192k/320k) or FLAC
- **试听版检测** — 时长低于 30 秒的文件自动移至 `rejected_trial/` 而非删除
- **Trial detection** — Files shorter than 30s are moved to `rejected_trial/` instead of being deleted

### 本地播放器 / Local Player

- **本地曲库** — 扫描本地音乐文件夹，支持 MP3 / FLAC / WAV / M4A / OGG / AAC
- **Local library** — Scan music folders, supporting MP3 / FLAC / WAV / M4A / OGG / AAC
- **播放控制** — 播放 / 暂停 / 上一首 / 下一首 / 进度拖动 / 音量调节
- **Playback control** — Play / pause / prev / next / seek / volume
- **播放模式** — 顺序播放 / 随机播放 / 单曲循环
- **Playback modes** — Sequential / shuffle / repeat-one
- **随机种子** — 自定义随机种子，同一种子产生固定打乱顺序
- **Random seed** — Custom seed produces deterministic shuffle order
- **自动扫描本地** — 同名同歌手的在线歌曲优先播放本地文件
- **Auto scan local** — Play local file when a matching one exists
- **快速下载** — 打开歌单后后台缓存本地曲库没有的歌曲
- **Fast download** — Auto-cache tracks missing locally in the background
- **缓存上限** — 自定义缓存大小，退出时按大小清理最旧文件
- **Cache limit** — Custom cache size, oldest files cleaned on exit
- **专辑封面** — 本地内嵌封面 + 网易云在线封面
- **Cover art** — Embedded cover + online cover from Netease
- **10 段均衡器** — 内置 7 种预设，实时生效
- **10-band equalizer** — 7 presets, applies in real time
- **播放列表** — 创建、重命名、删除、添加曲目
- **Playlists** — Create, rename, delete, add tracks
- **最近播放** — 自动记录，最多 500 条
- **Recently played** — Auto-tracked, up to 500 entries

### 网易云 / Netease Cloud Music

- **登录** — 内嵌浏览器加载官方登录页，自动捕获 Cookie，登录状态持久化
- **Login** — Embedded browser loads the official login page, cookies captured automatically and persisted
- **歌单管理** — 查看、创建、收藏歌单
- **Playlist management** — View, create and subscribe to playlists
- **收藏歌曲** — 一键收藏到指定歌单，多个歌单时弹窗选择
- **Favorite** — One-click favorite to a chosen playlist, prompt on multiple
- **每日推荐** — 一键加载当日推荐
- **Daily recommend** — Load daily recommendations in one click
- **私人雷达** — 一键加载私人雷达歌单
- **Private radar** — Load the personal radar playlist in one click
- **在线播放** — 网易云歌曲自动缓存到本地后播放
- **Online playback** — Netease tracks cached locally before playback

### 其他 / Misc

- **AI 助手** — 内置 DeepSeek 对话，支持代码高亮与推理过程展示
- **AI assistant** — Built-in DeepSeek chat with markdown rendering and reasoning display
- **多语言** — 实时切换中文 / English
- **Multi-language** — Switch between Chinese / English in real time
- **主题切换** — 暗色 / 亮色 / 跟随系统
- **Themes** — Dark / light / system
- **一键安装 API** — 内置安装向导，自动下载 API 源码并配置环境
- **One-click API installer** — Built-in wizard downloads API source and configures environment

## 系统要求 / System Requirements

- Windows 10+ / Linux / macOS
- Python 3.9+
- [NeteaseCloudMusicApi Enhanced](https://github.com/xgxdmx/NeteaseMusic-API) 服务（需自行部署，或使用内置安装向导）
- [NeteaseCloudMusicApi Enhanced](https://github.com/xgxdmx/NeteaseMusic-API) service (self-hosted, or use the built-in installer)

## 快速开始 / Quick Start

1. 部署 NeteaseCloudMusicApi Enhanced 服务（或使用程序内置的安装向导）
2. 运行 `python main.py` 或启动打包后的 `Music_Player.exe`
3. 在「API 服务器」一栏填写 API 地址（默认 `http://localhost:3000`）并点击「检测」
4. 开始搜索、下载或使用本地播放器

---

1. Deploy NeteaseCloudMusicApi Enhanced (or use the built-in installer)
2. Run `python main.py` or launch the packaged `Music_Player.exe`
3. Fill in the API address (default `http://localhost:3000`) and click "Check"
4. Start searching, downloading, or using the local player

## 配置文件 / Config Files

配置文件存放在程序同级的 `config/` 目录下。

Config files are stored in `config/` next to the executable.

| 文件 / File | 用途 / Purpose |
|------|------|
| `auth.json` | 网易云登录状态 / Netease login state |
| `playlists.json` | 播放列表 / Playlists |
| `recent_played.json` | 最近播放 / Recently played |
| `library_cache.json` | 本地曲库缓存 / Local library cache |
| `cache/` | 在线播放缓存 / Online playback cache |

## 许可证 / License

MIT
