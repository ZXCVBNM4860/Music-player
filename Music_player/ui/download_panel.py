"""下载面板"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QFileDialog, QGroupBox, QComboBox
)
from PyQt6.QtCore import pyqtSignal
from language import i18n


class DownloadPanel(QWidget):
    browse_clicked = pyqtSignal()
    start_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    resume_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()
    check_api_clicked = pyqtSignal()
    search_clicked = pyqtSignal()
    ai_chat_clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._is_downloading = False
        self._is_paused = False
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # API 设置
        self._api_group = QGroupBox(i18n.tr("api_server"))
        api_layout = QHBoxLayout()
        
        self.api_input = QLineEdit("http://localhost:3000")
        self._api_label = QLabel(i18n.tr("api_address"))
        api_layout.addWidget(self._api_label)
        api_layout.addWidget(self.api_input, stretch=1)
        
        self.btn_check = QPushButton(i18n.tr("api_check"))
        self.btn_check.clicked.connect(self.check_api_clicked.emit)
        api_layout.addWidget(self.btn_check)
        
        self._api_group.setLayout(api_layout)
        layout.addWidget(self._api_group)
        
        # 音质选择
        self._quality_group = QGroupBox(i18n.tr("quality"))
        quality_layout = QHBoxLayout()
        
        self.quality_combo = QComboBox()
        self.quality_combo.addItem(i18n.tr("quality_128"), 128000)
        self.quality_combo.addItem(i18n.tr("quality_192"), 192000)
        self.quality_combo.addItem(i18n.tr("quality_320"), 320000)
        self.quality_combo.addItem(i18n.tr("quality_flac"), "flac")
        self.quality_combo.setCurrentIndex(2)
        
        self._quality_label = QLabel(i18n.tr("quality_label"))
        quality_layout.addWidget(self._quality_label)
        quality_layout.addWidget(self.quality_combo, stretch=1)
        
        self._quality_group.setLayout(quality_layout)
        layout.addWidget(self._quality_group)
        
        # 下载路径
        self._path_group = QGroupBox(i18n.tr("save_path"))
        path_layout = QHBoxLayout()
        
        self.path_input = QLineEdit("D:/音乐")
        path_layout.addWidget(self.path_input, stretch=1)
        
        self.btn_browse = QPushButton(i18n.tr("browse"))
        self.btn_browse.clicked.connect(self.browse_clicked.emit)
        path_layout.addWidget(self.btn_browse)
        
        self._path_group.setLayout(path_layout)
        layout.addWidget(self._path_group)
        
        # 任务设置
        self._task_group = QGroupBox(i18n.tr("download_task"))
        task_layout = QVBoxLayout()
        
        # 搜索按钮
        search_layout = QHBoxLayout()
        self.btn_search = QPushButton(i18n.tr("search"))
        self.btn_search.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                padding: 10px;
            }
        """)
        self.btn_search.clicked.connect(self.search_clicked.emit)
        search_layout.addWidget(self.btn_search)
        task_layout.addLayout(search_layout)
        
        # 类型
        type_layout = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        
        self.rb_single = QRadioButton(i18n.tr("single"))
        self.rb_playlist = QRadioButton(i18n.tr("playlist"))
        self.rb_mv = QRadioButton(i18n.tr("mv"))
        self.rb_playlist.setChecked(True)
        
        self.type_group.addButton(self.rb_single, 1)
        self.type_group.addButton(self.rb_playlist, 2)
        self.type_group.addButton(self.rb_mv, 3)
        
        self._type_label = QLabel(i18n.tr("type"))
        type_layout.addWidget(self._type_label)
        type_layout.addWidget(self.rb_single)
        type_layout.addWidget(self.rb_playlist)
        type_layout.addWidget(self.rb_mv)
        type_layout.addStretch()
        task_layout.addLayout(type_layout)
        
        # ID输入
        id_layout = QHBoxLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText(i18n.tr("id_input"))
        self._id_label = QLabel("ID:")
        id_layout.addWidget(self._id_label)
        id_layout.addWidget(self.id_input, stretch=1)
        task_layout.addLayout(id_layout)
        
        self._task_group.setLayout(task_layout)
        layout.addWidget(self._task_group)
        
        # AI 助手分组
        self._ai_group = QGroupBox(i18n.tr("ai_assistant"))
        ai_layout = QVBoxLayout()
        ai_layout.setSpacing(8)
        
        # API Key 输入
        key_layout = QHBoxLayout()
        self.ai_key_input = QLineEdit()
        self.ai_key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        self.ai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._ai_label = QLabel(i18n.tr("ai_key"))
        key_layout.addWidget(self._ai_label)
        key_layout.addWidget(self.ai_key_input, stretch=1)
        
        self.btn_ai_key_toggle = QPushButton(i18n.tr("ai_show"))
        self.btn_ai_key_toggle.setCheckable(True)
        self.btn_ai_key_toggle.setFixedWidth(80)
        self.btn_ai_key_toggle.toggled.connect(self._toggle_ai_key_visibility)
        key_layout.addWidget(self.btn_ai_key_toggle)
        ai_layout.addLayout(key_layout)
        
        # 打开对话按钮
        self.btn_ai_chat = QPushButton(i18n.tr("ai_chat"))
        self.btn_ai_chat.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                padding: 10px;
            }
        """)
        self.btn_ai_chat.clicked.connect(self.ai_chat_clicked.emit)
        ai_layout.addWidget(self.btn_ai_chat)
        
        self._ai_group.setLayout(ai_layout)
        layout.addWidget(self._ai_group)
        
        # 控制按钮
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton(i18n.tr("start_download"))
        self.btn_start.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 11pt;
                padding: 10px;
            }
        """)
        self.btn_start.clicked.connect(self._on_start_clicked)
        
        self.btn_pause = QPushButton(i18n.tr("pause"))
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause_clicked)
        
        self.btn_stop = QPushButton(i18n.tr("stop"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_clicked.emit)
        
        btn_layout.addWidget(self.btn_start, stretch=2)
        btn_layout.addWidget(self.btn_pause, stretch=1)
        btn_layout.addWidget(self.btn_stop, stretch=1)
        layout.addLayout(btn_layout)
        
        layout.addStretch()
    
    def _on_start_clicked(self):
        if self._is_paused:
            self.resume_clicked.emit()
            self._is_paused = False
            self.btn_pause.setText(i18n.tr("pause"))
            self.btn_start.setText(i18n.tr("start_download"))
        else:
            self.start_clicked.emit()
    
    def _on_pause_clicked(self):
        if self._is_downloading and not self._is_paused:
            self.pause_clicked.emit()
            self._is_paused = True
            self.btn_pause.setText(i18n.tr("resume"))
            self.btn_start.setText(i18n.tr("resume"))
    
    def set_downloading_state(self, downloading: bool):
        # 设置下载状态，更新按钮可用性
        self._is_downloading = downloading
        if downloading:
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_stop.setEnabled(True)
            self._is_paused = False
            self.btn_pause.setText(i18n.tr("pause"))
        else:
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_stop.setEnabled(False)
            self._is_paused = False
            self.btn_pause.setText(i18n.tr("pause"))
            self.btn_start.setText(i18n.tr("start_download"))
    
    def refresh_texts(self):
        self._api_group.setTitle(i18n.tr("api_server"))
        self._api_label.setText(i18n.tr("api_address"))
        self.btn_check.setText(i18n.tr("api_check"))
        self._quality_group.setTitle(i18n.tr("quality"))
        self._quality_label.setText(i18n.tr("quality_label"))
        current_data = self.quality_combo.currentData()
        self.quality_combo.clear()
        self.quality_combo.addItem(i18n.tr("quality_128"), 128000)
        self.quality_combo.addItem(i18n.tr("quality_192"), 192000)
        self.quality_combo.addItem(i18n.tr("quality_320"), 320000)
        self.quality_combo.addItem(i18n.tr("quality_flac"), "flac")
        idx = self.quality_combo.findData(current_data)
        if idx >= 0:
            self.quality_combo.setCurrentIndex(idx)
        self._path_group.setTitle(i18n.tr("save_path"))
        self.btn_browse.setText(i18n.tr("browse"))
        self._task_group.setTitle(i18n.tr("download_task"))
        self.btn_search.setText(i18n.tr("search"))
        self.rb_single.setText(i18n.tr("single"))
        self.rb_playlist.setText(i18n.tr("playlist"))
        self.rb_mv.setText(i18n.tr("mv"))
        self._type_label.setText(i18n.tr("type"))
        self.id_input.setPlaceholderText(i18n.tr("id_input"))
        self._ai_group.setTitle(i18n.tr("ai_assistant"))
        self._ai_label.setText(i18n.tr("ai_key"))
        if self.ai_key_input.echoMode() == QLineEdit.EchoMode.Normal:
            self.btn_ai_key_toggle.setText(i18n.tr("ai_hide"))
        else:
            self.btn_ai_key_toggle.setText(i18n.tr("ai_show"))
        self.btn_ai_chat.setText(i18n.tr("ai_chat"))
        
        if not self._is_downloading:
            self.btn_start.setText(i18n.tr("start_download"))
            self.btn_pause.setText(i18n.tr("pause"))
        elif self._is_paused:
            self.btn_start.setText(i18n.tr("resume"))
            self.btn_pause.setText(i18n.tr("resume"))
        else:
            self.btn_pause.setText(i18n.tr("pause"))
        
        self.btn_stop.setText(i18n.tr("stop"))
    
    def _toggle_ai_key_visibility(self, checked):
        if checked:
            self.ai_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_ai_key_toggle.setText(i18n.tr("ai_hide"))
        else:
            self.ai_key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_ai_key_toggle.setText(i18n.tr("ai_show"))
    
    def get_ai_api_key(self) -> str:
        return self.ai_key_input.text().strip()
    
    def set_ai_chat_enabled(self, enabled: bool):
        self.btn_ai_chat.setEnabled(enabled)
    
    def set_task_type(self, type_id: int):
        for btn in self.type_group.buttons():
            if self.type_group.id(btn) == type_id:
                btn.setChecked(True)
                break

    def get_api_url(self) -> str:
        return self.api_input.text().strip()
    
    def get_bitrate(self):
        return self.quality_combo.currentData()
    
    def get_download_path(self) -> str:
        return self.path_input.text().strip()
    
    def get_task_type(self) -> int:
        return self.type_group.checkedId()
    
    def get_task_id(self) -> str:
        return self.id_input.text().strip()
    
    def set_task_id(self, id_str: str):
        self.id_input.setText(id_str)
    
    def browse_directory(self) -> str:
        path = QFileDialog.getExistingDirectory(self, i18n.tr("choose_dir"))
        if path:
            self.path_input.setText(path)
        return path