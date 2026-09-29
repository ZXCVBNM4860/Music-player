# Music Player

Music player，基于 PyQt6 + NeteaseCloudMusicApi Enhanced。

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

- **搜索发现** — 支持搜索歌曲、歌单、MV
  - Search songs, playlists, and MVs
- **歌单浏览** — 查看歌单完整曲目列表，支持单首试听或下载
  - Browse full playlist tracks with single-track preview or download
- **本地下载** — 支持单曲、歌单、MV 下载，可选 MP3（128k/320k）或 FLAC 音质
  - Download single songs, playlists, and MVs with MP3/FLAC quality selection

### 本地播放器 / Local Player

- **本地曲库** — 扫描本地音乐文件夹，支持 MP3 / FLAC / WAV / M4A / OGG / AAC
  - Scan local music folders, supporting MP3 / FLAC / WAV / M4A / OGG / AAC
- **播放控制** — 播放 / 暂停 / 上一首 / 下一首 / 进度拖动 / 音量调节
  - Playback control: play / pause / prev / next / seek / volume
- **播放模式** — 顺序播放 / 随机播放 / 单曲循环
  - Playback modes: sequential / shuffle / repeat-one
- **随机种子** — 自定义随机种子，同一种子产生固定打乱顺序
  - Custom random seed, same seed gives deterministic shuffle order
- **专辑封面** — 本地文件内嵌封面 + 网易云在线封面
  - Album cover from embedded metadata + Netease online cover
- **10 段均衡器** — 内置 7 种预设，实时生效
  - 10-band equalizer with 7 presets, applies in real time
- **播放列表** — 创建、删除、添加曲目
  - Create, delete, add tracks to playlists
- **最近播放** — 自动记录，最多 500 条
  - Auto-tracked recently played, up to 500 entries

### 网易云 / Netease Cloud Music

- **登录** — 内嵌浏览器加载官方登录页，自动捕获 Cookie，登录状态持久化
  - Embedded browser login, auto-capture cookies, persistent login state
- **歌单管理** — 查看、创建、收藏歌单
  - View, create, subscribe to playlists
- **每日推荐** — 一键加载当日推荐
  - Load daily recommendations in one click
- **心动模式** — 基于当前播放歌曲和歌单生成智能推荐
  - Smart recommendations based on current track and playlist
- **私人雷达** — 一键加载私人雷达歌单
  - Load personal radar playlist in one click
- **在线播放** — 网易云歌曲自动缓存到本地后播放
  - Online Netease tracks cached locally before playback

### 其他 / Misc

- **AI 助手** — 内置 DeepSeek 对话，支持代码高亮与推理过程展示
  - Built-in DeepSeek AI chat with markdown rendering and reasoning display
- **多语言** — 实时切换中文 / English
  - Real-time Chinese/English language switching
- **主题切换** — 暗色 / 亮色 / 跟随系统
  - Dark / Light / System theme switching
- **一键安装 API** — 内置安装向导，自动下载 Node.js 和 API 源码
  - Built-in installer for Node.js and API source

## 系统要求 / System Requirements

- Windows 10+ / Linux / macOS
- Python 3.9+
- [NeteaseCloudMusicApi Enhanced](https://github.com/xgxdmx/NeteaseMusic-API) 服务（需自行部署，或使用内置安装向导）
- [NeteaseCloudMusicApi Enhanced](https://github.com/xgxdmx/NeteaseMusic-API) service (self-hosted, or use the built-in installer)

## 许可证 / License

MIT
