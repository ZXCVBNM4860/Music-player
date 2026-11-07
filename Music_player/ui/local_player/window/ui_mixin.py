# ui/local_player/window/ui_mixin.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QLabel, QLineEdit,
    QPushButton, QComboBox, QSlider, QSplitter
)
from PyQt6.QtCore import Qt

from core.config import Config
from language import i18n
from ..cover_widget import CoverWidget
from ..player_tabs import PlayerTabsWidget
from ..lyric_widget import LyricWidget
from ..utils import read_int

class UIMixin:
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        main_layout.addLayout(self._build_top_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter)

        self._refresh_recent()

    def _build_top_bar(self) -> QHBoxLayout:
        top = QHBoxLayout()
        self.btn_scan = QPushButton(i18n.tr("scan_folder"))
        self.btn_scan.clicked.connect(self._scan_folder)
        top.addWidget(self.btn_scan)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(i18n.tr("search_placeholder"))
        self.search_box.textChanged.connect(self._on_search)
        top.addWidget(self.search_box, stretch=1)

        self.btn_netease = QPushButton(i18n.tr("netease_login"))
        self.btn_netease.clicked.connect(self._on_netease_btn_clicked)
        top.addWidget(self.btn_netease)
        return top

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.left_stack = QStackedWidget()
        
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        self.table = self._create_track_table()
        self.table.doubleClicked.connect(self._on_double_click)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_track_context_menu)
        table_layout.addWidget(self.table)
        
        self.lyric_widget = LyricWidget()

        self.left_stack.addWidget(table_container)
        self.left_stack.addWidget(self.lyric_widget)

        layout.addWidget(self.left_stack, stretch=1)

        info = QHBoxLayout()
        self.now_label = QLabel(i18n.tr("not_playing"))
        self.now_label.setObjectName("nowPlaying")
        info.addWidget(self.now_label, stretch=1)

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setObjectName("playerTime")
        info.addWidget(self.time_label)
        layout.addLayout(info)

        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.sliderPressed.connect(self._on_slider_pressed)
        self.progress.sliderReleased.connect(self._on_seek)
        self.progress.sliderMoved.connect(self._on_slider_move)
        self._dragging = False
        layout.addWidget(self.progress)

        layout.addLayout(self._build_playback_controls())
        return panel

    def _create_track_table(self) -> QTableWidget:
        table = QTableWidget()
        table.setObjectName("playerTable")
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels([
            i18n.tr("col_title"),
            i18n.tr("col_artist"),
            i18n.tr("col_duration"),
        ])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 150)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _build_playback_controls(self) -> QHBoxLayout:
        ctrl = QHBoxLayout()

        ctrl.addStretch()

        self.btn_prev = QPushButton("⏮")
        self.btn_prev.setFixedSize(48, 48)
        self.btn_prev.clicked.connect(self._play_prev)
        ctrl.addWidget(self.btn_prev)

        self.btn_play = QPushButton("▶")
        self.btn_play.setFixedSize(64, 64)
        self.btn_play.clicked.connect(self._toggle_play)
        self.btn_play.setStyleSheet("font-size: 20px; border-radius: 32px;")
        ctrl.addWidget(self.btn_play)

        self.btn_next = QPushButton("⏭")
        self.btn_next.setFixedSize(48, 48)
        self.btn_next.clicked.connect(self._play_next)
        ctrl.addWidget(self.btn_next)

        ctrl.addStretch()

        self.btn_toggle_lyric = QPushButton(i18n.tr("lyric_btn"))
        self.btn_toggle_lyric.setObjectName("lyricToggleBtn")
        self.btn_toggle_lyric.setCheckable(True)
        self.btn_toggle_lyric.setFixedHeight(36)
        self.btn_toggle_lyric.setMinimumWidth(40)
        self.btn_toggle_lyric.clicked.connect(self._toggle_lyric_view)
        ctrl.addWidget(self.btn_toggle_lyric)

        self.btn_favorite = QPushButton(i18n.tr("favorite"))
        self.btn_favorite.setFixedHeight(36)
        self.btn_favorite.setMinimumWidth(56)
        self.btn_favorite.clicked.connect(self._favorite_current)
        ctrl.addWidget(self.btn_favorite)

        self.btn_comments = QPushButton(i18n.tr("comments"))
        self.btn_comments.setFixedHeight(36)
        self.btn_comments.setMinimumWidth(56)
        self.btn_comments.clicked.connect(self._open_comments)
        ctrl.addWidget(self.btn_comments)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem(i18n.tr("mode_seq"), "seq")
        self.mode_combo.addItem(i18n.tr("mode_shuffle"), "shuffle")
        self.mode_combo.addItem(i18n.tr("mode_repeat_one"), "repeat_one")
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        ctrl.addWidget(self.mode_combo)

        ctrl.addWidget(QLabel(i18n.tr("speed")))
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(10, 500)
        self.speed_slider.setValue(100)
        self.speed_slider.setFixedWidth(80)
        self.speed_label = QLabel("1.0x")
        self.speed_label.setFixedWidth(36)
        self.speed_slider.valueChanged.connect(self._on_speed_changed)
        ctrl.addWidget(self.speed_slider)
        ctrl.addWidget(self.speed_label)

        ctrl.addWidget(QLabel(i18n.tr("volume")))

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(75)
        self.volume.setFixedWidth(80)
        self.volume.valueChanged.connect(self._on_volume)
        ctrl.addWidget(self.volume)

        return ctrl

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 0, 0, 0)
        layout.setSpacing(8)

        self.cover = CoverWidget(size=280)
        layout.addWidget(self.cover, alignment=Qt.AlignmentFlag.AlignCenter)

        self.player_tabs = PlayerTabsWidget()
        self.player_tabs.eq_changed.connect(self._on_eq_changed)
        self.player_tabs.playlist_activated.connect(self._on_playlist_activated)
        self.player_tabs.recent_double_clicked.connect(self._on_recent_double_click)
        self.player_tabs.clear_recent_clicked.connect(self._clear_recent)
        self.player_tabs.open_settings_clicked.connect(self._open_settings)
        self.player_tabs.toggle_desktop_lyric_clicked.connect(self._toggle_desktop_lyric)
        self.player_tabs.download_current_clicked.connect(self._download_current_song)
        
        layout.addWidget(self.player_tabs, stretch=1)
        return panel

    def _toggle_lyric_view(self, checked: bool):
        self.left_stack.setCurrentIndex(1 if checked else 0)
        self.btn_toggle_lyric.setStyleSheet(
            "background-color: #3d6fd6; color: white;" if checked else ""
        )
        
    def _toggle_desktop_lyric(self, checked: bool):
        if checked:
            pos = self._settings.value("desktop_lyric_position", "bottom")
            size = read_int(self._settings.value("desktop_lyric_font_size", 16), 16)
            self.desktop_lyric.apply_settings(size, pos)
            
            self.desktop_lyric.set_lyrics(self.lyric_widget._lines)
            self.desktop_lyric.show()
        else:
            self.desktop_lyric.hide()

    def refresh_texts(self):
        self.setWindowTitle(i18n.tr("local_player_title"))
        self.btn_scan.setText(i18n.tr("scan_folder"))
        self.search_box.setPlaceholderText(i18n.tr("search_placeholder"))

        self._update_login_state()

        self.table.setHorizontalHeaderLabels([
            i18n.tr("col_title"),
            i18n.tr("col_artist"),
            i18n.tr("col_duration"),
        ])

        if not self.cookies and not self.current_tracks:
            self.now_label.setText(i18n.tr("not_playing"))

        self.mode_combo.setItemText(0, i18n.tr("mode_seq"))
        self.mode_combo.setItemText(1, i18n.tr("mode_shuffle"))
        self.mode_combo.setItemText(2, i18n.tr("mode_repeat_one"))

        self.btn_toggle_lyric.setText(i18n.tr("lyric_btn"))
        self.btn_favorite.setText(i18n.tr("favorite"))
        self.btn_favorite.setToolTip(i18n.tr("favorite"))
        self.btn_comments.setText(i18n.tr("comments"))
        self.btn_comments.setToolTip(i18n.tr("comments"))
        
        self.player_tabs.refresh_texts()
        
        if hasattr(self, "lyric_widget"):
            self.lyric_widget.translate_check.setText(i18n.tr("lyric_show_translation"))