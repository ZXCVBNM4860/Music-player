# core/config.py

from utils.helpers import get_default_download_path


class Config:
    DEFAULT_API_URL = "http://localhost:3000"
    DEFAULT_DOWNLOAD_PATH = get_default_download_path()
    TIMEOUT_API = 10
    TIMEOUT_DOWNLOAD = (5, 60)
    DOWNLOAD_DELAY = 0.8
    MAX_RETRY = 3
    DEFAULT_AUTO_SCAN = False
    DEFAULT_LOCAL_LIBRARY_PATH = ""
    DEFAULT_FAST_DOWNLOAD = False
    DEFAULT_FAST_DOWNLOAD_THREADS = 5
    FAST_DOWNLOAD_THREADS_MAX = 20
    DEFAULT_CACHE_MAX_MB = 3072
    CACHE_MAX_MB_LIMIT = 20000