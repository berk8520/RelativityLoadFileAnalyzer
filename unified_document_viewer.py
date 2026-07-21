"""
Unified Document Viewer Widget for Relativity Load File Analyzer.
Contains a QTabWidget with 'Metadata' (record detail table) and 'Image' (QGraphicsView image viewer with pan/zoom).
"""

import os
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem, QTableWidget, QTableWidgetItem, QHeaderView, QLabel,
    QPushButton, QFrame, QCheckBox, QLineEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QPointF
from PyQt5.QtGui import QPixmap, QTransform, QPainter, QWheelEvent, QMouseEvent

from image_render_worker import ImageRenderWorker
from opt_engine import OptDocumentStore, OptDocument


class ZoomableGraphicsView(QGraphicsView):
    """
    QGraphicsView with smooth pan (middle/left drag) and mouse-wheel zoom centered on cursor.
    """
    # Signal emitted when scale changes: (zoom_percentage_int)
    zoom_changed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_zoom = 100
        self.setRenderHints(
            QPainter.Antialiasing | 
            QPainter.TextAntialiasing | 
            QPainter.SmoothPixmapTransform | 
            QPainter.HighQualityAntialiasing
        )
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setStyleSheet("background-color: #0F172A; border: none;")
        self._zoom_factor = 1.15

    def wheelEvent(self, event: QWheelEvent):
        if event.angleDelta().y() > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        self.scale(self._zoom_factor, self._zoom_factor)
        self._current_zoom = int(round(self._current_zoom * self._zoom_factor))
        self.zoom_changed.emit(self._current_zoom)
        self.update_transformation_mode()

    def zoom_out(self):
        self.scale(1.0 / self._zoom_factor, 1.0 / self._zoom_factor)
        self._current_zoom = int(round(self._current_zoom / self._zoom_factor))
        self.zoom_changed.emit(self._current_zoom)
        self.update_transformation_mode()

    def fit_in_view_custom(self, item, aspect_ratio_mode=Qt.KeepAspectRatio):
        if item and item.scene():
            self.fitInView(item, aspect_ratio_mode)
            # Recompute zoom factor based on fit scale
            self.recompute_fit_zoom(item)
            self.update_transformation_mode()

    def reset_zoom(self):
        self.resetTransform()
        self._current_zoom = 100
        self.zoom_changed.emit(self._current_zoom)
        self.update_transformation_mode()

    def recompute_fit_zoom(self, item):
        rect = item.boundingRect()
        if rect.width() > 0:
            scale_x = self.viewport().width() / rect.width()
            self._current_zoom = int(round(scale_x * 100))
            self.zoom_changed.emit(self._current_zoom)

    def update_transformation_mode(self):
        # Retrieve QGraphicsPixmapItem from current scene and apply original quality SmoothTransformation at all levels
        scene = self.scene()
        if scene:
            for item in scene.items():
                if isinstance(item, QGraphicsPixmapItem):
                    item.setTransformationMode(Qt.SmoothTransformation)


