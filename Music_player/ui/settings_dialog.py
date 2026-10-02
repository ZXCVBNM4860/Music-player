# ui/settings_dialog.py

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QCheckBox,QComboBox,QDialog,QGroupBox,
    QHBoxLayout,QLabel,QPushButton,QVBoxLayout,
)

from language import i18n


def read_bool(value, default=True) -> bool:
    if value is None:
        return default
    return str(value).lower() in ("1", "true", "yes", "on")


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("settingsDialog")
        self.setWindowTitle(i18n.tr("settings_title"))
        self.setMinimumSize(440, 360)

        self._settings = QSettings("netease_downloader", "settings")
        self._build_ui()
        self._load_current()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(self._build_theme_group())
        layout.addWidget(self._build_language_group())
        layout.addWidget(self._build_gpu_group())
        layout.addStretch()
        layout.addLayout(self._build_buttons())

    def _build_theme_group(self):
        group = QGroupBox(i18n.tr("settings_theme"))
        layout = QVBoxLayout(group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem(i18n.tr("theme_system"), "system")
        self.theme_combo.addItem(i18n.tr("theme_dark"), "dark")
        self.theme_combo.addItem(i18n.tr("theme_light"), "light")
        layout.addWidget(self.theme_combo)

        return group

    def _build_language_group(self):
        group = QGroupBox(i18n.tr("settings_language"))
        layout = QVBoxLayout(group)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem(i18n.tr("lang_zh"), "zh_cn")
        self.lang_combo.addItem(i18n.tr("lang_en"), "en_us")
        layout.addWidget(self.lang_combo)

        return group

    def _build_gpu_group(self):
        group = QGroupBox(i18n.tr("settings_gpu"))
        layout = QVBoxLayout(group)

        self.gpu_checkbox = QCheckBox(i18n.tr("settings_gpu_enable"))
        layout.addWidget(self.gpu_checkbox)

        hint = QLabel(i18n.tr("settings_gpu_hint"))
        hint.setObjectName("settingsHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

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

    def _load_current(self):
        theme = self._settings.value("theme", "system")
        index = self.theme_combo.findData(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

        lang = self._settings.value("lang", i18n.get_lang())
        index = self.lang_combo.findData(lang)
        if index >= 0:
            self.lang_combo.setCurrentIndex(index)

        gpu = self._settings.value("gpu_acceleration", "true")
        self.gpu_checkbox.setChecked(read_bool(gpu))

    def _on_ok(self):
        self._settings.setValue("theme", self.theme_combo.currentData())
        self._settings.setValue("lang", self.lang_combo.currentData())
        self._settings.setValue(
            "gpu_acceleration",
            "true" if self.gpu_checkbox.isChecked() else "false",
        )
        self.accept()

    def get_selected_theme(self) -> str:
        return self.theme_combo.currentData()

    def get_selected_language(self) -> str:
        return self.lang_combo.currentData()

    def is_gpu_enabled(self) -> bool:
        return self.gpu_checkbox.isChecked()