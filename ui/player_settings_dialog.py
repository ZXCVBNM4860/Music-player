# ui/player_settings_dialog.py

import hashlib
import random

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSpinBox, QVBoxLayout,
)

from core.config import Config
from language import i18n


SOURCE_LANGUAGE_OPTIONS = (
    ("auto", "lang_auto"),
    ("zh-CN", "lang_zh"),
    ("en", "lang_en"),
    ("ja", "lang_ja"),
)

TARGET_LANGUAGE_OPTIONS = (
    ("zh-CN", "lang_zh"),
    ("en", "lang_en"),
    ("ja", "lang_ja"),
)


def read_bool(value, default=False) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


def read_int(value, default=0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class PlayerSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("settingsDialog")
        self.setWindowTitle(i18n.tr("settings_player_title"))
        self.setMinimumSize(520, 560)

        self._settings = QSettings("netease_downloader", "settings")
        self._build_ui()
        self._load_current()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._build_local_scan_group())
        layout.addWidget(self._build_pre_download_group())
        layout.addWidget(self._build_cache_group())
        layout.addWidget(self._build_seed_group())
        layout.addWidget(self._build_translate_group())
        layout.addStretch()
        layout.addLayout(self._build_buttons())

    def _build_local_scan_group(self):
        group = QGroupBox(i18n.tr("settings_auto_scan"))
        layout = QVBoxLayout(group)

        self.auto_scan_check = QCheckBox(i18n.tr("settings_auto_scan"))
        layout.addWidget(self.auto_scan_check)

        hint = QLabel(i18n.tr("settings_auto_scan_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("settingsHint")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.tr("settings_local_path")))

        self.local_path_input = QLineEdit()
        self.local_path_input.setPlaceholderText("D:/Music")
        row.addWidget(self.local_path_input, stretch=1)

        btn_browse = QPushButton(i18n.tr("browse"))
        btn_browse.clicked.connect(self._pick_local_path)
        row.addWidget(btn_browse)

        layout.addLayout(row)
        return group

    def _build_pre_download_group(self):
        group = QGroupBox(i18n.tr("settings_pre_download"))
        layout = QVBoxLayout(group)

        self.fast_download_check = QCheckBox(i18n.tr("settings_pre_download"))
        layout.addWidget(self.fast_download_check)

        hint = QLabel(i18n.tr("settings_pre_download_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("settingsHint")
        layout.addWidget(hint)

        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.tr("settings_pre_download_threads")))

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, Config.FAST_DOWNLOAD_THREADS_MAX)
        self.threads_spin.setValue(Config.DEFAULT_FAST_DOWNLOAD_THREADS)
        row.addWidget(self.threads_spin)
        row.addStretch()

        layout.addLayout(row)
        return group

    def _build_cache_group(self):
        group = QGroupBox(i18n.tr("settings_cache_max"))
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel(i18n.tr("settings_cache_max")))

        self.cache_spin = QSpinBox()
        self.cache_spin.setRange(0, Config.CACHE_MAX_MB_LIMIT)
        self.cache_spin.setSingleStep(100)
        self.cache_spin.setValue(Config.DEFAULT_CACHE_MAX_MB)
        row.addWidget(self.cache_spin)
        row.addStretch()

        layout.addLayout(row)

        hint = QLabel(i18n.tr("settings_cache_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("settingsHint")
        layout.addWidget(hint)

        return group

    def _build_seed_group(self):
        group = QGroupBox(i18n.tr("random_settings_title"))
        layout = QVBoxLayout(group)

        hint = QLabel(i18n.tr("random_settings_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("settingsHint")
        layout.addWidget(hint)

        row = QHBoxLayout()

        self.seed_input = QLineEdit()
        row.addWidget(self.seed_input, stretch=1)

        btn_gen = QPushButton(i18n.tr("random_settings_generate"))
        btn_gen.clicked.connect(self._generate_seed)
        row.addWidget(btn_gen)

        layout.addLayout(row)
        return group

    def _build_translate_group(self):
        group = QGroupBox(i18n.tr("settings_translate"))
        layout = QVBoxLayout(group)

        self.translate_check = QCheckBox(i18n.tr("settings_translate_enable"))
        layout.addWidget(self.translate_check)

        hint = QLabel(i18n.tr("settings_translate_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("settingsHint")
        layout.addWidget(hint)

        source_row = QHBoxLayout()
        source_row.addWidget(QLabel(i18n.tr("settings_translate_source")))

        self.translate_source_combo = QComboBox()
        for value, key in SOURCE_LANGUAGE_OPTIONS:
            self.translate_source_combo.addItem(i18n.tr(key), value)
        source_row.addWidget(self.translate_source_combo, stretch=1)
        layout.addLayout(source_row)

        target_row = QHBoxLayout()
        target_row.addWidget(QLabel(i18n.tr("settings_translate_target")))

        self.translate_target_combo = QComboBox()
        for value, key in TARGET_LANGUAGE_OPTIONS:
            self.translate_target_combo.addItem(i18n.tr(key), value)
        target_row.addWidget(self.translate_target_combo, stretch=1)
        layout.addLayout(target_row)

        return group

    def _build_buttons(self):
        layout = QHBoxLayout()
        layout.addStretch()

        self.btn_ok = QPushButton(i18n.tr("confirm"))
        self.btn_ok.clicked.connect(self._on_ok)
        layout.addWidget(self.btn_ok)

        self.btn_cancel = QPushButton(i18n.tr("cancel"))
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel)

        return layout

    def _pick_local_path(self):
        folder = QFileDialog.getExistingDirectory(self, i18n.tr("settings_local_path"))
        if folder:
            self.local_path_input.setText(folder)

    def _generate_seed(self):
        self.seed_input.setText(str(random.randint(0, 999999999)))

    def _load_current(self):
        self.auto_scan_check.setChecked(
            read_bool(self._settings.value("auto_scan_local", Config.DEFAULT_AUTO_SCAN), False)
        )
        self.local_path_input.setText(
            self._settings.value("local_library_path", Config.DEFAULT_LOCAL_LIBRARY_PATH) or ""
        )

        self.fast_download_check.setChecked(
            read_bool(self._settings.value("fast_download", Config.DEFAULT_FAST_DOWNLOAD), False)
        )
        self.threads_spin.setValue(
            read_int(self._settings.value("fast_download_threads", Config.DEFAULT_FAST_DOWNLOAD_THREADS), 5)
        )

        self.cache_spin.setValue(
            read_int(self._settings.value("cache_max_mb", Config.DEFAULT_CACHE_MAX_MB), 500)
        )

        self.seed_input.setText(
            str(read_int(self._settings.value("random_seed", 0), 0))
        )

        self.translate_check.setChecked(
            read_bool(self._settings.value("translate_enabled", False), False)
        )

        source = str(self._settings.value("translate_source", "auto") or "auto")
        index = self.translate_source_combo.findData(source)
        self.translate_source_combo.setCurrentIndex(max(index, 0))

        target = str(self._settings.value("translate_target", "en") or "en")
        index = self.translate_target_combo.findData(target)
        self.translate_target_combo.setCurrentIndex(max(index, 0))

    def _on_ok(self):
        self._settings.setValue("auto_scan_local", "true" if self.auto_scan_check.isChecked() else "false")
        self._settings.setValue("local_library_path", self.local_path_input.text().strip())
        self._settings.setValue("fast_download", "true" if self.fast_download_check.isChecked() else "false")
        self._settings.setValue("fast_download_threads", self.threads_spin.value())
        self._settings.setValue("cache_max_mb", self.cache_spin.value())

        seed_text = self.seed_input.text().strip()
        if not seed_text:
            seed = 0
        else:
            try:
                seed = int(seed_text)
            except ValueError:
                seed = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest()[:8], 16)
        self._settings.setValue("random_seed", seed)

        self._settings.setValue(
            "translate_enabled",
            "true" if self.translate_check.isChecked() else "false",
        )
        self._settings.setValue(
            "translate_source", self.translate_source_combo.currentData()
        )
        self._settings.setValue(
            "translate_target", self.translate_target_combo.currentData()
        )

        self.accept()

    def get_random_seed(self) -> int:
        return read_int(self._settings.value("random_seed", 0), 0)

    def get_translate_settings(self) -> dict:
        return {
            "enabled": self.translate_check.isChecked(),
            "source": self.translate_source_combo.currentData(),
            "target": self.translate_target_combo.currentData(),
        }