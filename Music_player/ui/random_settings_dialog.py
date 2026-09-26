import random
import hashlib
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton
)
from language import i18n


class RandomSettingsDialog(QDialog):
    def __init__(self, parent=None, current_seed=0):
        super().__init__(parent)
        self.setWindowTitle(i18n.tr("random_settings_title"))
        self.setMinimumWidth(420)
        self.seed = current_seed
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(i18n.tr("random_settings_hint")))

        row = QHBoxLayout()
        self.seed_input = QLineEdit(str(self.seed))
        row.addWidget(self.seed_input, stretch=1)

        self.btn_gen = QPushButton(i18n.tr("random_settings_generate"))
        self.btn_gen.clicked.connect(self._generate)
        row.addWidget(self.btn_gen)

        layout.addLayout(row)

        btns = QHBoxLayout()
        btns.addStretch()

        ok = QPushButton(i18n.tr("confirm"))
        ok.clicked.connect(self._on_ok)
        btns.addWidget(ok)

        cancel = QPushButton(i18n.tr("cancel"))
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)

        layout.addLayout(btns)

    def _generate(self):
        self.seed_input.setText(str(random.randint(0, 999999999)))

    def _on_ok(self):
        text = self.seed_input.text().strip()
        if not text:
            self.seed = 0
        else:
            try:
                self.seed = int(text)
            except ValueError:
                self.seed = int(hashlib.md5(text.encode("utf-8")).hexdigest()[:8], 16)
        self.accept()

    def get_seed(self):
        return self.seed