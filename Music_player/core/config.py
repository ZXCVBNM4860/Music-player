# config.py
from utils.helpers import get_default_download_path


class Config:
    DEFAULT_API_URL = "http://localhost:3000"
    DEFAULT_DOWNLOAD_PATH = get_default_download_path()
    TIMEOUT_API = 10
    TIMEOUT_DOWNLOAD = (5, 60)
    DOWNLOAD_DELAY = 0.8
    MAX_RETRY = 3