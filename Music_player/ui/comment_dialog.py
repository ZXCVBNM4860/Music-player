# ui/comment_dialog.py

import html
from datetime import datetime
from typing import Any, Optional

from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTextBrowser, QVBoxLayout,
)

from core.api_client import APIClient
from core.translator import BingTranslator
from language import i18n
from ui.workers import run_async


PAGE_SIZE = 20


def _format_time(timestamp: int) -> str:
    if not timestamp:
        return ""
    try:
        return datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""


class CommentDialog(QDialog):
    def __init__(
        self,
        api_url: str,
        song_id: str,
        song_title: str,
        cookies=None,
        translate_enabled: bool = False,
        translate_source: str = "auto",
        translate_target: str = "en",
        parent=None,
    ):
        super().__init__(parent)

        self.setObjectName("commentDialog")
        self.setWindowTitle(i18n.tr("comments"))
        self.setMinimumSize(560, 640)

        self._song_id = song_id
        self._cookies = cookies or {}
        self._api = APIClient(api_url, cookies=self._cookies)

        self._translator = BingTranslator(translate_source, translate_target)

        self._offset = 0
        self._total = 0
        self._items = []
        self._translations = {}
        self._seen_comment_ids = set()
        self._reply_to_comment_id: Optional[str] = None

        self._build_ui(song_title, translate_enabled)
        self._load_more()

    def _build_ui(self, song_title: str, translate_enabled: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.title_label = QLabel(song_title)
        layout.addWidget(self.title_label)

        self.status_label = QLabel(i18n.tr("comment_loading"))
        layout.addWidget(self.status_label)

        self.browser = QTextBrowser()
        self.browser.setReadOnly(True)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.setObjectName("commentView")
        self.browser.anchorClicked.connect(self._on_anchor_clicked)
        layout.addWidget(self.browser, stretch=1)

        options = QHBoxLayout()
        self.translate_check = QCheckBox(i18n.tr("comment_translate"))
        self.translate_check.setChecked(translate_enabled)
        self.translate_check.toggled.connect(self._on_translate_toggled)
        options.addWidget(self.translate_check)

        self.attribution_label = QLabel(i18n.tr("translate_by_bing"))
        self.attribution_label.setObjectName("commentAttribution")
        self.attribution_label.setVisible(translate_enabled)
        options.addWidget(self.attribution_label)
        options.addStretch()
        layout.addLayout(options)

        self.reply_hint = QLabel("")
        self.reply_hint.setObjectName("commentReplyHint")
        self.reply_hint.setVisible(False)
        layout.addWidget(self.reply_hint)

        post_row = QHBoxLayout()

        self.content_input = QLineEdit()
        self.content_input.setObjectName("commentInput")
        self.content_input.setEnabled(bool(self._cookies))
        self.content_input.setPlaceholderText(
            i18n.tr("comment_post_placeholder") if self._cookies
            else i18n.tr("favorite_need_login")
        )
        self.content_input.returnPressed.connect(self._post_comment)
        post_row.addWidget(self.content_input, stretch=1)

        self.btn_cancel_reply = QPushButton(i18n.tr("cancel_reply"))
        self.btn_cancel_reply.setVisible(False)
        self.btn_cancel_reply.clicked.connect(self._cancel_reply)
        post_row.addWidget(self.btn_cancel_reply)

        self.btn_send = QPushButton(i18n.tr("comment_send"))
        self.btn_send.setObjectName("commentSendBtn")
        self.btn_send.setEnabled(bool(self._cookies))
        self.btn_send.clicked.connect(self._post_comment)
        post_row.addWidget(self.btn_send)

        layout.addLayout(post_row)

        row = QHBoxLayout()
        row.addStretch()

        self.btn_more = QPushButton(i18n.tr("comment_load_more"))
        self.btn_more.setEnabled(False)
        self.btn_more.clicked.connect(self._load_more)
        row.addWidget(self.btn_more)

        self.btn_close = QPushButton(i18n.tr("close"))
        self.btn_close.clicked.connect(self.reject)
        row.addWidget(self.btn_close)

        layout.addLayout(row)

    def _load_more(self):
        self.btn_more.setEnabled(False)
        self.status_label.setText(i18n.tr("comment_loading"))

        run_async(
            self._fetch,
            args=(self._offset,),
            on_success=self._on_loaded,
            on_error=self._on_failed,
        )

    def _fetch(self, offset: int):
        data = self._api.get_song_comments(
            self._song_id, limit=PAGE_SIZE, offset=offset
        )
        return data, offset

    def _on_loaded(self, result):
        data, offset = result
        self._total = data.get("total", 0)

        if offset == 0:
            self._items = []
            self._translations = {}
            self._seen_comment_ids.clear()
            self._append_unique(data.get("hot"), i18n.tr("comment_hot"))

        self._append_unique(data.get("comments"), None)

        self._offset = offset + PAGE_SIZE
        self._render()

        if self.browser.toPlainText().strip():
            self.status_label.setText(
                i18n.tr("comment_total").format(total=self._total)
            )
        else:
            self.status_label.setText(i18n.tr("comment_empty"))

        self.btn_more.setEnabled(bool(data.get("more")))

        if self.translate_check.isChecked():
            self._translate_pending()

    def _append_unique(self, comments: Optional[list], header: Optional[str]):
        for comment in comments or []:
            cid = comment.get("id")
            if cid and cid in self._seen_comment_ids:
                continue
            if cid:
                self._seen_comment_ids.add(cid)
            self._items.append({"header": header, "comment": comment})
            header = None

    def _on_failed(self, message):
        self.status_label.setText(f"{i18n.tr('comment_failed')}: {message}")
        self.btn_more.setEnabled(True)

    def _render(self):
        self.browser.clear()

        for item in self._items:
            if item["header"]:
                self.browser.append(
                    f"<p><b>{html.escape(item['header'])}</b></p>"
                )

            comment = item["comment"]
            self.browser.append(
                self._format_comment(
                    comment, self._translations.get(comment.get("id"))
                )
            )

    def _format_comment(
        self, comment: dict[str, Any], translated: Optional[str] = None
    ) -> str:
        cid = html.escape(str(comment.get("id") or ""))
        nickname = html.escape(str(comment.get("nickname") or ""))
        content = html.escape(str(comment.get("content") or "")).replace("\n", "<br>")
        location = html.escape(str(comment.get("location") or ""))
        when = _format_time(comment.get("time", 0))
        liked = comment.get("liked_count", 0)
        is_liked = comment.get("liked", False)

        meta = " · ".join(part for part in (when, location, f"♥ {liked}") if part)

        reply_html = ""
        for r in comment.get("reply_to") or []:
            r_name = html.escape(str(r.get("nickname") or ""))
            r_text = html.escape(str(r.get("content") or "")).replace("\n", "<br>")
            reply_html += (
                f"<br><span style='color:#888;'>{i18n.tr('comment_reply_to')} @{r_name}：{r_text}</span>"
            )

        parts = [f"<p><b>{nickname}</b><br>", content, reply_html]

        if translated:
            safe = html.escape(translated).replace("\n", "<br>")
            parts.append(f"<br><span style='color:#6d9eeb;'>{safe}</span>")

        parts.append(
            f"<br><span style='color:#888888;font-size:9pt;'>{meta}</span>"
        )

        if self._cookies:
            like_label = i18n.tr("comment_unlike") if is_liked else i18n.tr("comment_like")
            parts.append(
                f' <a href="like:{cid}" style="color:#3d6fd6;">{like_label}</a>'
                f' <a href="reply:{cid}" style="color:#3d6fd6;">{i18n.tr("comment_reply")}</a>'
            )

        parts.append("</p>")
        return "".join(parts)

    def _on_anchor_clicked(self, url):
        url_str = url.toString() if hasattr(url, "toString") else str(url)
        if url_str.startswith("like:"):
            self._toggle_like(url_str[len("like:"):])
        elif url_str.startswith("reply:"):
            self._start_reply(url_str[len("reply:"):])

    def _toggle_like(self, comment_id: str):
        target = None
        for item in self._items:
            if str(item["comment"].get("id")) == str(comment_id):
                target = item["comment"]
                break
        if target is None:
            return

        new_like = not target.get("liked", False)

        run_async(
            self._api.like_comment,
            args=(self._song_id, comment_id, new_like),
            on_success=lambda _: self._apply_like_result(target, new_like),
            on_error=lambda msg: self.status_label.setText(
                f"{i18n.tr('comment_like_failed')}: {msg}"
            ),
        )

    def _apply_like_result(self, comment: dict, liked: bool):
        comment["liked"] = liked
        comment["liked_count"] = max(
            0, comment.get("liked_count", 0) + (1 if liked else -1)
        )
        self._render()

    def _start_reply(self, comment_id: str):
        self._reply_to_comment_id = comment_id
        nickname = ""
        for item in self._items:
            c = item["comment"]
            if str(c.get("id")) == str(comment_id):
                nickname = c.get("nickname", "")
                break
        self.reply_hint.setText(
            i18n.tr("comment_replying_to").format(name=nickname)
        )
        self.reply_hint.setVisible(True)
        self.btn_cancel_reply.setVisible(True)
        self.content_input.setFocus()

    def _cancel_reply(self):
        self._reply_to_comment_id = None
        self.reply_hint.setVisible(False)
        self.btn_cancel_reply.setVisible(False)

    def _post_comment(self):
        content = self.content_input.text().strip()

        if not self._cookies:
            self.status_label.setText(i18n.tr("favorite_need_login"))
            return
        if not content:
            self.status_label.setText(i18n.tr("comment_empty_content"))
            return

        self.btn_send.setEnabled(False)
        self.content_input.setEnabled(False)
        self.status_label.setText(i18n.tr("comment_posting"))

        parent_id = self._reply_to_comment_id

        run_async(
            self._api.post_song_comment,
            args=(self._song_id, content, parent_id),
            on_success=self._on_posted,
            on_error=self._on_post_failed,
        )

    def _on_posted(self, _result):
        self.btn_send.setEnabled(True)
        self.content_input.setEnabled(True)
        self.content_input.clear()
        self.status_label.setText(i18n.tr("comment_posted"))
        self._cancel_reply()

        self._offset = 0
        self._load_more()

    def _on_post_failed(self, message):
        self.btn_send.setEnabled(True)
        self.content_input.setEnabled(True)
        self.status_label.setText(f"{i18n.tr('comment_post_failed')}: {message}")

    def _on_translate_toggled(self, checked: bool):
        self.attribution_label.setVisible(checked)
        if checked:
            self._translate_pending()
            return
        self._translations = {}
        self._render()

    def _translate_pending(self):
        pending = [
            item["comment"]
            for item in self._items
            if item["comment"].get("content")
            and item["comment"].get("id") not in self._translations
        ]
        if not pending:
            return

        self.status_label.setText(i18n.tr("comment_translating"))
        run_async(
            self._translate_worker,
            args=(pending,),
            on_success=self._on_translated,
            on_error=self._on_translate_failed,
        )

    def _translate_worker(self, comments: list):
        results = self._translator.translate_many(
            [c.get("content", "") for c in comments]
        )
        return list(zip(comments, results))

    def _on_translated(self, pairs):
        for comment, translated in pairs:
            if translated:
                self._translations[comment.get("id")] = translated
        self._render()
        self.status_label.setText(
            i18n.tr("comment_total").format(total=self._total)
        )

    def _on_translate_failed(self, message):
        if message in ("bing_params_error", "bing_unexpected_response", "bing_empty_translation"):
            err_msg = i18n.tr(message)
        else:
            err_msg = message
        self.status_label.setText(f"{i18n.tr('translate_failed')}: {err_msg}")