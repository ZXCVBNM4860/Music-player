# ui/equalizer_widget.py

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,QHBoxLayout,QLabel,
    QPushButton,QSlider,
    QVBoxLayout,QWidget
)

from language import i18n


BANDS = [
    ("32Hz", 32),
    ("64Hz", 64),
    ("125Hz", 125),
    ("250Hz", 250),
    ("500Hz", 500),
    ("1kHz", 1000),
    ("2kHz", 2000),
    ("4kHz", 4000),
    ("8kHz", 8000),
    ("16kHz", 16000),
]

EQ_PRESETS = {
    "preset_flat": [0] * 10,
    "preset_pop": [-1, -1, 0, 2, 4, 4, 2, 0, -1, -2],
    "preset_rock": [4, 3, 2, -1, -2, -1, 2, 3, 4, 5],
    "preset_jazz": [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
    "preset_classical": [2, 1, 0, 0, 0, 0, -1, -2, -3, -4],
    "preset_bass": [8, 6, 4, 2, 0, 0, 0, 0, 0, 0],
    "preset_vocal": [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
}

PRESET_KEYS = list(EQ_PRESETS)


class EqualizerWidget(QWidget):
    eq_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.sliders = []
        self._build_ui()
        self._populate_presets()
        self.refresh_texts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        preset_row = QHBoxLayout()

        self.preset_label = QLabel()
        preset_row.addWidget(self.preset_label)

        self.preset_combo = QComboBox()
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.preset_combo, stretch=1)

        self.btn_reset = QPushButton()
        self.btn_reset.clicked.connect(self.reset)
        preset_row.addWidget(self.btn_reset)

        layout.addLayout(preset_row)

        band_row = QHBoxLayout()
        band_row.setSpacing(5)

        for name, _frequency in BANDS:
            column = QVBoxLayout()
            column.setSpacing(2)

            gain_label = QLabel("0")
            gain_label.setObjectName("eqGain")
            gain_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(gain_label)

            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-15, 15)
            slider.setValue(0)
            slider.setFixedHeight(150)
            slider.valueChanged.connect(
                lambda value, label=gain_label: self._on_gain_label(label, value)
            )
            slider.valueChanged.connect(self._on_slider_changed)
            column.addWidget(slider, alignment=Qt.AlignmentFlag.AlignCenter)

            freq_label = QLabel(name)
            freq_label.setObjectName("eqFreq")
            freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(freq_label)

            self.sliders.append(slider)
            band_row.addLayout(column)

        layout.addLayout(band_row)

    @staticmethod
    def _on_gain_label(label: QLabel, value: int):
        label.setText(f"{value:+d}" if value != 0 else "0")

    def _populate_presets(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.addItems(PRESET_KEYS)
        self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, _name: str):
        index = self.preset_combo.currentIndex()
        if not 0 <= index < len(PRESET_KEYS):
            return

        self.apply_gains(EQ_PRESETS[PRESET_KEYS[index]])

    def apply_gains(self, gains: list):
        for index, slider in enumerate(self.sliders):
            if index < len(gains):
                slider.setValue(gains[index])

    def reset(self):
        for slider in self.sliders:
            slider.setValue(0)
        self.preset_combo.setCurrentIndex(0)

    def get_gains(self) -> list:
        return [slider.value() for slider in self.sliders]

    def set_gains(self, gains: list):
        self.apply_gains(gains)

    def refresh_texts(self):
        self.preset_label.setText(i18n.tr("preset_label"))
        self.btn_reset.setText(i18n.tr("reset"))

        current_index = max(self.preset_combo.currentIndex(), 0)

        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems([i18n.tr(key) for key in PRESET_KEYS])
        self.preset_combo.setCurrentIndex(min(current_index, len(PRESET_KEYS) - 1))
        self.preset_combo.blockSignals(False)

    def _on_slider_changed(self):
        self.eq_changed.emit(self.get_gains())