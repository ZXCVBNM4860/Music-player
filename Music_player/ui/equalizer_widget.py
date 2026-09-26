# ui/equalizer_widget.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from language import i18n


BANDS = [
    ("32Hz", 32), ("64Hz", 64), ("125Hz", 125), ("250Hz", 250),
    ("500Hz", 500), ("1kHz", 1000), ("2kHz", 2000), ("4kHz", 4000),
    ("8kHz", 8000), ("16kHz", 16000)
]


class EqualizerWidget(QWidget):
    eq_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sliders = []
        self._build_ui()
        self._load_presets()
        self.refresh_texts()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        preset_layout = QHBoxLayout()
        self.preset_label = QLabel()
        preset_layout.addWidget(self.preset_label)
        self.preset_combo = QComboBox()
        self.preset_combo.currentTextChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo, stretch=1)
        self.btn_reset = QPushButton()
        self.btn_reset.clicked.connect(self.reset)
        preset_layout.addWidget(self.btn_reset)
        layout.addLayout(preset_layout)

        band_layout = QHBoxLayout()
        band_layout.setSpacing(5)

        for name, freq in BANDS:
            v_layout = QVBoxLayout()
            v_layout.setSpacing(2)

            gain_label = QLabel("0")
            gain_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gain_label.setStyleSheet("color: #888888; font-size: 9pt;")
            v_layout.addWidget(gain_label)

            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-15, 15)
            slider.setValue(0)
            slider.setFixedHeight(150)
            slider.valueChanged.connect(
                lambda v, lbl=gain_label: lbl.setText(f"{v:+d}" if v != 0 else "0")
            )
            slider.valueChanged.connect(self._on_slider_changed)
            v_layout.addWidget(slider, alignment=Qt.AlignmentFlag.AlignCenter)

            freq_label = QLabel(name)
            freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            freq_label.setStyleSheet("color: #666666; font-size: 8pt;")
            v_layout.addWidget(freq_label)

            self.sliders.append(slider)
            band_layout.addLayout(v_layout)

        layout.addLayout(band_layout)

    def _on_slider_changed(self):
        self.eq_changed.emit([s.value() for s in self.sliders])

    def _load_presets(self):
        self.presets = {
            "preset_flat": [0] * 10,
            "preset_pop": [-1, -1, 0, 2, 4, 4, 2, 0, -1, -2],
            "preset_rock": [4, 3, 2, -1, -2, -1, 2, 3, 4, 5],
            "preset_jazz": [3, 2, 1, 2, -1, -1, 0, 1, 2, 3],
            "preset_classical": [2, 1, 0, 0, 0, 0, -1, -2, -3, -4],
            "preset_bass": [8, 6, 4, 2, 0, 0, 0, 0, 0, 0],
            "preset_vocal": [-2, -1, 0, 2, 4, 4, 3, 1, 0, -1],
        }
        self.preset_keys = list(self.presets)
        self.preset_combo.blockSignals(True)
        self.preset_combo.addItems(self.preset_keys)
        self.preset_combo.setCurrentIndex(0)
        self.preset_combo.blockSignals(False)

    def refresh_texts(self):
        self.preset_label.setText(i18n.tr("preset_label"))
        self.btn_reset.setText(i18n.tr("reset"))
        current = max(self.preset_combo.currentIndex(), 0)
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems([i18n.tr(key) for key in self.preset_keys])
        self.preset_combo.setCurrentIndex(min(current, len(self.preset_keys) - 1))
        self.preset_combo.blockSignals(False)

    def _on_preset_changed(self, name: str):
        index = self.preset_combo.currentIndex()
        if 0 <= index < len(self.preset_keys):
            gains = self.presets[self.preset_keys[index]]
            for i, slider in enumerate(self.sliders):
                if i < len(gains):
                    slider.setValue(gains[i])

    def reset(self):
        for slider in self.sliders:
            slider.setValue(0)
        self.preset_combo.setCurrentIndex(0)

    def get_gains(self) -> list:
        return [s.value() for s in self.sliders]

    def set_gains(self, gains: list):
        for i, val in enumerate(gains):
            if i < len(self.sliders):
                self.sliders[i].setValue(val)