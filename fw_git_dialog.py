"""
GitHub 릴리즈 목록 조회 → 선택 → 다운로드·추출 다이얼로그.
완료 시 firmware_ready(bin_path, filesize) 시그널 emit 후 자동 닫힘.
"""
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QComboBox, QPushButton, QProgressBar,
    QFileDialog, QMessageBox, QFrame,
)


class _FetchReleasesThread(QThread):
    done = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, fetcher, repo):
        super().__init__()
        self._fetcher = fetcher
        self._repo = repo

    def run(self):
        try:
            self.done.emit(self._fetcher.get_releases(self._repo))
        except Exception as e:
            self.error.emit(str(e))


class _DownloadThread(QThread):
    done = pyqtSignal(str, int)   # (bin_path, filesize)
    error = pyqtSignal(str)

    def __init__(self, fetcher, asset, dest_dir, extract_file):
        super().__init__()
        self._fetcher = fetcher
        self._asset = asset
        self._dest_dir = dest_dir
        self._extract_file = extract_file

    def run(self):
        try:
            path, size = self._fetcher.download_and_extract(
                self._asset, self._dest_dir, self._extract_file
            )
            self.done.emit(path, size)
        except Exception as e:
            self.error.emit(str(e))


class FWGitDialog(QDialog):
    firmware_ready = pyqtSignal(str, int)   # (bin_path, filesize)

    def __init__(self, parent, device_name, family, device_spec, fetcher, dl_path):
        super().__init__(parent)
        self._device_name = device_name
        self._family = family
        self._device_spec = device_spec
        self._fetcher = fetcher
        self._dl_path = dl_path
        self._releases = []
        self._current_asset = None
        self._fetch_thread = None
        self._dl_thread = None

        self.setWindowTitle("FW from Git")
        self.setFixedWidth(540)
        self.setModal(True)
        self._build_ui()
        self._start_fetch()

    # ── UI 구성 ──────────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(12, 12, 12, 12)

        # 장치 / 저장소 정보
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.addWidget(QLabel("장치:"), 0, 0)
        grid.addWidget(QLabel(
            f"<b>{self._device_name}</b>  "
            f"<span style='color:gray'>({self._family['repo']})</span>"
        ), 0, 1)

        # 릴리즈 선택 행
        grid.addWidget(QLabel("릴리즈:"), 1, 0)
        rel_row = QHBoxLayout()
        self._combo = QComboBox()
        self._combo.setMinimumWidth(260)
        self._combo.currentIndexChanged.connect(self._update_asset_label)
        rel_row.addWidget(self._combo, 1)
        self._btn_refresh = QPushButton("새로고침")
        self._btn_refresh.setFixedWidth(80)
        self._btn_refresh.clicked.connect(self._start_fetch)
        rel_row.addWidget(self._btn_refresh)
        grid.addLayout(rel_row, 1, 1)

        # 에셋 행
        grid.addWidget(QLabel("에셋:"), 2, 0)
        self._lbl_asset = QLabel("—")
        self._lbl_asset.setWordWrap(True)
        grid.addWidget(self._lbl_asset, 2, 1)

        root.addLayout(grid)

        # 구분선
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.HLine)
        sep1.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep1)

        # 다운로드 경로 행
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("저장 경로:"))
        self._lbl_dlpath = QLabel(self._dl_path)
        self._lbl_dlpath.setWordWrap(True)
        path_row.addWidget(self._lbl_dlpath, 1)
        btn_change = QPushButton("변경")
        btn_change.setFixedWidth(60)
        btn_change.clicked.connect(self._change_dl_path)
        path_row.addWidget(btn_change)
        root.addLayout(path_row)

        # 구분선
        sep2 = QFrame()
        sep2.setFrameShape(QFrame.HLine)
        sep2.setFrameShadow(QFrame.Sunken)
        root.addWidget(sep2)

        # 진행 바 (기본 숨김)
        self._pgbar = QProgressBar()
        self._pgbar.setRange(0, 0)   # indeterminate
        self._pgbar.setVisible(False)
        root.addWidget(self._pgbar)

        # 하단 버튼 행
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._btn_dl = QPushButton("다운로드 & 업로드")
        self._btn_dl.setEnabled(False)
        self._btn_dl.setDefault(True)
        self._btn_dl.clicked.connect(self._on_download)
        btn_row.addWidget(self._btn_dl)
        btn_cancel = QPushButton("취소")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        root.addLayout(btn_row)

    # ── 릴리즈 조회 ─────────────────────────────────────────────────
    def _start_fetch(self):
        self._set_busy(True)
        self._combo.clear()
        self._lbl_asset.setText("목록 조회 중...")
        self._lbl_asset.setStyleSheet("")
        self._releases = []
        self._current_asset = None
        self._fetch_thread = _FetchReleasesThread(self._fetcher, self._family["repo"])
        self._fetch_thread.done.connect(self._on_releases_fetched)
        self._fetch_thread.error.connect(self._on_fetch_error)
        self._fetch_thread.start()

    def _on_releases_fetched(self, releases):
        self._releases = releases
        self._combo.blockSignals(True)
        self._combo.clear()
        for r in releases:
            date = r.get("published_at", "")[:10]
            self._combo.addItem(f"{r['tag_name']}  ({date})")
        self._combo.blockSignals(False)
        self._set_busy(False)
        if releases:
            self._update_asset_label(0)
        else:
            self._lbl_asset.setText("릴리즈가 없습니다.")

    def _on_fetch_error(self, msg):
        self._set_busy(False)
        self._lbl_asset.setText("조회 실패")
        self._lbl_asset.setStyleSheet("color: red;")
        QMessageBox.critical(self, "오류", f"릴리즈 목록 조회 실패:\n{msg}")

    def _update_asset_label(self, index):
        if not self._releases or index < 0 or index >= len(self._releases):
            self._current_asset = None
            self._btn_dl.setEnabled(False)
            return
        release = self._releases[index]
        asset = self._fetcher.find_asset(release, self._device_spec, self._family)
        self._current_asset = asset
        if asset:
            extract = self._device_spec.get("extract_file") or "(직접 사용)"
            self._lbl_asset.setText(f"{asset['name']}  →  {extract}")
            self._lbl_asset.setStyleSheet("")
            self._btn_dl.setEnabled(True)
        else:
            self._lbl_asset.setText("해당 릴리즈에 매칭 에셋 없음")
            self._lbl_asset.setStyleSheet("color: red;")
            self._btn_dl.setEnabled(False)

    # ── 다운로드 ─────────────────────────────────────────────────────
    def _on_download(self):
        self._set_busy(True)
        extract_file = self._device_spec.get("extract_file")
        self._dl_thread = _DownloadThread(
            self._fetcher,
            self._current_asset,
            self._dl_path,
            extract_file,
        )
        self._dl_thread.done.connect(self._on_download_done)
        self._dl_thread.error.connect(self._on_download_error)
        self._dl_thread.start()

    def _on_download_done(self, path, size):
        self._set_busy(False)
        self.firmware_ready.emit(path, size)
        self.accept()

    def _on_download_error(self, msg):
        self._set_busy(False)
        QMessageBox.critical(self, "오류", f"다운로드 실패:\n{msg}")

    # ── 저장 경로 변경 ───────────────────────────────────────────────
    def _change_dl_path(self):
        path = QFileDialog.getExistingDirectory(self, "다운로드 저장 경로", self._dl_path)
        if path:
            self._dl_path = path
            self._lbl_dlpath.setText(path)

    # ── 헬퍼 ─────────────────────────────────────────────────────────
    def _set_busy(self, busy: bool):
        self._pgbar.setVisible(busy)
        self._btn_refresh.setEnabled(not busy)
        self._combo.setEnabled(not busy)
        if not busy:
            self._btn_dl.setEnabled(self._current_asset is not None)
        else:
            self._btn_dl.setEnabled(False)
