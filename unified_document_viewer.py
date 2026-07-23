"""
Unified Document Viewer Widget for Relativity Load File Analyzer using PySide6.
Contains a QTabWidget with 'Metadata' (record detail table) and 'Image' (QWebEngineView HTML5 canvas document viewer).
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, QTableWidgetItem, 
    QHeaderView, QLabel, QPushButton, QFrame, QCheckBox, QLineEdit, QSizePolicy,
    QMenu, QApplication
)
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView


class CopyableTableWidget(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)
        
    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if not item:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background-color: #1E293B; color: #FFFFFF; border: 1px solid #475569; padding: 4px; }
            QMenu::item { padding: 6px 24px; margin: 2px; border-radius: 4px; }
            QMenu::item:selected { background-color: #3B82F6; color: #FFFFFF; }
        """)
        copy_action = menu.addAction("Copy Field Value")
        
        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == copy_action:
            QApplication.clipboard().setText(item.text())

from image_render_worker import ImageRenderWorker
from opt_engine import OptDocumentStore, OptDocument


class UnifiedDocumentViewer(QWidget):
    """
    Reusable Document Viewer Component with Metadata & Image tabs using PySide6 and QWebEngineView.
    Listens to record_selected(record_id: str) signal.
    """
    # Signals
    request_nav_action = Signal(str)
    page_changed = Signal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.opt_store: OptDocumentStore = OptDocumentStore()
        self.metadata_dict: dict = {}  # {DocID: {Field: Value}}
        self.base_dir: str = ""
        self.current_doc_id: str = ""
        self.current_page_idx: int = 0
        self.worker: ImageRenderWorker = None
        self.view_mode: str = "fit_page"  # "fit_page", "fit_width"
        self.current_temp_img = ""
        
        # Prevent the web engine / layout container from expanding and pushing splitters out of window boundaries
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #334155; background-color: #1E293B; }
            QTabBar::tab { background-color: #0F172A; color: #94A3B8; padding: 6px 14px; border: 1px solid #334155; }
            QTabBar::tab:selected { background-color: #1E293B; color: #FFFFFF; border-bottom: 2px solid #3B82F6; }
        """)

        # Tab 1: Image View
        self.image_tab = QWidget()
        img_layout = QVBoxLayout(self.image_tab)
        img_layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar overlay controls
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(2, 2, 2, 2)
        
        self.btn_fit_page = QPushButton("Fit Page")
        self.btn_fit_width = QPushButton("Fit Width")
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_out = QPushButton("-")

        for btn in (self.btn_fit_page, self.btn_fit_width, self.btn_zoom_in, self.btn_zoom_out):
            btn.setStyleSheet("""
                QPushButton { background-color: #334155; color: white; border: none; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
                QPushButton:hover { background-color: #475569; }
            """)
            tb_layout.addWidget(btn)

        self.lbl_status = QLabel("No document loaded")
        self.lbl_status.setStyleSheet("color: #94A3B8; font-size: 11px; padding-left: 8px;")
        tb_layout.addWidget(self.lbl_status)
        tb_layout.addStretch()

        img_layout.addLayout(tb_layout)

        # QWebEngineView setup
        self.web_view = QWebEngineView(self)
        # Load local viewer HTML page
        viewer_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer.html")
        self.web_view.load(QUrl.fromLocalFile(viewer_path))
        img_layout.addWidget(self.web_view, 1)

        # Bottom Navigation Bar
        nav_bar_box = QFrame()
        nav_bar_box.setStyleSheet("background-color: #1E293B; border-top: 1px solid #334155;")
        nav_bar_layout = QHBoxLayout(nav_bar_box)
        nav_bar_layout.setContentsMargins(6, 4, 6, 4)

        self.btn_nav_prev_doc = QPushButton("|<<")
        self.btn_nav_prev_page = QPushButton("<")
        self.btn_nav_next_page = QPushButton(">")
        self.btn_nav_next_doc = QPushButton(">>|")

        for nav_btn in (self.btn_nav_prev_doc, self.btn_nav_prev_page, self.btn_nav_next_page, self.btn_nav_next_doc):
            nav_btn.setStyleSheet("""
                QPushButton { background-color: #0F172A; color: #3B82F6; border: 1px solid #334155; border-radius: 4px; font-weight: bold; min-width: 36px; padding: 4px; }
                QPushButton:hover { background-color: #334155; color: #60A5FA; }
            """)
            nav_bar_layout.addWidget(nav_btn)

        self.lbl_nav_counter = QLabel("Doc 0 of 0 | Page 0 of 0")
        self.lbl_nav_counter.setStyleSheet("color: #F8FAFC; font-weight: bold; padding-left: 8px; font-size: 12px;")
        nav_bar_layout.addWidget(self.lbl_nav_counter)
        nav_bar_layout.addStretch()

        img_layout.addWidget(nav_bar_box)

        # Tab 2: Metadata View
        self.metadata_tab = QWidget()
        meta_layout = QVBoxLayout(self.metadata_tab)
        meta_layout.setContentsMargins(4, 4, 4, 4)
        meta_layout.setSpacing(6)

        # Metadata Filters
        meta_ctrl_layout = QHBoxLayout()
        self.chk_hide_empty_fields = QCheckBox("Hide Empty Fields")
        self.chk_hide_empty_fields.setStyleSheet("color: #FFFFFF; font-size: 12px;")
        
        self.record_search = QLineEdit()
        self.record_search.setPlaceholderText("Filter record properties...")
        self.record_search.setStyleSheet("""
            QLineEdit { background-color: #0F172A; color: #FFFFFF; border: 1px solid #475569; border-radius: 4px; padding: 4px 8px; }
            QLineEdit:focus { border: 1px solid #3B82F6; }
        """)

        meta_ctrl_layout.addWidget(self.chk_hide_empty_fields)
        meta_ctrl_layout.addWidget(self.record_search)
        meta_layout.addLayout(meta_ctrl_layout)

        self.meta_table = CopyableTableWidget()
        self.meta_table.setColumnCount(2)
        self.meta_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.meta_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.meta_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.meta_table.setStyleSheet("""
            QTableWidget { background-color: #0F172A; color: #FFFFFF; gridline-color: #334155; }
            QHeaderView::section { background-color: #1E293B; color: #94A3B8; font-weight: bold; padding: 4px; }
        """)
        meta_layout.addWidget(self.meta_table)

        # Add tabs: Metadata strictly precedes Image
        self.tab_widget.addTab(self.metadata_tab, "Metadata")
        self.tab_widget.addTab(self.image_tab, "Image")
        layout.addWidget(self.tab_widget)

        # Connect toolbar button signals
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.btn_fit_page.clicked.connect(self.fit_page)
        self.btn_fit_width.clicked.connect(self.fit_width)
        
        # Connect metadata filter signals
        self.record_search.textChanged.connect(self.filter_metadata_table)
        self.chk_hide_empty_fields.stateChanged.connect(self.filter_metadata_table)

        # Connect bottom navigation signals
        self.btn_nav_prev_doc.clicked.connect(lambda: self.request_nav_action.emit("prev_doc"))
        self.btn_nav_prev_page.clicked.connect(lambda: self.request_nav_action.emit("prev_page"))
        self.btn_nav_next_page.clicked.connect(lambda: self.request_nav_action.emit("next_page"))
        self.btn_nav_next_doc.clicked.connect(lambda: self.request_nav_action.emit("next_doc"))

    def set_stores(self, opt_store: OptDocumentStore, metadata_dict: dict = None, base_dir: str = ""):
        self.opt_store = opt_store
        if metadata_dict is not None:
            self.metadata_dict.update(metadata_dict)
        self.base_dir = base_dir
        if self.current_doc_id:
            self._update_metadata_tab(self.current_doc_id)

    def clear_viewer(self):
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        # Clear web canvas
        self.web_view.page().runJavaScript("loadImage('');")
        self.meta_table.setRowCount(0)
        self.metadata_dict = {}
        self.lbl_status.setText("No document loaded")
        if hasattr(self, "lbl_nav_counter"):
            self.lbl_nav_counter.setText("Doc 0 of 0 | Page 0 of 0")
        self.current_doc_id = ""
        self.current_page_idx = 0
        self._clear_temp_image()

    def _clear_temp_image(self):
        if self.current_temp_img and os.path.exists(self.current_temp_img):
            try:
                os.remove(self.current_temp_img)
            except Exception:
                pass
            self.current_temp_img = ""

    def record_selected(self, record_id: str, page_idx: int = 0):
        """
        Slot called when a record is selected in the UI. Loads page via background thread.
        """
        self.current_doc_id = str(record_id)
        self.current_page_idx = page_idx

        # 1. Update Metadata Tab
        self._update_metadata_tab(self.current_doc_id)

        # 2. Update Image Tab
        doc = self.opt_store.get_document(self.current_doc_id)
        if not doc or not doc.image_paths:
            self.web_view.page().runJavaScript("loadImage('');")
            self.lbl_status.setText(f"No images linked for DocID: {self.current_doc_id}")
            self.page_changed.emit(self.current_doc_id, 0, 0)
            return

        self.total_doc_pages = len(doc.image_paths)
        target_page = max(0, min(self.current_page_idx, self.total_doc_pages - 1))
        img_path = doc.image_paths[target_page]

        self.lbl_status.setText(f"Loading {os.path.basename(img_path)}...")

        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()

        self.worker = ImageRenderWorker(
            img_path, 
            page_index=target_page, 
            dpi=300, 
            base_dir=self.base_dir, 
            parent=self
        )
        self.worker.image_rendered.connect(self._on_image_rendered)
        self.worker.start()

    def _on_image_rendered(self, temp_img_path: str, page_idx: int, total_pages: int, err_msg: str):
        if err_msg or not temp_img_path or not os.path.exists(temp_img_path):
            self.lbl_status.setText(f"Error: {err_msg or 'Failed to load image path'}")
            return

        self._clear_temp_image()
        self.current_temp_img = temp_img_path

        # Convert to local file URL for Chromium to load safely
        file_url = QUrl.fromLocalFile(temp_img_path).toString()
        self.web_view.page().runJavaScript(f"loadImage('{file_url}');")

        bates = ""
        doc = self.opt_store.get_document(self.current_doc_id)
        if doc and self.current_page_idx < len(doc.bates_list):
            bates = doc.bates_list[self.current_page_idx]

        status_text = f"DocID: {self.current_doc_id} | Page {self.current_page_idx + 1} of {self.total_doc_pages}"
        if bates:
            status_text += f" ({bates})"
        self.lbl_status.setText(status_text)
        if hasattr(self, "lbl_nav_counter"):
            self.lbl_nav_counter.setText(status_text)

        # Apply persisted view mode (Fit Width vs Fit Page)
        self.web_view.page().runJavaScript(f"setViewMode('{self.view_mode}');")
        self.page_changed.emit(self.current_doc_id, self.current_page_idx + 1, self.total_doc_pages)

    def zoom_in(self):
        self.web_view.page().runJavaScript("zoom(1.15);")

    def zoom_out(self):
        self.web_view.page().runJavaScript("zoom(0.85);")

    def reset_zoom(self):
        self.web_view.page().runJavaScript("zoomPercent(100);")

    def fit_page(self):
        self.view_mode = "fit_page"
        self.web_view.page().runJavaScript("setViewMode('fit_page');")

    def fit_width(self):
        self.view_mode = "fit_width"
        self.web_view.page().runJavaScript("setViewMode('fit_width');")

    def _update_metadata_tab(self, doc_id: str):
        record_data = self.metadata_dict.get(doc_id)
        if record_data is None:
            doc_id_lower = str(doc_id).strip().lower()
            for k, v in self.metadata_dict.items():
                if str(k).strip().lower() == doc_id_lower:
                    record_data = v
                    break

        if record_data is None and len(self.metadata_dict) == 1:
            record_data = next(iter(self.metadata_dict.values()))

        record_data = record_data or {}
        self.meta_table.setRowCount(len(record_data))
        for row, (k, v) in enumerate(record_data.items()):
            self.meta_table.setItem(row, 0, QTableWidgetItem(str(k)))
            self.meta_table.setItem(row, 1, QTableWidgetItem(str(v)))
        self.filter_metadata_table()
        
        # Dynamically size columns to fit longest fields/values
        self.meta_table.resizeColumnToContents(0)
        self.meta_table.resizeColumnToContents(1)

    def filter_metadata_table(self):
        query = self.record_search.text().lower()
        hide_empty = self.chk_hide_empty_fields.isChecked()

        for r in range(self.meta_table.rowCount()):
            key_item = self.meta_table.item(r, 0)
            val_item = self.meta_table.item(r, 1)

            key_str = key_item.text().lower() if key_item else ""
            val_str = val_item.text() if val_item else ""
            val_lower = val_str.lower()

            is_empty = not val_str.strip()
            matches_search = not query or (query in key_str or query in val_lower)

            if hide_empty and is_empty:
                self.meta_table.setRowHidden(r, True)
            elif not matches_search:
                self.meta_table.setRowHidden(r, True)
            else:
                self.meta_table.setRowHidden(r, False)

    def closeEvent(self, event):
        self._clear_temp_image()
        super().closeEvent(event)