class UnifiedDocumentViewer(QWidget):
    """
    Reusable Document Viewer Component with Metadata & Image tabs.
    Listens to record_selected(record_id: str) signal.
    """
    # Signals
    request_nav_action = pyqtSignal(str)
    page_changed = pyqtSignal(str, int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.opt_store: OptDocumentStore = OptDocumentStore()
        self.metadata_dict: dict = {}  # {DocID: {Field: Value}}
        self.base_dir: str = ""
        self.current_doc_id: str = ""
        self.current_page_idx: int = 0
        self.worker: ImageRenderWorker = None
        self.view_mode: str = "fit_page"  # "fit_page", "fit_width"

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

        # Toolbar overlay controls (Fit Width, Fit Page, Zoom In, Zoom Out, Reset)
        tb_layout = QHBoxLayout()
        tb_layout.setContentsMargins(2, 2, 2, 2)
        
        self.btn_fit_page = QPushButton("Fit Page")
        self.btn_fit_width = QPushButton("Fit Width")
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_out = QPushButton("-")
        self.btn_reset_zoom = QPushButton("100%")

        for btn in (self.btn_fit_page, self.btn_fit_width, self.btn_zoom_in, self.btn_zoom_out, self.btn_reset_zoom):
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

        # QGraphicsView setup
        self.graphics_scene = QGraphicsScene(self)
        self.graphics_view = ZoomableGraphicsView(self)
        self.graphics_view.setScene(self.graphics_scene)
        self.pixmap_item = QGraphicsPixmapItem()
        self.graphics_scene.addItem(self.pixmap_item)

        img_layout.addWidget(self.graphics_view)

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

        self.meta_table = QTableWidget()
        self.meta_table.setColumnCount(2)
        self.meta_table.setHorizontalHeaderLabels(["Field", "Value"])
        self.meta_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Interactive)
        self.meta_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
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
        self.btn_zoom_in.clicked.connect(self.graphics_view.zoom_in)
        self.btn_zoom_out.clicked.connect(self.graphics_view.zoom_out)
        self.btn_reset_zoom.clicked.connect(self.graphics_view.reset_zoom)
        self.btn_fit_page.clicked.connect(self.fit_page)
        self.btn_fit_width.clicked.connect(self.fit_width)
        self.graphics_view.zoom_changed.connect(lambda pct: self.btn_reset_zoom.setText(f"{pct}%"))
        
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
            # Overwrite or merge changes dynamically
            self.metadata_dict.update(metadata_dict)
        self.base_dir = base_dir
        if self.current_doc_id:
            self._update_metadata_tab(self.current_doc_id)

    def clear_viewer(self):
        # Cancel any active render worker thread
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        self.graphics_scene.clear()
        self.pixmap_item = QGraphicsPixmapItem()
        self.graphics_scene.addItem(self.pixmap_item)
        self.meta_table.setRowCount(0)
        self.metadata_dict = {}
        self.lbl_status.setText("No document loaded")
        if hasattr(self, "lbl_nav_counter"):
            self.lbl_nav_counter.setText("Doc 0 of 0 | Page 0 of 0")
        self.current_doc_id = ""
        self.current_page_idx = 0

    def record_selected(self, record_id: str, page_idx: int = 0):
        """
        Slot called when a record is selected in the UI.
        Loads page synchronously or asynchronously via background thread.
        """
        self.current_doc_id = str(record_id)
        self.current_page_idx = page_idx

        # 1. Update Metadata Tab
        self._update_metadata_tab(self.current_doc_id)

        # 2. Update Image Tab
        doc = self.opt_store.get_document(self.current_doc_id)
        if not doc or not doc.image_paths:
            self.graphics_scene.clear()
            self.pixmap_item = QGraphicsPixmapItem()
            self.graphics_scene.addItem(self.pixmap_item)
            self.lbl_status.setText(f"No images linked for DocID: {self.current_doc_id}")
            self.page_changed.emit(self.current_doc_id, 0, 0)
            return

        self.total_doc_pages = len(doc.image_paths)
        target_page = max(0, min(self.current_page_idx, self.total_doc_pages - 1))
        img_path = doc.image_paths[target_page]

        self.lbl_status.setText(f"Loading {os.path.basename(img_path)}...")

        # Get target bounds from the viewport size
        self.worker = ImageRenderWorker(
            img_path, 
            page_index=target_page, 
            dpi=300, 
            base_dir=self.base_dir, 
            parent=self
        )
        self.worker.image_rendered.connect(self._on_image_rendered)
        self.worker.start()

    def _on_image_rendered(self, pixmap: QPixmap, page_idx: int, total_pages: int, err_msg: str):
        if err_msg or pixmap.isNull():
            self.lbl_status.setText(f"Error: {err_msg or 'Failed to load image pixmap'}")
            return

        self.graphics_scene.clear()
        self.pixmap_item = QGraphicsPixmapItem(pixmap)
        self.graphics_scene.addItem(self.pixmap_item)
        self.graphics_view.update_transformation_mode()
        self.graphics_scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())

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
        if self.view_mode == "fit_width":
            self.fit_width()
        else:
            self.fit_page()

        self.page_changed.emit(self.current_doc_id, self.current_page_idx + 1, self.total_doc_pages)

    def fit_page(self):
        self.view_mode = "fit_page"
        if self.pixmap_item and not self.pixmap_item.pixmap().isNull():
            self.graphics_view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
            self.graphics_view.recompute_fit_zoom(self.pixmap_item)
            self.graphics_view.update_transformation_mode()
            self.graphics_view.verticalScrollBar().setValue(0)

    def fit_width(self):
        self.view_mode = "fit_width"
        if self.pixmap_item and not self.pixmap_item.pixmap().isNull():
            rect = self.pixmap_item.boundingRect()
            vw = self.graphics_view.viewport().width() - 12
            if vw > 0 and rect.width() > 0:
                scale_factor = vw / rect.width()
                self.graphics_view.resetTransform()
                self.graphics_view.scale(scale_factor, scale_factor)
                self.graphics_view.recompute_fit_zoom(self.pixmap_item)
                self.graphics_view.update_transformation_mode()
                # Scroll all the way to top of page
                self.graphics_view.verticalScrollBar().setValue(0)

    def _update_metadata_tab(self, doc_id: str):
        record_data = self.metadata_dict.get(doc_id)
        if record_data is None:
            # Case-insensitive lookup
            doc_id_lower = str(doc_id).strip().lower()
            for k, v in self.metadata_dict.items():
                if str(k).strip().lower() == doc_id_lower:
                    record_data = v
                    break

        if record_data is None and len(self.metadata_dict) == 1:
            # Fallback if metadata_dict was passed containing a single active selection
            record_data = next(iter(self.metadata_dict.values()))

        record_data = record_data or {}
        self.meta_table.setRowCount(len(record_data))
        for row, (k, v) in enumerate(record_data.items()):
            self.meta_table.setItem(row, 0, QTableWidgetItem(str(k)))
            self.meta_table.setItem(row, 1, QTableWidgetItem(str(v)))
        self.filter_metadata_table()

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

