import sys
import os
import traceback
import datetime
import polars as pl

def my_excepthook(type, value, tback):
    with open("crash.log", "w") as f:
        f.write(str(datetime.datetime.now()) + "\n")
        traceback.print_exception(type, value, tback, file=f)
    sys.__excepthook__(type, value, tback)

sys.excepthook = my_excepthook

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QTabWidget, QTableView,
    QHeaderView, QLineEdit, QComboBox, QFrame, QMessageBox, QProgressDialog,
    QDialog, QTextEdit, QSplitter, QMenu, QSpinBox, QFormLayout, QCheckBox, QAction,
    QGridLayout, QListWidget
)
from PyQt5.QtCore import Qt, QSize, QSettings
from PyQt5.QtGui import QIcon, QFont, QPixmap, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QColor
import processor
import opt_engine
from opt_engine import OptDocumentStore, OptDocument, parse_image_load_file, infer_base_dir, resolve_full_image_path
from unified_document_viewer import UnifiedDocumentViewer
from pyside_workers import AnalysisWorker, RemapWorker, GapWorker, PreviewSearchWorker, ReplaceWorker, AppendFieldWorker, MergeFieldsWorker, MassRedactionWorker
from pyside_models import SchemaTableModel, SchemaFilterProxyModel, GapTableModel, PreviewTableModel, RecordTableModel, ImagePageTableModel


def get_asset_path(*args):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, *args)

def apply_dark_titlebar(window):
    import sys
    if sys.platform == 'win32':
        import ctypes
        try:
            hwnd = int(window.winId())
            DwmSetWindowAttribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
            DwmSetWindowAttribute.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
            DwmSetWindowAttribute(hwnd, 20, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int(2)))
            DwmSetWindowAttribute(hwnd, 19, ctypes.byref(ctypes.c_int(2)), ctypes.sizeof(ctypes.c_int(2)))
        except Exception:
            pass

def show_dark_message(parent, title, text, icon=QMessageBox.Information):
    from PyQt5.QtCore import Qt
    msg = QMessageBox(icon, title, text, QMessageBox.Ok, parent)
    msg.setStyleSheet(GLOBAL_STYLE)
    msg.setWindowFlags(msg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
    apply_dark_titlebar(msg)
    return msg.exec()

def show_dark_warning_yes_no_cancel(parent, title, text):
    from PyQt5.QtCore import Qt
    msg = QMessageBox(QMessageBox.Warning, title, text, QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, parent)
    msg.setStyleSheet(GLOBAL_STYLE)
    msg.setWindowFlags(msg.windowFlags() & ~Qt.WindowContextHelpButtonHint)
    apply_dark_titlebar(msg)
    return msg.exec()


# --- QSS Style (Slate Dark Theme) ---
GLOBAL_STYLE = """
QMainWindow, QDialog {
    background-color: #0F172A;
}
QWidget {
    color: #FFFFFF;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    font-size: 13px;
}
QFrame#Card {
    background-color: #1E293B;
    border: 1px solid #334155;
    border-radius: 8px;
}
QFrame#Card QLabel {
    color: #FFFFFF;
}
QFrame#Card QLabel#CardTitle {
    color: #94A3B8;
    font-size: 11px;
}
QFrame#Card QLabel#CardValue {
    font-weight: bold;
    font-size: 14px;
}
QPushButton {
    background-color: #1D4ED8;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #2563EB;
}
QPushButton:disabled {
    background-color: #334155;
    color: #94A3B8;
}
QPushButton#BtnExportRemapped, QPushButton#BtnOpen, QPushButton#BtnHelp {
    background-color: #15803D;
}
QPushButton#BtnExportRemapped:hover, QPushButton#BtnOpen:hover, QPushButton#BtnHelp:hover {
    background-color: #16A34A;
}
QPushButton#BtnTools {
    background-color: #8B5CF6;
}
QPushButton#BtnTools:hover {
    background-color: #A78BFA;
}
QLineEdit, QComboBox, QTextEdit, QSpinBox {
    background-color: #1E293B;
    border: 1px solid #475569;
    border-radius: 4px;
    padding: 6px;
    color: #F8FAFC;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #3B82F6;
}
QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #1E293B;
    border-radius: 8px;
}
QTabBar::tab {
    background-color: #0F172A;
    color: #94A3B8;
    padding: 8px 16px;
    border: 1px solid #334155;
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    margin-right: 2px;
}
QTabBar::tab:selected {
    background-color: #1E293B;
    color: #FFFFFF;
    border-bottom: 2px solid #3B82F6;
}
QTableView {
    background-color: #1E293B;
    alternate-background-color: #0F172A;
    border: none;
    gridline-color: #334155;
}
QHeaderView {
    background-color: #0F172A;
}
QHeaderView::section, QTableCornerButton::section {
    background-color: #0F172A;
    color: #FFFFFF;
    font-weight: bold;
    padding: 6px;
    border: 1px solid #334155;
}
QComboBox QAbstractItemView {
    background-color: #1E293B;
    color: #FFFFFF;
    selection-background-color: #3B82F6;
    selection-color: #FFFFFF;
}
QMenu {
    background-color: #1E293B;
    color: #FFFFFF;
    border: 1px solid #475569;
}
QMenu::item:selected {
    background-color: #3B82F6;
}
QScrollBar:vertical {
    background-color: #0F172A;
    width: 12px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background-color: #334155;
    min-height: 20px;
    border-radius: 5px;
    margin: 1px;
}
QScrollBar::handle:vertical:hover {
    background-color: #475569;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    background-color: #0F172A;
    height: 12px;
    margin: 0px;
}
QScrollBar::handle:horizontal {
    background-color: #334155;
    min-width: 20px;
    border-radius: 5px;
    margin: 1px;
}
QScrollBar::handle:horizontal:hover {
    background-color: #475569;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}
QSplitter::handle {
    background-color: #334155;
}
QSplitter::handle:horizontal {
    width: 2px;
}
QSplitter::handle:vertical {
    height: 2px;
}
"""

class StatusCard(QFrame):
    def __init__(self, title, initial_value="Not Detected", color=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        if color:
            self.setStyleSheet(f"QFrame#Card {{ background-color: #1E293B; border-radius: 8px; border: 1px solid #334155; border-top: 3px solid {color}; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        self.val_label = QLabel(initial_value)
        self.val_label.setObjectName("CardValue")
        
        layout.addWidget(title_label)
        layout.addWidget(self.val_label)
        
    def set_value(self, value):
        self.val_label.setText(str(value))

class InlineSearchCard(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet("QFrame#Card { background-color: #1E3A8A; border-radius: 6px; border: 1.5px solid #3B82F6; }")
        self.setFixedHeight(32)
        from PyQt5.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(5)
        
        title_label = QLabel("Applied Search:")
        title_label.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        
        self.val_label = QLabel("None")
        self.val_label.setStyleSheet("color: #60A5FA; font-size: 13px; font-weight: bold;")
        
        layout.addWidget(title_label)
        layout.addWidget(self.val_label)
        layout.addStretch()
        
    def set_value(self, value):
        self.val_label.setText(str(value))


class CopyableTableView(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def show_context_menu(self, pos):
        index = self.indexAt(pos)
        if not index.isValid():
            return
            
        menu = QMenu(self)
        copy_action = menu.addAction("Copy Field Value")
        
        action = menu.exec(self.viewport().mapToGlobal(pos))
        if action == copy_action:
            QApplication.clipboard().setText(str(index.data()))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_C and (event.modifiers() & Qt.ControlModifier):
            selected = self.selectedIndexes()
            if not selected:
                return
            
            # Group by row
            row_map = {}
            for index in selected:
                row_map.setdefault(index.row(), {})[index.column()] = index.data()
            
            # Format as TSV
            rows_str = []
            for row in sorted(row_map.keys()):
                cols = row_map[row]
                row_str = "\t".join(str(cols[col]) for col in sorted(cols.keys()))
                rows_str.append(row_str)
                
            QApplication.clipboard().setText("\n".join(rows_str))
        else:
            super().keyPressEvent(event)


class ReplaceDialog(QDialog):
    def __init__(self, columns, filtered_count=0, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Find & Replace")
        self.resize(400, 250)
        apply_dark_titlebar(self)
        
        layout = QFormLayout(self)
        
        self.cb_field = QComboBox()
        self.cb_field.addItems(columns)
        
        self.txt_find = QLineEdit()
        self.txt_find.setPlaceholderText("Search string or Regex")
        
        self.txt_replace = QLineEdit()
        
        self.chk_regex = QCheckBox("Use Regex")
        self.chk_regex.setChecked(False)
        
        self.chk_filtered = QCheckBox(f"Apply only to current search results ({filtered_count} records)")
        self.chk_filtered.setChecked(True)
        if filtered_count == 0:
            self.chk_filtered.setVisible(False)
            self.chk_filtered.setChecked(False)
        
        self.btn_replace = QPushButton("Replace")
        self.btn_replace.clicked.connect(self.accept)
        
        layout.addRow("Target Field:", self.cb_field)
        layout.addRow("Find Pattern:", self.txt_find)
        layout.addRow("Replace With:", self.txt_replace)
        layout.addRow("", self.chk_regex)
        layout.addRow("", self.chk_filtered)
        layout.addRow(QLabel(""))
        layout.addRow(self.btn_replace)
        


    def get_data(self):
        return self.cb_field.currentText(), self.txt_find.text(), self.txt_replace.text(), self.chk_regex.isChecked(), self.chk_filtered.isChecked()


class DateFormatDialog(QDialog):
    def __init__(self, columns, filtered_count=0, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Format Dates")
        self.resize(450, 250)
        apply_dark_titlebar(self)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # Tab 1: Format Existing
        self.tab_format = QWidget()
        fmt_layout = QFormLayout(self.tab_format)
        self.cb_field = QComboBox()
        self.cb_field.addItems(columns)
        self.cb_format = QComboBox()
        self.cb_format.addItems([
            "MM/DD/YYYY HH:MM:SS",
            "YYYY-MM-DD HH:MM:SS",
            "MM/DD/YYYY",
            "YYYY-MM-DD"
        ])
        fmt_layout.addRow("Target Field:", self.cb_field)
        fmt_layout.addRow("Target Format:", self.cb_format)
        
        # Tab 2: Merge Fields
        self.tab_merge = QWidget()
        merge_layout = QFormLayout(self.tab_merge)
        self.cb_date_field = QComboBox()
        self.cb_date_field.addItems(columns)
        self.cb_time_field = QComboBox()
        self.cb_time_field.addItems(columns)
        self.txt_new_field = QLineEdit()
        self.txt_new_field.setPlaceholderText("New Date/Time Field Name")
        self.cb_merge_format = QComboBox()
        self.cb_merge_format.addItems([
            "MM/DD/YYYY HH:MM:SS",
            "YYYY-MM-DD HH:MM:SS"
        ])
        merge_layout.addRow("Date Field:", self.cb_date_field)
        merge_layout.addRow("Time Field:", self.cb_time_field)
        merge_layout.addRow("New Field Name:", self.txt_new_field)
        merge_layout.addRow("Target Format:", self.cb_merge_format)
        
        self.tabs.addTab(self.tab_format, "Format Existing Field")
        self.tabs.addTab(self.tab_merge, "Merge Date & Time")
        layout.addWidget(self.tabs)
        
        self.chk_filtered = QCheckBox(f"Apply only to current search results ({filtered_count} records)")
        self.chk_filtered.setChecked(True)
        if filtered_count == 0:
            self.chk_filtered.setVisible(False)
            self.chk_filtered.setChecked(False)
        layout.addWidget(self.chk_filtered)
        
        self.btn_format = QPushButton("Run")
        self.btn_format.clicked.connect(self.accept)
        layout.addWidget(self.btn_format)
        


    def get_data(self):
        data = {}
        if self.tabs.currentIndex() == 0:
            data = {
                "mode": "format",
                "field": self.cb_field.currentText(),
                "format": self.cb_format.currentText()
            }
        else:
            data = {
                "mode": "merge",
                "date_field": self.cb_date_field.currentText(),
                "time_field": self.cb_time_field.currentText(),
                "new_field": self.txt_new_field.text(),
                "format": self.cb_merge_format.currentText()
            }
        return data

class AppendFieldDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QSpinBox
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Append New Field")
        self.resize(400, 280)
        apply_dark_titlebar(self)
        
        layout = QFormLayout(self)
        
        self.txt_field_name = QLineEdit()
        self.txt_field_name.setPlaceholderText("New Field Name")
        
        self.cb_val_type = QComboBox()
        self.cb_val_type.addItems(["Static Text", "Record Number (1-based)", "Copy from Field"])
        
        self.txt_static_val = QLineEdit()
        self.txt_static_val.setPlaceholderText("Static Value")
        
        self.cb_copy_field = QComboBox()
        self.cb_copy_field.addItems(columns)
        self.cb_copy_field.setEnabled(False)
        
        self.txt_prefix = QLineEdit()
        self.txt_prefix.setPlaceholderText("e.g. DOC_")
        self.txt_prefix.setEnabled(False)
        
        self.sb_padding = QSpinBox()
        self.sb_padding.setRange(0, 20)
        self.sb_padding.setValue(0)
        self.sb_padding.setEnabled(False)
        
        self.cb_val_type.currentTextChanged.connect(self.on_val_type_changed)
        
        self.btn_run = QPushButton("Append")
        self.btn_run.clicked.connect(self.accept)
        
        layout.addRow("New Field Name:", self.txt_field_name)
        layout.addRow("Value Type:", self.cb_val_type)
        layout.addRow("Static Value:", self.txt_static_val)
        layout.addRow("Copy Source Field:", self.cb_copy_field)
        layout.addRow("Record Number Prefix:", self.txt_prefix)
        layout.addRow("Zero Padding Width:", self.sb_padding)
        layout.addRow(QLabel(""))
        layout.addRow(self.btn_run)
        
    def on_val_type_changed(self, text):
        self.txt_static_val.setEnabled(text == "Static Text")
        self.cb_copy_field.setEnabled(text == "Copy from Field")
        self.txt_prefix.setEnabled(text == "Record Number (1-based)")
        self.sb_padding.setEnabled(text == "Record Number (1-based)")
        
    def get_data(self):
        val_type_map = {
            "Static Text": "static",
            "Record Number (1-based)": "row_num",
            "Copy from Field": "copy"
        }
        return (
            self.txt_field_name.text().strip(),
            val_type_map[self.cb_val_type.currentText()],
            self.txt_static_val.text(),
            self.cb_copy_field.currentText(),
            self.txt_prefix.text(),
            self.sb_padding.value()
        )

class MergeFieldsDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Merge Two Fields")
        self.resize(400, 250)
        apply_dark_titlebar(self)
        
        layout = QFormLayout(self)
        
        self.cb_first = QComboBox()
        self.cb_first.addItems(columns)
        
        self.cb_second = QComboBox()
        self.cb_second.addItems(columns)
        
        self.txt_separator = QLineEdit()
        self.txt_separator.setPlaceholderText("e.g. _ or - or Space")
        
        self.txt_new_field = QLineEdit()
        self.txt_new_field.setPlaceholderText("New Merged Field Name")
        
        self.btn_run = QPushButton("Merge")
        self.btn_run.clicked.connect(self.accept)
        
        layout.addRow("First Field:", self.cb_first)
        layout.addRow("Second Field:", self.cb_second)
        layout.addRow("Separator Between:", self.txt_separator)
        layout.addRow("New Field Name:", self.txt_new_field)
        layout.addRow(QLabel(""))
        layout.addRow(self.btn_run)
        
    def get_data(self):
        return (
            self.cb_first.currentText(),
            self.cb_second.currentText(),
            self.txt_separator.text(),
            self.txt_new_field.text().strip()
        )

class ExportDialog(QDialog):
    def __init__(self, is_filtered_active=False, is_mapped_active=False, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Export Options")
        self.resize(380, 240)
        apply_dark_titlebar(self)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        self.chk_filter_sort = QCheckBox("Apply field selection & order")
        self.chk_filter_sort.setChecked(True)
        self.chk_filter_sort.setToolTip("Only export columns checked on the Schema Analysis tab, in their custom order.")
        
        self.chk_mapped_names = QCheckBox("Apply mapped field names")
        self.chk_mapped_names.setChecked(is_mapped_active)
        self.chk_mapped_names.setToolTip("Rename exported headers using the loaded cross-reference mapping.")
        
        self.chk_search_results = QCheckBox("Limit export to search results")
        self.chk_search_results.setChecked(is_filtered_active)
        self.chk_search_results.setEnabled(is_filtered_active)
        self.chk_search_results.setToolTip("Only export records matching the current search filter.")
        
        self.chk_include_audit = QCheckBox("Include system audit fields (Error & Modification)")
        self.chk_include_audit.setChecked(False)
        self.chk_include_audit.setToolTip("Include the internal 'Error' and 'Modification' fields in the exported file.")
        
        layout.addWidget(QLabel("Configure your export options:"))
        layout.addWidget(self.chk_filter_sort)
        layout.addWidget(self.chk_mapped_names)
        layout.addWidget(self.chk_search_results)
        layout.addWidget(self.chk_include_audit)
        
        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("Export")
        self.btn_export.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        # Style cancel button
        self.btn_cancel.setStyleSheet("background-color: #334155;")
        
        btn_layout.addWidget(self.btn_export)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
    def get_data(self):
        return (
            self.chk_filter_sort.isChecked(),
            self.chk_mapped_names.isChecked(),
            self.chk_search_results.isChecked(),
            self.chk_include_audit.isChecked()
        )


class MassRedactionDialog(QDialog):
    def __init__(self, lf_headers, csv_headers, csv_path, parent=None):
        super().__init__(parent)
        self.lf_headers = lf_headers
        self.csv_headers = csv_headers
        self.csv_path = csv_path
        
        from PyQt5.QtCore import Qt, QSettings
        from PyQt5.QtWidgets import QListWidgetItem
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Mass Field Redaction")
        self.resize(600, 500)
        apply_dark_titlebar(self)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # History Selection Dropdown
        history_layout = QHBoxLayout()
        history_layout.addWidget(QLabel("Pre-populate from Past Run:"))
        self.cb_history = QComboBox()
        self.cb_history.addItem("-- None --")
        
        # Load history
        settings = QSettings("RelativityLoadFileAnalyzer", "MassRedactionHistory")
        self.history_records = settings.value("history", [])
        for record in self.history_records:
            date_val = record.get("date", "")
            fields_val = ", ".join(record.get("fields", []))
            self.cb_history.addItem(f"{date_val} (Fields: {fields_val})")
            
        self.cb_history.currentIndexChanged.connect(self.on_history_selected)
        history_layout.addWidget(self.cb_history)
        main_layout.addLayout(history_layout)
        
        # 1. Join configuration layout
        grid = QGridLayout()
        grid.setSpacing(8)
        
        grid.addWidget(QLabel("Load File Match Field:"), 0, 0)
        self.cb_lf_match = QComboBox()
        self.cb_lf_match.addItems(self.lf_headers)
        for idx, h in enumerate(self.lf_headers):
            if h.lower() in ("docid", "begdoc", "controlnumber", "control number"):
                self.cb_lf_match.setCurrentIndex(idx)
                break
        grid.addWidget(self.cb_lf_match, 0, 1)
        
        grid.addWidget(QLabel("CSV Match Field (Match Identifier):"), 1, 0)
        self.cb_csv_match = QComboBox()
        self.cb_csv_match.addItems(self.csv_headers)
        for idx, h in enumerate(self.csv_headers):
            if h.lower() in ("controlnumber", "control number", "docid", "begdoc"):
                self.cb_csv_match.setCurrentIndex(idx)
                break
        grid.addWidget(self.cb_csv_match, 1, 1)
        
        grid.addWidget(QLabel("Replacement Text:"), 2, 0)
        self.txt_replacement = QLineEdit("[REDACTED]")
        grid.addWidget(self.txt_replacement, 2, 1)
        
        main_layout.addLayout(grid)
        
        # 2. Target Fields Check List
        main_layout.addWidget(QLabel("Select Target Fields to Redact:"))
        self.lst_targets = QListWidget()
        self.lst_targets.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; color: #FFFFFF;")
        
        for h in self.lf_headers:
            if h.lower() not in ("error", "modification"):
                item = QListWidgetItem(h)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.lst_targets.addItem(item)
                
        main_layout.addWidget(self.lst_targets)
        
        # Import/Export configuration buttons
        config_buttons_layout = QHBoxLayout()
        self.btn_import = QPushButton("Import Field List")
        self.btn_import.clicked.connect(self.import_field_list)
        self.btn_import.setStyleSheet("background-color: #334155;")
        
        self.btn_export = QPushButton("Export Field List")
        self.btn_export.clicked.connect(self.export_field_list)
        self.btn_export.setStyleSheet("background-color: #334155;")
        
        config_buttons_layout.addWidget(self.btn_import)
        config_buttons_layout.addWidget(self.btn_export)
        main_layout.addLayout(config_buttons_layout)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_process = QPushButton("Process Redactions")
        self.btn_process.clicked.connect(self.accept)
        self.btn_process.setStyleSheet("background-color: #10B981; color: white;")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        
        btn_layout.addWidget(self.btn_process)
        btn_layout.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_layout)
        
    def on_history_selected(self, index):
        if index <= 0:
            return
        record = self.history_records[index - 1]
        fields = record.get("fields", [])
        value = record.get("value", "")
        
        # Update replacement text
        self.txt_replacement.setText(value)
        
        # Check matching fields
        fields_lower = {f.lower() for f in fields}
        for i in range(self.lst_targets.count()):
            item = self.lst_targets.item(i)
            if item.text().lower() in fields_lower:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
                
    def export_field_list(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Field List", "", "Text Files (*.txt)")
        if path:
            selected = []
            for i in range(self.lst_targets.count()):
                item = self.lst_targets.item(i)
                if item.checkState() == Qt.Checked:
                    selected.append(item.text())
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write("\n".join(selected))
                show_dark_message(self, "Success", f"Exported {len(selected)} fields to list.", QMessageBox.Information)
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to export fields:\n{str(e)}", QMessageBox.Critical)
                
    def import_field_list(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import Field List", "", "Text Files (*.txt)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    imported = [line.strip() for line in f if line.strip()]
                
                # Validate headers
                lf_set = {h.lower() for h in self.lf_headers}
                invalid = [f for f in imported if f.lower() not in lf_set]
                if invalid:
                    show_dark_message(
                        self, 
                        "Validation Error", 
                        f"Failed to import field list. The following fields do not exist in the current load file:\n\n" + "\n".join(invalid), 
                        QMessageBox.Critical
                    )
                    return
                    
                imported_lower = {f.lower() for f in imported}
                for i in range(self.lst_targets.count()):
                    item = self.lst_targets.item(i)
                    if item.text().lower() in imported_lower:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)
                show_dark_message(self, "Success", f"Imported selection for {len(imported)} fields.", QMessageBox.Information)
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to import fields:\n{str(e)}", QMessageBox.Critical)
                
    def get_selections(self):
        matched_fields = []
        for i in range(self.lst_targets.count()):
            item = self.lst_targets.item(i)
            if item.checkState() == Qt.Checked:
                matched_fields.append(item.text())
        return (
            self.cb_lf_match.currentText(),
            self.cb_csv_match.currentText(),
            self.txt_replacement.text(),
            matched_fields
        )


class BooleanQueryHighlighter(QSyntaxHighlighter):
    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import QRegExp, Qt
        self.error_start = -1
        self.error_end = -1
        
        self.rules = []
        
        # 1. Field brackets: [Custodian] -> Cyan #22D3EE
        field_format = QTextCharFormat()
        field_format.setForeground(QColor("#22D3EE"))
        field_format.setFontWeight(QFont.Bold)
        self.rules.append((QRegExp(r"\[[^\]]*\]"), field_format))
        
        # 2. String values: "value" -> Amber #F59E0B
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#F59E0B"))
        self.rules.append((QRegExp(r'"[^"]*"'), str_format))
        
        # 3. Connectives & Operators -> Pink/Magenta #EC4899
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#EC4899"))
        keyword_format.setFontWeight(QFont.Bold)
        keywords = [
            r"\bAND\b", r"\bOR\b", r"\bNOT\b",
            r"\bLIKE\b", r"\bCONTAINS\b", r"\bIS\b", r"\bSET\b",
            r"=", r"!="
        ]
        for kw in keywords:
            self.rules.append((QRegExp(kw, Qt.CaseInsensitive), keyword_format))

    def set_error_span(self, start, end):
        self.error_start = start
        self.error_end = end
        self.rehighlight()

    def highlightBlock(self, text):
        from PyQt5.QtCore import QRegExp, Qt
        # 1. Normal syntax coloring
        for pattern, fmt in self.rules:
            expression = QRegExp(pattern)
            index = expression.indexOf(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, fmt)
                index = expression.indexOf(text, index + length)
                
        # 2. Red squiggly underline
        if self.error_start != -1 and self.error_end != -1:
            err_fmt = QTextCharFormat()
            err_fmt.setUnderlineStyle(QTextCharFormat.WaveUnderline)
            err_fmt.setUnderlineColor(QColor("#EF4444"))
            
            start = max(0, min(self.error_start, len(text)))
            end = max(0, min(self.error_end, len(text)))
            length = end - start
            if length > 0:
                self.setFormat(start, length, err_fmt)

class QueryTextEdit(QTextEdit):
    def __init__(self, headers, parent=None):
        super().__init__(parent)
        from PyQt5.QtWidgets import QCompleter
        from PyQt5.QtCore import Qt
        
        self.headers = headers
        self.completer = QCompleter(self.headers, self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)
        
        popup = self.completer.popup()
        popup.setStyleSheet("background-color: #1E293B; color: #FFFFFF; border: 1px solid #334155; selection-background-color: #2563EB;")
        
        self.setLineWrapMode(QTextEdit.NoWrap)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedHeight(32)
        self.setStyleSheet("background-color: #0F172A; border: 1px solid #334155; border-radius: 6px; color: white; padding: 4px; font-size: 13px;")
        
        # Attach syntax highlighter
        self.highlighter = BooleanQueryHighlighter(self.document())

    def keyPressEvent(self, event):
        from PyQt5.QtCore import Qt
        if self.completer.popup().isVisible():
            if event.key() in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Escape, Qt.Key_Tab, Qt.Key_Backtab):
                event.ignore()
                return

        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            parent = self.parentWidget()
            while parent:
                if hasattr(parent, 'accept'):
                    parent.accept()
                    return
                parent = parent.parentWidget()
            event.ignore()
            return

        super().keyPressEvent(event)
        
        text = self.toPlainText()
        cursor = self.textCursor()
        cursor_pos = cursor.position()
        
        bracket_idx = text.rfind('[', 0, cursor_pos)
        close_idx = text.rfind(']', 0, cursor_pos)
        
        if bracket_idx != -1 and bracket_idx > close_idx:
            prefix = text[bracket_idx+1:cursor_pos]
            self.completer.setCompletionPrefix(prefix)
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))
            
            rect = self.cursorRect()
            rect.setWidth(popup.sizeHintForColumn(0) + popup.verticalScrollBar().sizeHint().width())
            self.completer.complete(rect)
        else:
            self.completer.popup().hide()

    def insert_completion(self, completion):
        text = self.toPlainText()
        cursor = self.textCursor()
        cursor_pos = cursor.position()
        bracket_idx = text.rfind('[', 0, cursor_pos)
        if bracket_idx != -1:
            has_close = (cursor_pos < len(text) and text[cursor_pos] == ']')
            cursor.setPosition(bracket_idx + 1)
            cursor.setPosition(cursor_pos, cursor.KeepAnchor)
            
            suffix = "]" if not has_close else ""
            cursor.insertText(completion + suffix)
            
            end_pos = bracket_idx + 1 + len(completion) + 1
            updated_text = self.toPlainText()
            has_space = (end_pos < len(updated_text) and updated_text[end_pos] == ' ')
            
            cursor.setPosition(end_pos)
            if not has_space:
                cursor.insertText(" ")
            else:
                cursor.setPosition(end_pos + 1)
                
            self.setTextCursor(cursor)

class SearchDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt, QTimer
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Search")
        self.resize(600, 420)
        apply_dark_titlebar(self)
        
        # Validation Timer to prevent lag while typing
        self.validation_timer = QTimer(self)
        self.validation_timer.setSingleShot(True)
        self.validation_timer.setInterval(300) # 300 ms debounce
        self.validation_timer.timeout.connect(self.validate_syntax)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        # Tab 1: Field Search
        self.tab_field = QWidget()
        field_layout = QFormLayout(self.tab_field)
        self.cb_field = QComboBox()
        self.cb_field.addItems(columns)
        self.txt_field_query = QLineEdit()
        self.chk_field_regex = QCheckBox("Use Regex")
        field_layout.addRow("Target Field:", self.cb_field)
        field_layout.addRow("Search Query:", self.txt_field_query)
        field_layout.addRow("", self.chk_field_regex)
        
        # Tab 2: Boolean Query Search
        self.tab_query = QWidget()
        query_layout = QVBoxLayout(self.tab_query)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(6)
        ops = ["AND", "OR", "NOT", "()", "[]", '""', "=", "!=", "LIKE", "CONTAINS", "IS SET"]
        for op in ops:
            btn = QPushButton(op)
            btn.setStyleSheet("background-color: #334155; color: white; padding: 4px 8px; font-weight: bold; border-radius: 4px; font-size: 11px;")
            btn.clicked.connect(lambda checked, o=op: self.insert_operator(o))
            buttons_layout.addWidget(btn)
        buttons_layout.addStretch()
        
        self.txt_query = QueryTextEdit(columns)
        self.txt_query.setPlaceholderText('e.g. [Custodian] = "Jones" AND ([Date] LIKE "2026*" OR [Error] CONTAINS "Merge")')
        self.lbl_syntax_status = QLabel("Enter a query...")
        self.lbl_syntax_status.setStyleSheet("color: #94A3B8; font-size: 11px;")
        
        # Structured Syntax Cheatsheet Panel
        cheatsheet = QFrame()
        cheatsheet.setStyleSheet("QFrame { background-color: #1E293B; border-radius: 6px; border: 1px solid #334155; }")
        cs_layout = QGridLayout(cheatsheet)
        cs_layout.setContentsMargins(8, 6, 8, 6)
        cs_layout.setHorizontalSpacing(15)
        cs_layout.setVerticalSpacing(4)
        
        headers_lbl = QLabel("Operator Usage Cheat Sheet:")
        headers_lbl.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px; border: none; background: transparent;")
        cs_layout.addWidget(headers_lbl, 0, 0, 1, 4)
        
        examples = [
            ("Exact Match:", '[Custodian] = "John Doe"'),
            ("Not Equal:", '[DocID] != "DOC001"'),
            ("Wildcard:", '[Custodian] LIKE "Jane*"'),
            ("Substring:", '[Error] CONTAINS "Merge"'),
            ("Compound:", '[DocID] = "DOC002" AND NOT [Custodian] LIKE "*Smith"'),
            ("Is Set:", '[Date] IS SET')
        ]
        
        for idx, (desc, val) in enumerate(examples):
            lbl_desc = QLabel(desc)
            lbl_desc.setStyleSheet("color: #94A3B8; font-size: 10px; border: none; font-weight: bold; background: transparent;")
            lbl_val = QLabel(val)
            lbl_val.setStyleSheet("color: #10B981; font-size: 10px; border: none; font-family: Consolas, monospace; background: transparent;")
            
            row = 1 + (idx // 2)
            col_offset = 0 if (idx % 2 == 0) else 2
            
            cs_layout.addWidget(lbl_desc, row, col_offset)
            cs_layout.addWidget(lbl_val, row, col_offset + 1)
            
        help_label = QLabel("Autocomplete pops up when typing '['. Click search buttons to quick-insert queries.")
        help_label.setStyleSheet("color: #64748B; font-size: 10px; margin-top: 2px;")
        
        query_layout.addWidget(QLabel("Boolean Query Expression:"))
        query_layout.addLayout(buttons_layout)
        query_layout.addWidget(self.txt_query)
        query_layout.addWidget(self.lbl_syntax_status)
        query_layout.addWidget(cheatsheet)
        query_layout.addWidget(help_label)
        query_layout.addStretch()
        
        self.txt_query.textChanged.connect(self.on_query_text_changed)
        
        self.tabs.addTab(self.tab_field, "Field Level Search")
        self.tabs.addTab(self.tab_query, "Boolean Query Search")
        layout.addWidget(self.tabs)
        
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.accept)
        layout.addWidget(self.btn_search)

    def on_query_text_changed(self):
        # Restart validation timer on every key stroke
        self.validation_timer.start()

    def insert_operator(self, op):
        cursor = self.txt_query.textCursor()
        
        if op == "()":
            cursor.insertText("()")
            cursor.movePosition(cursor.Left, cursor.MoveAnchor, 1)
        elif op == "[]":
            cursor.insertText("[]")
            cursor.movePosition(cursor.Left, cursor.MoveAnchor, 1)
        elif op == '""':
            cursor.insertText('""')
            cursor.movePosition(cursor.Left, cursor.MoveAnchor, 1)
        elif op in ("=", "!=", "LIKE", "CONTAINS"):
            cursor.insertText(f" {op} \"\"")
            cursor.movePosition(cursor.Left, cursor.MoveAnchor, 1)
        else:
            cursor.insertText(f" {op} ")
            
        self.txt_query.setTextCursor(cursor)
        self.txt_query.setFocus()

    def validate_syntax(self):
        query = self.txt_query.toPlainText().strip()
        if not query:
            self.lbl_syntax_status.setText("Enter a query...")
            self.lbl_syntax_status.setStyleSheet("color: #94A3B8; font-size: 11px;")
            self.txt_query.highlighter.set_error_span(-1, -1)
            return
            
        is_valid, err, start_pos, end_pos = processor.validate_query(query, self.txt_query.headers)
        if is_valid:
            self.lbl_syntax_status.setText("✓ Query syntax is valid")
            self.lbl_syntax_status.setStyleSheet("color: #10B981; font-size: 11px; font-weight: bold;")
            self.btn_search.setEnabled(True)
            self.txt_query.highlighter.set_error_span(-1, -1)
        else:
            self.lbl_syntax_status.setText(f"✗ Syntax Error: {err}")
            self.lbl_syntax_status.setStyleSheet("color: #EF4444; font-size: 11px; font-weight: bold;")
            self.btn_search.setEnabled(False)
            self.txt_query.highlighter.set_error_span(start_pos, end_pos)

    def get_data(self):
        if self.tabs.currentIndex() == 0:
            return {
                "mode": "field",
                "field": self.cb_field.currentText(),
                "query": self.txt_field_query.text(),
                "regex": self.chk_field_regex.isChecked()
            }
        else:
            return {
                "mode": "query",
                "query": self.txt_query.toPlainText()
            }

class GapReportDialog(QDialog):
    def __init__(self, file_path, analysis_results, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Gap Report")
        self.resize(700, 500)
        apply_dark_titlebar(self)
        
        self.file_path = file_path
        self.analysis_results = analysis_results
        self.gap_results = []
        
        layout = QVBoxLayout(self)
        
        # Gap Controls
        gap_ctrl_layout = QHBoxLayout()
        gap_ctrl_layout.addWidget(QLabel("Start Column:"))
        self.gap_start_cb = QComboBox()
        self.gap_start_cb.setMinimumWidth(180)
        gap_ctrl_layout.addWidget(self.gap_start_cb)
        
        gap_ctrl_layout.addWidget(QLabel("End Column (Optional):"))
        self.gap_end_cb = QComboBox()
        self.gap_end_cb.setMinimumWidth(180)
        gap_ctrl_layout.addWidget(self.gap_end_cb)
        
        self.btn_run_gap = QPushButton("Run Gap Analysis")
        self.btn_run_gap.setObjectName("BtnFindGaps")
        gap_ctrl_layout.addWidget(self.btn_run_gap)
        gap_ctrl_layout.addStretch()
        
        self.btn_export_gap = QPushButton("Export Gap CSV")
        self.btn_export_gap.setEnabled(False)
        gap_ctrl_layout.addWidget(self.btn_export_gap)
        
        layout.addLayout(gap_ctrl_layout)
        
        # Gap Table
        self.gap_table = QTableView()
        self.gap_table.setAlternatingRowColors(True)
        self.gap_model = GapTableModel()
        self.gap_table.setModel(self.gap_model)
        self.gap_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.gap_table)
        
        # Populate Comboboxes
        self.gap_all_columns = sorted([r["column"] for r in self.analysis_results], key=lambda x: x.lower())
        self.gap_start_cb.addItems(self.gap_all_columns)
        self.gap_end_cb.addItem("")
        self.gap_end_cb.addItems(self.gap_all_columns)
        
        for i, col in enumerate(self.gap_all_columns):
            if "begctrl" in col.lower() or "bates" in col.lower() or "control" in col.lower():
                self.gap_start_cb.setCurrentIndex(i)
                break
                
        # Connect Signals
        self.btn_run_gap.clicked.connect(self.run_gap_analysis)
        self.btn_export_gap.clicked.connect(self.export_gap_report)
        
    def run_gap_analysis(self):
        start_col = self.gap_start_cb.currentText()
        end_col = self.gap_end_cb.currentText() or None
        if not start_col:
            show_dark_message(self, "Warning", "Please select a Start Column.", QMessageBox.Warning)
            return
            
        self.progress = QProgressDialog("Running Gap Analysis...", None, 0, 0, self)
        self.progress.setStyleSheet(GLOBAL_STYLE)
        from PyQt5.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()
        
        self.worker = GapWorker(self.file_path, start_col, end_col)
        self.worker.finished.connect(self.on_gap_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        
    def on_gap_finished(self, results):
        self.progress.accept()
        self.gap_results = results
        self.gap_model.update_data(results)
        self.gap_table.resizeColumnsToContents()
        self.btn_export_gap.setEnabled(len(results) > 0)
        show_dark_message(self, "Success", f"Gap Check Complete: Found {len(results)} gaps.", QMessageBox.Information)
        
    def export_gap_report(self):
        if not self.gap_results:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Gap Report CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            df = pl.DataFrame(self.gap_results)
            df = df.rename({
                "prefix": "Prefix",
                "gap_start": "Gap Start",
                "gap_end": "Gap End",
                "missing_count": "Missing Count"
            })
            df.write_csv(path)
            show_dark_message(self, "Success", "Gap Report exported successfully.", QMessageBox.Information)
        except Exception as e:
            show_dark_message(self, "Error", f"Export failed:\n{str(e)}", QMessageBox.Critical)
            
    def on_error(self, error_msg):
        if hasattr(self, 'progress') and self.progress:
            self.progress.accept()
        show_dark_message(self, "Error", error_msg, QMessageBox.Critical)


class ManualDelimiterDialog(QDialog):
    def __init__(self, file_path, encoding, first_line, parent=None):
        super().__init__(parent)
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem, QFormLayout
        import collections
        import csv
        import io

        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Configure Delimiters")
        self.resize(750, 450)
        apply_dark_titlebar(self)

        self.file_path = file_path
        self.encoding = encoding
        
        # Read the first two lines from the file
        self.sample_lines = []
        try:
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                first = f.readline()
                if first:
                    self.sample_lines.append(first)
                second = f.readline()
                if second:
                    self.sample_lines.append(second)
        except Exception:
            pass
            
        if not self.sample_lines and first_line:
            self.sample_lines.append(first_line)

        layout = QVBoxLayout(self)

        # File path label
        path_lbl = QLabel(f"File: {os.path.basename(file_path)}")
        path_lbl.setStyleSheet("font-weight: bold; color: #38BDF8;")
        layout.addWidget(path_lbl)

        # Raw sample text label and preview
        layout.addWidget(QLabel("Raw First Line (Sample):"))
        self.raw_text = QTextEdit()
        self.raw_text.setReadOnly(True)
        raw_display = self.sample_lines[0] if self.sample_lines else first_line
        self.raw_text.setPlainText(raw_display.strip())
        self.raw_text.setFont(QFont("Consolas", 10))
        self.raw_text.setMaximumHeight(80)
        layout.addWidget(self.raw_text)

        # Dropdowns layout
        form_layout = QHBoxLayout()
        
        # Find and rank symbols in first row (all candidate delimiters/qualifiers)
        counter = collections.Counter()
        source_line = self.sample_lines[0] if self.sample_lines else first_line
        for char in source_line:
            if not (char.isascii() and char.isalnum()) and char not in (' ', '\n', '\r'):
                counter[char] += 1
        ranked_chars = [char for char, count in counter.most_common()]
        
        # Delimiter Combobox
        self.cb_sep = QComboBox()
        # Add ranked characters first
        for char in ranked_chars:
            char_repr = repr(char).replace("'", "")
            self.cb_sep.addItem(f"Detected: '{char_repr}' (Count: {counter[char]})", char)
            
        if ranked_chars:
            self.cb_sep.insertSeparator(self.cb_sep.count())
            
        sep_presets = [
            ("DC4 (chr20) - Relativity Default", chr(20)),
            ("Comma (,)", ","),
            ("Pipe (|)", "|"),
            ("Tab (\\t)", "\t"),
            ("Semi-colon (;)", ";")
        ]
        for name, val in sep_presets:
            self.cb_sep.addItem(name, val)

        # Text Qualifier Combobox
        self.cb_quote = QComboBox()
        # Add ranked characters first
        for char in ranked_chars:
            char_repr = repr(char).replace("'", "")
            self.cb_quote.addItem(f"Detected: '{char_repr}' (Count: {counter[char]})", char)
            
        if ranked_chars:
            self.cb_quote.insertSeparator(self.cb_quote.count())
            
        quote_presets = [
            ("Thorn (chr254) - Relativity Default", chr(254)),
            ("Double Quote (\")", '"'),
            ("Single Quote (')", "'"),
            ("None", "")
        ]
        for name, val in quote_presets:
            self.cb_quote.addItem(name, val)

        # Build form
        sep_widget = QWidget()
        sep_lay = QFormLayout(sep_widget)
        sep_lay.setContentsMargins(0, 0, 0, 0)
        sep_lay.addRow("Delimiter / Separator:", self.cb_sep)
        
        quote_widget = QWidget()
        quote_lay = QFormLayout(quote_widget)
        quote_lay.setContentsMargins(0, 0, 0, 0)
        quote_lay.addRow("Text Qualifier:", self.cb_quote)

        form_layout.addWidget(sep_widget)
        form_layout.addWidget(quote_widget)
        layout.addLayout(form_layout)

        # Preview layout
        layout.addWidget(QLabel("Live Parsing Preview (Columns):"))
        self.preview_table = QTableWidget()
        self.preview_table.setStyleSheet("background-color: #0F172A; gridline-color: #334155; color: #FFFFFF;")
        self.preview_table.verticalHeader().hide()
        self.preview_table.horizontalHeader().hide()
        layout.addWidget(self.preview_table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_apply = QPushButton("Apply Settings")
        self.btn_apply.setStyleSheet("background-color: #10B981; color: white;")
        self.btn_apply.clicked.connect(self.accept)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_apply)
        layout.addLayout(btn_layout)

        # Connect signals for real-time preview
        self.cb_sep.currentIndexChanged.connect(self.update_preview)
        self.cb_quote.currentIndexChanged.connect(self.update_preview)

        # Run initial preview update
        self.update_preview()

    def update_preview(self):
        from PyQt5.QtWidgets import QTableWidgetItem
        import csv
        import io
        
        sep = self.cb_sep.currentData()
        quote = self.cb_quote.currentData()
        
        # Parse lines
        all_rows = []
        for line in self.sample_lines:
            try:
                if not sep:
                    fields = [line.strip()]
                else:
                    reader_kwargs = {'delimiter': sep}
                    if quote:
                        reader_kwargs['quotechar'] = quote
                    else:
                        reader_kwargs['quoting'] = csv.QUOTE_NONE
                    
                    reader = csv.reader(io.StringIO(line), **reader_kwargs)
                    fields = next(reader)
            except Exception:
                if sep:
                    fields = line.split(sep)
                else:
                    fields = [line]
            all_rows.append(fields)
            
        max_cols = max(len(row) for row in all_rows) if all_rows else 0
                
        # Update table
        self.preview_table.clear()
        self.preview_table.setColumnCount(max_cols)
        self.preview_table.setRowCount(len(all_rows))
        
        for row_idx, row_fields in enumerate(all_rows):
            for col_idx, val in enumerate(row_fields):
                item = QTableWidgetItem(val.strip())
                self.preview_table.setItem(row_idx, col_idx, item)
            
        self.preview_table.resizeColumnsToContents()

    def get_data(self):
        return self.cb_sep.currentData(), self.cb_quote.currentData()


class RelativityApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Page One Relativity Load File Tools")
        self.resize(1200, 850)
        
        apply_dark_titlebar(self)
        
        self.selected_file_path = None
        self.backup_created = False
        self.cross_ref_path = None
        self.rename_map = {}
        self.analysis_results = []
        self.gap_results = []
        self.gap_all_columns = []
        
        self.settings = QSettings("PageOneLegal", "PageOneRelativityLoadFileTools")
        self.preview_start_line = 1
        self.preview_headers = []
        self.preview_hits = []
        self.preview_current_hit_index = -1

        # Image Engine & Studio state
        self.opt_store = OptDocumentStore()
        self.image_doc_id_field = ""
        self.doc_id_metadata_map = {}  # {DocID: {Field: Value}}
        self.image_current_doc_idx = 0

        self.setAcceptDrops(True)
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- Header Ribbon ---
        header_layout = QHBoxLayout()
        
        # Logo with white background
        logo_container = QFrame()
        logo_container.setStyleSheet("background-color: white; border-radius: 5px;")
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(5, 5, 5, 5)
        self.logo_label = QLabel()
        logo_path = get_asset_path("assets", "pageone-logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path).scaledToHeight(32, Qt.SmoothTransformation)
            self.logo_label.setPixmap(pixmap)
        logo_layout.addWidget(self.logo_label)
        header_layout.addWidget(logo_container)

        title_label = QLabel("Page One Relativity Load File Tools")
        font = title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()

        self.cb_encoding = QComboBox()
        self.cb_encoding.addItems(["Auto", "utf-8", "cp1252", "ascii", "utf-16"])
        self.cb_sep = QComboBox()
        self.cb_sep.addItems(["Auto", "DC4 (chr20)", "Comma (,)", "Pipe (|)", "Tab (\\t)"])
        self.cb_quote = QComboBox()
        self.cb_quote.addItems(["Auto", "Thorn (chr254)", "Double Quote (\")", "None"])
        
        header_layout.addStretch()
        
        # Encoding dynamic button
        self.btn_encoding = QPushButton("Encoding: Auto")
        self.enc_menu = QMenu(self)
        for enc in ["Auto", "utf-8", "cp1252", "ascii", "utf-16"]:
            self.enc_menu.addAction(enc).triggered.connect(lambda checked=False, val=enc: self.on_encoding_selected(val))
        self.btn_encoding.setMenu(self.enc_menu)
        
        # Delimiters dynamic button
        self.btn_delimiters = QPushButton("Delimiters: Auto")
        self.del_menu = QMenu(self)
        
        self.sep_submenu = self.del_menu.addMenu("Separator")
        for s in ["Auto", "DC4 (chr20)", "Comma (,)", "Pipe (|)", "Tab (\\t)"]:
            self.sep_submenu.addAction(s).triggered.connect(lambda checked=False, val=s: self.on_sep_selected(val))
            
        self.quote_submenu = self.del_menu.addMenu("Quote Character")
        for q in ["Auto", "Thorn (chr254)", "Double Quote (\")", "None"]:
            self.quote_submenu.addAction(q).triggered.connect(lambda checked=False, val=q: self.on_quote_selected(val))
            
        self.btn_delimiters.setMenu(self.del_menu)

        self.btn_open = QPushButton("Open File")
        
        # Schema Tools Button (renamed load_map for compatibility)
        self.btn_load_map = QPushButton("Tools")
        self.btn_load_map.setObjectName("BtnTools")
        self.schema_tools_menu = QMenu(self)
        self.map_menu = QMenu("Replace Field Names", self)
        self.schema_tools_menu.addMenu(self.map_menu)
        self.btn_load_map.setMenu(self.schema_tools_menu)
        self.update_recent_mappings_menu()
        self.btn_export_analysis = QPushButton("Export Analysis")
        self.btn_export_remapped = QPushButton("Export Load File")
        self.btn_export_remapped.clicked.connect(self.show_export_dialog)
        
        self.btn_help = QPushButton("?")
        self.btn_export_remapped.setObjectName("BtnExportRemapped")
        self.btn_open.setObjectName("BtnOpen")
        self.btn_help.setObjectName("BtnHelp")
        self.btn_help.setFixedWidth(40)

        self.btn_load_map.setEnabled(False)
        self.btn_export_analysis.setEnabled(False)
        self.btn_export_remapped.setEnabled(False)

        for btn in [self.btn_open, self.btn_encoding, self.btn_delimiters, self.btn_export_remapped, self.btn_help]:
            header_layout.addWidget(btn)

        main_layout.addLayout(header_layout)
        # --- Config Bar (Cards) ---
        config_layout = QHBoxLayout()
        
        self.card_filename = StatusCard("File Name", "None", "#8B5CF6")
        self.card_encoding = StatusCard("Encoding", "Not Detected", "#F59E0B")
        self.card_rows = StatusCard("Row Count", "0", "#0EA5E9")
        self.card_cols = StatusCard("Column Count", "0", "#10B981")
        self.card_delim = StatusCard("Delimiter", "Not Detected", "#EC4899")
        
        config_layout.addWidget(self.card_filename)
        config_layout.addWidget(self.card_encoding)
        config_layout.addWidget(self.card_rows)
        config_layout.addWidget(self.card_cols)
        config_layout.addWidget(self.card_delim)
        config_layout.addStretch()
        main_layout.addLayout(config_layout)

        # --- Tabs ---
        self.tabs = QTabWidget()
        
        # Data Preview Tab
        preview_tab = QWidget()
        preview_layout = QVBoxLayout(preview_tab)
        preview_layout.setContentsMargins(5, 5, 5, 5)

        
        # Controls
        preview_ctrl = QHBoxLayout()
        preview_ctrl.setContentsMargins(0, 0, 0, 5)
        preview_ctrl.setSpacing(10)
        
        self.preview_line_spin = QSpinBox()
        self.preview_line_spin.setRange(1, 999999999)
        self.btn_preview_go = QPushButton("Go")
        self.btn_preview_prev = QPushButton("< Prev 100")
        self.btn_preview_next = QPushButton("Next 100 >")
        
        preview_ctrl.addWidget(QLabel("Line:"))
        preview_ctrl.addWidget(self.preview_line_spin)
        preview_ctrl.addWidget(self.btn_preview_go)
        preview_ctrl.addWidget(self.btn_preview_prev)
        preview_ctrl.addWidget(self.btn_preview_next)
        
        preview_ctrl.addSpacing(20)
        
        # Quick Search
        self.txt_quick_search = QLineEdit()
        self.txt_quick_search.setPlaceholderText("Quick Search")
        self.txt_quick_search.setFixedWidth(180)
        self.btn_quick_search = QPushButton("Search")
        self.btn_advanced_search = QPushButton("Advanced Search")
        
        self.lbl_preview_hits = QLabel("0 hits")
        
        preview_ctrl.addWidget(self.txt_quick_search)
        preview_ctrl.addWidget(self.btn_quick_search)
        preview_ctrl.addWidget(self.btn_advanced_search)
        preview_ctrl.addWidget(self.lbl_preview_hits)
        
        self.card_search = InlineSearchCard()
        self.btn_clear_search = QPushButton("Clear Search")
        self.btn_clear_search.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.btn_clear_search.setFixedHeight(32)
        self.btn_clear_search.clicked.connect(self.clear_all_searches)
        
        # Transform Dropdown
        self.btn_transform = QPushButton("Tools")
        self.btn_transform.setObjectName("BtnTools")
        self.transform_menu = QMenu(self)
        self.act_replace = self.transform_menu.addAction("Replace...")
        self.act_format_dates = self.transform_menu.addAction("Format Dates...")
        self.act_append_field = self.transform_menu.addAction("Append Field...")
        self.act_merge_fields = self.transform_menu.addAction("Merge Fields...")
        self.act_bulk_replace = self.transform_menu.addAction("Mass Field Redaction...")
        self.transform_menu.addSeparator()
        self.act_gap_report = self.transform_menu.addAction("Gap Report...")
        self.btn_transform.setMenu(self.transform_menu)
        
        self.btn_preview_expand = QPushButton("Expand Columns")
        self.btn_preview_expand.clicked.connect(self.expand_preview_columns)
        
        preview_ctrl.addWidget(self.btn_transform)
        preview_ctrl.addWidget(self.btn_preview_expand)
        preview_ctrl.addStretch()
        
        preview_layout.addLayout(preview_ctrl)
        
        # Applied Search Bar container widget (hidden by default)
        self.search_status_container = QWidget()
        status_layout = QHBoxLayout(self.search_status_container)
        status_layout.setContentsMargins(0, 4, 0, 4)
        status_layout.setSpacing(10)
        status_layout.addWidget(self.btn_clear_search)
        status_layout.addWidget(self.card_search)
        self.search_status_container.setVisible(False)
        
        preview_layout.addWidget(self.search_status_container)
        
        # Splitter
        self.preview_splitter = QSplitter(Qt.Horizontal)
        
        # Left Table
        self.preview_table = CopyableTableView()
        self.preview_model = PreviewTableModel()
        self.preview_table.setModel(self.preview_model)
        self.preview_table.setSelectionBehavior(QTableView.SelectRows)
        self.preview_table.setSelectionMode(QTableView.SingleSelection)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        self.preview_splitter.addWidget(self.preview_table)
        
        # Right Record View using UnifiedDocumentViewer
        self.preview_doc_viewer = UnifiedDocumentViewer()
        self.preview_splitter.addWidget(self.preview_doc_viewer)
        self.preview_splitter.setSizes([900, 300])
        
        preview_layout.addWidget(self.preview_splitter, 1)

        # --- Image Preview Tab ---
        image_preview_tab = QWidget()
        img_preview_layout = QVBoxLayout(image_preview_tab)
        img_preview_layout.setContentsMargins(10, 10, 10, 10)
        img_preview_layout.setSpacing(8)

        # Header Panel
        img_header_box = QFrame()
        img_header_box.setObjectName("Card")
        img_header_box.setStyleSheet(GLOBAL_STYLE)
        img_header_layout = QHBoxLayout(img_header_box)
        img_header_layout.setContentsMargins(10, 8, 10, 8)

        lbl_doc_id = QLabel("DocID Field:")
        lbl_doc_id.setStyleSheet("font-weight: bold; color: #94A3B8;")
        self.cb_image_doc_id = QComboBox()
        self.cb_image_doc_id.setMinimumWidth(180)

        self.lbl_image_status_badge = QLabel("No Image File Loaded")
        self.lbl_image_status_badge.setStyleSheet("color: #FBBF24; font-weight: bold; padding: 4px 8px; background-color: #334155; border-radius: 4px;")

        img_header_layout.addWidget(lbl_doc_id)
        img_header_layout.addWidget(self.cb_image_doc_id)
        img_header_layout.addSpacing(15)
        img_header_layout.addWidget(self.lbl_image_status_badge)
        img_header_layout.addStretch()

        img_preview_layout.addWidget(img_header_box)

        # Body Splitter (Left: Table, Right: Viewer)
        self.image_splitter = QSplitter(Qt.Horizontal)
        self.image_table = QTableView()
        self.image_table.setStyleSheet("background-color: #1E293B; gridline-color: #334155; color: #FFFFFF;")
        self.image_table_model = ImagePageTableModel()
        self.image_table.setModel(self.image_table_model)
        self.image_table.setSelectionBehavior(QTableView.SelectRows)
        self.image_table.setSelectionMode(QTableView.SingleSelection)
        self.image_table.horizontalHeader().setStretchLastSection(True)

        self.studio_doc_viewer = UnifiedDocumentViewer()

        self.image_splitter.addWidget(self.image_table)
        self.image_splitter.addWidget(self.studio_doc_viewer)
        self.image_splitter.setSizes([900, 300])

        img_preview_layout.addWidget(self.image_splitter, 1)

        # Schema Tab

        schema_tab = QWidget()
        schema_layout = QVBoxLayout(schema_tab)
        
        # Filter Row
        self.filter_container = QWidget()
        self.filter_layout = QHBoxLayout(self.filter_container)
        self.filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_layout.setSpacing(0)
        
        # Top Schema controls (Select All Fields toggle, Up/Down buttons)
        schema_ctrls = QHBoxLayout()
        self.chk_toggle_all_fields = QCheckBox("Select All Fields")
        self.chk_toggle_all_fields.setChecked(True)
        
        self.btn_field_up = QPushButton("Field Up")
        self.btn_field_down = QPushButton("Field Down")
        self.btn_field_up.setFixedWidth(100)
        self.btn_field_down.setFixedWidth(100)
        
        schema_ctrls.addWidget(self.chk_toggle_all_fields)
        schema_ctrls.addSpacing(20)
        schema_ctrls.addWidget(self.btn_field_up)
        schema_ctrls.addWidget(self.btn_field_down)
        schema_ctrls.addWidget(self.btn_load_map)
        schema_ctrls.addWidget(self.btn_export_analysis)
        schema_ctrls.addStretch()
        schema_layout.addLayout(schema_ctrls)

        self.cb_checked_filter = QComboBox()
        self.cb_checked_filter.addItems(["Show All Fields", "Show Checked Only", "Show Unchecked Only"])
        
        self.filter_src = QLineEdit(); self.filter_src.setPlaceholderText("Filter Source...")
        self.filter_tgt = QLineEdit(); self.filter_tgt.setPlaceholderText("Filter Target...")
        self.filter_typ = QLineEdit(); self.filter_typ.setPlaceholderText("Filter Type...")
        
        self.filter_max_container = QWidget()
        max_layout = QHBoxLayout(self.filter_max_container)
        max_layout.setContentsMargins(0, 0, 0, 0)
        max_layout.setSpacing(2)
        self.filter_max_op = QComboBox()
        self.filter_max_op.addItems(["=", ">", "<", ">=", "<="])
        self.filter_max = QLineEdit(); self.filter_max.setPlaceholderText("Filter Max Lenght...")
        max_layout.addWidget(self.filter_max_op)
        max_layout.addWidget(self.filter_max)
        
        self.filter_smp = QWidget() # Empty placeholder for sample column
        
        self.filter_layout.addWidget(self.cb_checked_filter)
        self.filter_layout.addWidget(self.filter_src)
        self.filter_layout.addWidget(self.filter_tgt)
        self.filter_layout.addWidget(self.filter_typ)
        self.filter_layout.addWidget(self.filter_max_container)
        self.filter_layout.addWidget(self.filter_smp)
        self.filter_layout.addStretch()
        
        self.filter_tgt.hide()
        
        for w in [self.filter_src, self.filter_tgt, self.filter_typ, self.filter_max]:
            w.textChanged.connect(self.on_filter_changed)
        self.filter_max_op.currentTextChanged.connect(self.on_filter_changed)
        self.cb_checked_filter.currentTextChanged.connect(self.on_filter_changed)
        
        
        schema_layout.addWidget(self.filter_container)

        # Schema Table
        self.schema_table = QTableView()
        self.schema_table.setAlternatingRowColors(True)
        self.schema_table.setSelectionBehavior(QTableView.SelectRows)
        self.schema_table.setSelectionMode(QTableView.SingleSelection)
        self.schema_table.verticalHeader().hide()
        self.schema_model = SchemaTableModel()
        self.schema_proxy = SchemaFilterProxyModel()
        self.schema_proxy.setSourceModel(self.schema_model)
        self.schema_table.setModel(self.schema_proxy)
        
        self.header = self.schema_table.horizontalHeader()
        self.header.setSectionResizeMode(QHeaderView.Interactive)
        self.header.setStretchLastSection(False)
        self.header.sectionResized.connect(self.sync_filter_widths)
        
        schema_layout.addWidget(self.schema_table)
        self.tabs.addTab(schema_tab, "Schema Analysis")
        self.tabs.addTab(preview_tab, "Data Preview")
        self.tabs.addTab(image_preview_tab, "Image Preview")

        main_layout.addWidget(self.tabs)

        # Initial dynamic button text
        self.btn_open.setText("Open Data Load File")

        # Connect Signals
        self.btn_open.clicked.connect(self.on_open_clicked)
        self.btn_export_analysis.clicked.connect(self.export_analysis)

        self.btn_help.clicked.connect(self.show_help)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Schema signals
        self.chk_toggle_all_fields.stateChanged.connect(self.toggle_all_fields)
        self.schema_table.clicked.connect(self.on_schema_table_clicked)
        self.btn_field_up.clicked.connect(self.move_selected_field_up)
        self.btn_field_down.clicked.connect(self.move_selected_field_down)
        
        # Preview Signals
        self.btn_preview_go.clicked.connect(self.preview_go)
        self.btn_preview_prev.clicked.connect(self.preview_prev)
        self.btn_preview_next.clicked.connect(self.preview_next)
        self.btn_quick_search.clicked.connect(self.run_quick_search)
        self.txt_quick_search.returnPressed.connect(self.run_quick_search)
        self.btn_advanced_search.clicked.connect(self.preview_search_open)
        self.btn_clear_search.clicked.connect(self.clear_all_searches)

        # Image Studio Signals
        self.cb_image_doc_id.currentTextChanged.connect(self.on_doc_id_field_changed)
        self.image_table.selectionModel().selectionChanged.connect(self.on_image_table_row_selected)
        self.preview_doc_viewer.request_nav_action.connect(self.handle_preview_nav)
        self.studio_doc_viewer.request_nav_action.connect(self.handle_studio_nav)
        self.preview_doc_viewer.page_changed.connect(self.on_preview_page_changed)
        self.studio_doc_viewer.page_changed.connect(self.on_studio_page_changed)
        self.act_replace.triggered.connect(self.show_replace_dialog)
        self.act_format_dates.triggered.connect(self.show_format_date_dialog)
        self.act_append_field.triggered.connect(self.show_append_field_dialog)
        self.act_merge_fields.triggered.connect(self.show_merge_fields_dialog)
        self.act_bulk_replace.triggered.connect(self.show_mass_redaction_dialog)
        self.act_gap_report.triggered.connect(self.show_gap_report_dialog)
        self.preview_line_spin.editingFinished.connect(self.preview_go)
        self.preview_table.selectionModel().selectionChanged.connect(self.preview_row_selected)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sync_filter_widths()

    def showEvent(self, event):
        super().showEvent(event)
        self.schema_table.setColumnWidth(0, 60)
        has_target = "Target Name" in self.schema_model.headers
        if has_target:
            self.schema_table.setColumnWidth(1, 150)
            self.schema_table.setColumnWidth(2, 200)
            self.schema_table.setColumnWidth(3, 150)
            self.schema_table.setColumnWidth(4, 100)
            # Column 5 (Sample) is stretched
            # Column 6 (Order) is 60px
        else:
            self.schema_table.setColumnWidth(1, 200)
            self.schema_table.setColumnWidth(2, 150)
            self.schema_table.setColumnWidth(3, 100)
            # Column 4 (Sample) is stretched
            # Column 5 (Order) is 60px
            
        self.header.setStretchLastSection(False)
        try:
            sample_idx = self.schema_model.headers.index("Sample")
            self.header.setSectionResizeMode(sample_idx, QHeaderView.Stretch)
        except ValueError:
            pass
            
        try:
            order_idx = self.schema_model.headers.index("Order")
            self.header.setSectionResizeMode(order_idx, QHeaderView.Fixed)
            self.schema_table.setColumnWidth(order_idx, 60)
        except ValueError:
            pass
        
        # Default Record table widths
        self.record_table.setColumnWidth(0, 150)
        
        self.sync_filter_widths()

    def sync_filter_widths(self, *args):
        self.filter_exp.setFixedWidth(self.header.sectionSize(0))
        has_target = "Target Name" in self.schema_model.headers
        
        if has_target:
            self.filter_tgt.show()
            self.filter_tgt.setFixedWidth(self.header.sectionSize(1))
            self.filter_src.setFixedWidth(self.header.sectionSize(2))
            self.filter_typ.setFixedWidth(self.header.sectionSize(3))
            self.filter_max_container.setFixedWidth(self.header.sectionSize(4))
            self.filter_smp.setFixedWidth(self.header.sectionSize(5))
        else:
            self.filter_tgt.hide()
            self.filter_src.setFixedWidth(self.header.sectionSize(1))
            self.filter_typ.setFixedWidth(self.header.sectionSize(2))
            self.filter_max_container.setFixedWidth(self.header.sectionSize(3))
            self.filter_smp.setFixedWidth(self.header.sectionSize(4))

    def pad_table_columns(self, table, padding=30):
        header = table.horizontalHeader()
        for i in range(header.count()):
            table.setColumnWidth(i, table.columnWidth(i) + padding)

    def on_filter_changed(self):
        checked_opt_map = {
            "Show All Fields": "All",
            "Show Checked Only": "Checked",
            "Show Unchecked Only": "Unchecked"
        }
        checked_filter = checked_opt_map.get(self.cb_checked_filter.currentText(), "All")
        self.schema_proxy.set_filters(
            self.filter_src.text(),
            self.filter_tgt.text(),
            self.filter_typ.text(),
            self.filter_max.text(),
            self.filter_max_op.currentText(),
            checked_filter
        )

    def show_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Page One Relativity Load File Tools - Help")
        dlg.resize(600, 560)
        layout = QVBoxLayout(dlg)
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; color: #E2E8F0; line-height: 1.6; padding: 10px;">
            <h2 style="color: #60A5FA; font-size: 18px; margin-top: 0; margin-bottom: 5px; font-weight: 600;">
                Page One Relativity Load File Tools v1.3.0
            </h2>
            <p style="margin-top: 0; margin-bottom: 20px; color: #94A3B8; font-size: 12px;">
                Support: <a href="mailto:support@pageonelegal.com" style="color: #60A5FA; text-decoration: none;">support@pageonelegal.com</a>
            </p>

            <h3 style="color: #60A5FA; font-size: 14px; border-bottom: 1px solid #334155; padding-bottom: 6px; margin-top: 25px; margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                Workflow Overview
            </h3>
            <ol style="margin-left: 20px; padding-left: 0; margin-bottom: 20px;">
                <li style="margin-bottom: 12px;">
                    <b style="color: #93C5FD;">Dynamic Settings:</b> Click the <b>Encoding</b> or <b>Delimiters</b> dropdowns at the top of the window to override file parsing rules. The file will be re-analyzed instantly upon changing.
                </li>
                <li style="margin-bottom: 12px;">
                    <b style="color: #93C5FD;">Load File:</b> Click <b>Open File</b> or drag-and-drop a DAT or CSV file to load it.
                </li>
                <li style="margin-bottom: 12px;">
                    <b style="color: #93C5FD;">Data Preview:</b> View loaded records in grids of 100. Type queries directly into the <b>Quick Search</b> bar and press Enter, or click <b>Advanced Search</b> for targeted field-level queries.
                </li>
                <li style="margin-bottom: 12px;">
                    <b style="color: #93C5FD;">Data Transformations:</b> Access advanced options under the <b>Transform Data ▾</b> dropdown:
                    <ul style="margin-left: 18px; padding-left: 0; margin-top: 6px;">
                        <li style="margin-bottom: 6px;"><i>Replace:</i> Perform text, wildcard (* or ?), or Regular Expression substitutions. Wildcard and regex matches overwrite the entire cell value.</li>
                        <li style="margin-bottom: 6px;"><i>Format Dates:</i> Standardize date formats or combine separate Date & Time columns.</li>
                        <li style="margin-bottom: 6px;"><i>Append Field:</i> Insert a new column populated with static values, row indexes, or clones of another field.</li>
                        <li style="margin-bottom: 6px;"><i>Merge Fields:</i> Combine any two columns together with a custom separator.</li>
                        <li style="margin-bottom: 6px;"><i>Mass Field Redaction:</i> Upload a CSV containing document identifiers, map match fields, and select multiple target fields to redact in bulk with a custom string (e.g. privilege redaction). Features persistent run histories and import/export lists.</li>
                    </ul>
                    <div style="color: #94A3B8; font-size: 11px; margin-top: 8px;">
                        * Note: Modifications are processed in-place and track failures in system-only "Error" and "Modification" columns. You will be prompted to create a .bak backup on the first modification. If errors occur, you will be prompted to filter the table to review errored records.
                    </div>
                </li>
                <li style="margin-bottom: 12px;">
                    <b style="color: #93C5FD;">Schema Selection & Sorting:</b> Toggle the <b>Select All Fields</b> checkbox or filter list views using the selection filter dropdown (All, Checked, Unchecked). Select a field row and click <b>Field Up</b> or <b>Field Down</b> to customize the column export order.
                </li>
                <li style="margin-bottom: 12px;">
                    <b style="color: #93C5FD;">Exporting:</b> Click <b>Export Load File</b> to choose your format (.dat, .csv, .xlsx). The dialog provides options to export only selected/sorted columns, apply target name mappings, or limit records to search hits.
                </li>
            </ol>

            <h3 style="color: #60A5FA; font-size: 14px; border-bottom: 1px solid #334155; padding-bottom: 6px; margin-top: 25px; margin-bottom: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                Relativity Field Types
            </h3>
            <ul style="margin-left: 20px; padding-left: 0; margin-bottom: 20px;">
                <li style="margin-bottom: 8px;"><b style="color: #93C5FD;">Whole Number / Decimal:</b> Detected from integer or floating-point patterns.</li>
                <li style="margin-bottom: 8px;"><b style="color: #93C5FD;">Date:</b> Detected via standard e-discovery header strings and timestamp matching.</li>
                <li style="margin-bottom: 8px;"><b style="color: #93C5FD;">Fixed-length Text:</b> Text columns containing data under 256 characters.</li>
                <li style="margin-bottom: 8px;"><b style="color: #93C5FD;">Long Text:</b> Text columns containing values exceeding 256 characters.</li>
                <li style="margin-bottom: 8px;"><b style="color: #93C5FD;">Empty/Blank:</b> Columns with zero maximum length.</li>
            </ul>
        </div>
        """)
        layout.addWidget(text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignCenter)
        
        dlg.exec()

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Load File", "", "Load Files (*.dat *.csv *.txt);;All Files (*.*)")
        if not path:
            return
            
        self.selected_file_path = path
        self.backup_created = False
        self.start_analysis()
        
    def start_analysis(self):
        if not self.selected_file_path:
            return
            
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        # Ingest, Infer & Validate format
        try:
            det_enc, det_sep, det_quote, first_line, validation_passed = processor.infer_and_validate_format(self.selected_file_path)
            
            final_enc = enc or det_enc
            final_sep = sep or det_sep
            final_qt = qt or det_quote
            
            # Re-validate with the final settings
            if final_sep and final_sep not in first_line:
                validation_passed = False
                
            if not validation_passed:
                dialog = ManualDelimiterDialog(self.selected_file_path, final_enc, first_line, self)
                if dialog.exec() == QDialog.Accepted:
                    final_sep, final_qt = dialog.get_data()
                    
                    # Sync selection back to comboboxes
                    sep_mapping = {
                        chr(20): "DC4 (chr20)",
                        ",": "Comma (,)",
                        "|": "Pipe (|)",
                        "\t": "Tab (\\t)",
                        ";": "Semi-colon (;)"
                    }
                    quote_mapping = {
                        chr(254): "Thorn (chr254)",
                        '"': 'Double Quote (")',
                        "'": "Single Quote (')",
                        "": "None"
                    }
                    
                    sep_text = sep_mapping.get(final_sep, f"Custom ('{final_sep}')")
                    if self.cb_sep.findText(sep_text) == -1:
                        self.cb_sep.addItem(sep_text, final_sep)
                    self.cb_sep.setCurrentText(sep_text)
                    
                    quote_text = quote_mapping.get(final_qt, f"Custom ('{final_qt}')" if final_qt else "None")
                    if self.cb_quote.findText(quote_text) == -1:
                        self.cb_quote.addItem(quote_text, final_qt)
                    self.cb_quote.setCurrentText(quote_text)
                    
                    self.update_delimiters_button_text()
                else:
                    self.selected_file_path = None
                    return
                    
            enc = final_enc
            sep = final_sep
            qt = final_qt
            if qt == "":
                qt = "\x00"
            
        except Exception as e:
            show_dark_message(self, "Load Error", f"Failed to validate load file format:\n{str(e)}", QMessageBox.Critical)
            self.selected_file_path = None
            return
            
        self.progress = QProgressDialog("Analyzing load file...", None, 0, 0, self)
        self.progress.setStyleSheet(GLOBAL_STYLE)
        from PyQt5.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        self.worker = AnalysisWorker(self.selected_file_path, enc, sep, qt)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
            
        file_path = urls[0].toLocalFile()
        if not file_path:
            return
            
        ext = os.path.splitext(file_path)[1].lower()
        current_tab = self.tabs.currentIndex()

        if current_tab == 2:  # Image Preview tab
            if ext in ['.opt', '.dii', '.smi', '.lfp']:
                # Import image load file
                self.import_image_load_file_path(file_path)
            else:
                show_dark_message(self, "Invalid File", "Please drop a valid image load file (.opt, .dii, .smi, .lfp)", QMessageBox.Warning)
        else:  # Schema Analysis or Data Preview tabs
            if ext in ['.dat', '.csv', '.txt']:
                self.selected_file_path = file_path
                self.start_analysis()
            else:
                show_dark_message(self, "Invalid File", "Please drop a valid load file (.dat, .csv, .txt)", QMessageBox.Warning)

    def on_analysis_finished(self, encoding, delimiter, row_count, schema_results):
        self.progress.accept()
        self.analysis_results = schema_results
        
        filename = os.path.basename(self.selected_file_path)
        self.card_filename.set_value(filename)
        self.card_encoding.set_value(encoding)
        self.card_delim.set_value(delimiter)
        self.card_rows.set_value(row_count)
        actual_cols = [r for r in schema_results if not r.get("system_field", False) and not r.get("system_only", False)]
        self.card_cols.set_value(len(actual_cols))
        self.card_search.set_value("None")
        
        self.schema_model.update_data(self.analysis_results)
        
        # Populate Gap dropdowns
        self.gap_all_columns = sorted([r["column"] for r in self.analysis_results], key=lambda x: x.lower())
                
        self.btn_load_map.setEnabled(True)
        self.btn_export_analysis.setEnabled(True)
        self.btn_export_remapped.setEnabled(True)
        self.schema_table.resizeColumnsToContents()
        self.pad_table_columns(self.schema_table)
        self.sync_filter_widths()
        
        self.load_preview_data()
        
        show_dark_message(self, "Success", f"Analysis complete for {os.path.basename(self.selected_file_path)}.", QMessageBox.Information)

    def load_map(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Cross-Reference CSV", "", "CSV Files (*.csv)")
        if not path:
            return
            
        try:
            self.cross_ref_path = path
            self.rename_map = processor.load_mapping_csv(self.cross_ref_path)
            self.schema_model.update_map(self.rename_map)
            self.filter_tgt.show()
            self.schema_table.resizeColumnsToContents()
            self.pad_table_columns(self.schema_table)
            self.sync_filter_widths()
            
            self.btn_export_remapped.setEnabled(True)
            show_dark_message(self, "Success", f"Mapping loaded: {len(self.rename_map)} fields identified.", QMessageBox.Information)
        except Exception as e:
            show_dark_message(self, "Error", f"Failed to load cross-ref:\n{str(e)}", QMessageBox.Critical)

    def export_analysis(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Analysis CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            df = pl.DataFrame(self.analysis_results)
            df = df.rename({
                "column": "Source Field",
                "type": "Relativity Field Type",
                "max_len": "Max Length",
                "sample": "Sample Data"
            })
            df.write_csv(path)
            show_dark_message(self, "Success", "Analysis exported successfully.", QMessageBox.Information)
        except Exception as e:
            show_dark_message(self, "Error", f"Export failed:\n{str(e)}", QMessageBox.Critical)

    def export_remapped(self, mode="both", include_audit=False):
        if not self.selected_file_path:
            return
            
        keep_columns = None
        if mode in ("filtered", "both"):
            keep_columns = []
            for row in range(self.schema_proxy.rowCount()):
                idx = self.schema_proxy.index(row, 0)
                keep_columns.append(self.schema_proxy.data(idx))
                
        if not include_audit:
            system_fields = [item["column"].lower() for item in self.schema_model._data if item.get("system_field", False)]
            if keep_columns is None:
                keep_columns = [
                    item["column"] for item in self.schema_model._data 
                    if not item.get("system_field", False)
                ]
            else:
                keep_columns = [c for c in keep_columns if c.lower() not in system_fields]
                
        cross_ref_path = self.cross_ref_path if mode in ("renamed", "both") else None

        filter_str = "DAT Files (*.dat);;CSV Files (*.csv);;Excel Files (*.xlsx)"
            
        path, _ = QFileDialog.getSaveFileName(self, "Export Final Load File", "", filter_str)
        if not path:
            return
            
        self.progress = QProgressDialog("Exporting load file...", None, 0, 0, self)
        self.progress.setStyleSheet(GLOBAL_STYLE)
        from PyQt5.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        self.worker = RemapWorker(self.selected_file_path, cross_ref_path, path, keep_columns, enc, sep, qt)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_export_finished(self, count):
        self.progress.accept()
        show_dark_message(self, "Success", "Export completed successfully!", QMessageBox.Information)



    def on_error(self, error_msg):
        if hasattr(self, 'progress') and self.progress:
            self.progress.accept()
        show_dark_message(self, "Error", error_msg, QMessageBox.Critical)


    def get_override_val(self, cb):
        data = cb.currentData()
        if data is not None:
            if data == "":
                return "\x00"
            return data
            
        val = cb.currentText()
        if val == "Auto": return None
        if "chr20" in val: return chr(20)
        if "chr254" in val: return chr(254)
        if "Comma" in val: return ","
        if "Pipe" in val: return "|"
        if "Tab" in val: return "\t"
        if "Double Quote" in val: return '"'
        if "None" in val: return "\x00"
        return val

    def update_recent_mappings_menu(self):
        self.map_menu.clear()
        recent = self.settings.value("recent_mappings", [])
        if not recent:
            act = self.map_menu.addAction("No recent mappings")
            act.setEnabled(False)
        else:
            for path in recent:
                if os.path.exists(path):
                    act = self.map_menu.addAction(os.path.basename(path))
                    act.setData(path)
                    act.triggered.connect(lambda checked=False, p=path: self.load_recent_map(p))
                    
        self.map_menu.addSeparator()
        act_new = self.map_menu.addAction("Load New Mapping...")
        act_new.triggered.connect(self.load_map)

    def add_recent_mapping(self, path):
        recent = self.settings.value("recent_mappings", [])
        if path in recent:
            recent.remove(path)
        recent.insert(0, path)
        recent = recent[:5]
        self.settings.setValue("recent_mappings", recent)
        self.update_recent_mappings_menu()

    def load_recent_map(self, path):
        try:
            self.cross_ref_path = path
            self.rename_map = processor.load_mapping_csv(self.cross_ref_path)
            self.schema_model.update_map(self.rename_map)
            self.filter_tgt.show()
            self.schema_table.resizeColumnsToContents()
            self.pad_table_columns(self.schema_table)
            self.sync_filter_widths()
            self.btn_export_remapped.setEnabled(True)
            self.add_recent_mapping(path)
            show_dark_message(self, "Success", f"Mapping loaded: {len(self.rename_map)} fields identified.", QMessageBox.Information)
        except Exception as e:
            show_dark_message(self, "Error", f"Failed to load cross-ref:\n{str(e)}", QMessageBox.Critical)

    def reload_file_schema(self):
        if not self.selected_file_path:
            return
        # 1. Update preview headers list
        self.preview_headers = [r["column"] for r in self.analysis_results]
        
        # 2. Reload preview rows in the table model
        self.load_preview_data()
        
        # 3. Rebuild record properties view
        self.preview_row_selected(None, None)

    def load_preview_data(self):
        if not self.selected_file_path: return
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        try:
            if getattr(self, 'preview_is_filtered_mode', False) and getattr(self, 'preview_hits', []):
                start_idx = self.preview_current_hit_index
                end_idx = min(start_idx + 100, len(self.preview_hits))
                target_lines = self.preview_hits[start_idx:end_idx]
                headers, records = processor.read_specific_records(self.selected_file_path, target_lines, enc, sep, qt)
                if target_lines:
                    self.preview_start_line = target_lines[0]
                    self.preview_line_spin.setValue(self.preview_start_line)
            else:
                self.preview_line_spin.setValue(self.preview_start_line)
                headers, records = processor.read_records(self.selected_file_path, self.preview_start_line, 100, enc, sep, qt)
                
            self.preview_headers = headers
            self.preview_model.update_data(headers, records, start_line=self.preview_start_line)

            # Build metadata lookup map for dynamic binding
            self.doc_id_metadata_map = {}
            for rec in records:
                row_dict = {}
                for idx, h in enumerate(headers):
                    if idx < len(rec):
                        row_dict[h] = str(rec[idx])
                
                # Determine control/doc identifier
                doc_id = ""
                if self.image_doc_id_field and self.image_doc_id_field in row_dict:
                    doc_id = row_dict[self.image_doc_id_field]
                else:
                    for cand in ("Control Number", "DocID", "BegBates", "Bates", "ID"):
                        for key in row_dict:
                            if cand.lower() in key.lower():
                                doc_id = row_dict[key]
                                break
                        if doc_id:
                            break
                if not doc_id and headers:
                    doc_id = row_dict.get(headers[0], "")
                if doc_id:
                    self.doc_id_metadata_map[doc_id] = row_dict

            if records:
                self.preview_table.selectionModel().blockSignals(True)
                try:
                    self.preview_table.selectRow(0)
                finally:
                    self.preview_table.selectionModel().blockSignals(False)
        except Exception as e:
            show_dark_message(self, "Preview Error", str(e), QMessageBox.Critical)

    def expand_preview_columns(self):
        self.preview_table.resizeColumnsToContents()

    def preview_go(self):
        if getattr(self, 'preview_is_filtered_mode', False):
            self.preview_is_filtered_mode = False
            self.lbl_preview_hits.setText("0 hits")
        self.preview_start_line = self.preview_line_spin.value()
        self.load_preview_data()

    def preview_prev(self):
        if getattr(self, 'preview_is_filtered_mode', False):
            self.preview_current_hit_index = max(0, self.preview_current_hit_index - 100)
        else:
            self.preview_start_line = max(1, self.preview_start_line - 100)
        self.load_preview_data()

    def preview_next(self):
        if getattr(self, 'preview_is_filtered_mode', False):
            if self.preview_current_hit_index + 100 < len(self.preview_hits):
                self.preview_current_hit_index += 100
        else:
            self.preview_start_line += 100
        self.load_preview_data()

    def preview_search_open(self):
        if not self.selected_file_path or not self.analysis_results:
            return
            
        columns = [r["column"] for r in self.analysis_results]
        dialog = SearchDialog(columns, self)
        if dialog.exec() == QDialog.Accepted:
            config = dialog.get_data()
            if not config.get("query"):
                self.preview_is_filtered_mode = False
                self.lbl_preview_hits.setText("0 hits")
                self.load_preview_data()
                return
                
            self.progress = QProgressDialog("Searching file...", None, 0, 0, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            from PyQt5.QtCore import Qt
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Please Wait")
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
    
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            self.search_worker = PreviewSearchWorker(self.selected_file_path, config, enc, sep, qt)
            self.search_worker.finished.connect(self.on_search_finished)
            self.search_worker.error.connect(self.on_error)
            self.search_worker.start()

    def on_search_finished(self, hits):
        self.progress.accept()
        self.preview_hits = hits
        self.preview_is_filtered_mode = bool(hits)
        self.preview_current_hit_index = 0
        self.lbl_preview_hits.setText(f"{len(hits)} hits")
        if hits:
            if hasattr(self, 'search_worker') and self.search_worker:
                self.update_applied_search_card(self.search_worker.config)
            self.load_preview_data()
        else:
            self.update_applied_search_card(None)
            show_dark_message(self, "Search", "No matches found.", QMessageBox.Information)
    def preview_row_selected(self, selected, deselected):
        indexes = self.preview_table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        if row < len(self.preview_model._data):
            row_data = self.preview_model._data[row]
            # Build metadata dict for record
            record_dict = {}
            for idx, h in enumerate(self.preview_headers):
                if idx < len(row_data):
                    record_dict[h] = str(row_data[idx])
            
            doc_id = ""
            if self.image_doc_id_field and self.image_doc_id_field in record_dict:
                doc_id = record_dict[self.image_doc_id_field]
            else:
                # Search candidate fields
                for cand in ("Control Number", "DocID", "BegBates", "Bates", "ID"):
                    for key in record_dict:
                        if cand.lower() in key.lower():
                            doc_id = record_dict[key]
                            break
                    if doc_id:
                        break
            if not doc_id and self.preview_headers:
                doc_id = record_dict.get(self.preview_headers[0], "")

            base_dir = getattr(self.preview_doc_viewer, "base_dir", "") or os.path.dirname(self.selected_file_path or "")
            self.preview_doc_viewer.set_stores(self.opt_store, {doc_id: record_dict}, base_dir=base_dir)
            self.preview_doc_viewer.record_selected(doc_id)

            # Bidirectional cross-tab synchronization: select the matching page row in the image table
            self.image_table.selectionModel().blockSignals(True)
            try:
                for idx, page_tuple in enumerate(self.image_table_model.pages):
                    p_doc_id = page_tuple[1]
                    if str(p_doc_id).strip().lower() == str(doc_id).strip().lower():
                        self.image_table.selectRow(idx)
                        break
            finally:
                self.image_table.selectionModel().blockSignals(False)

    def show_replace_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            return
            
        columns = [r["column"] for r in self.analysis_results]
        
        filtered_count = len(self.preview_hits) if getattr(self, 'preview_is_filtered_mode', False) else 0
        dialog = ReplaceDialog(columns, filtered_count, self)
        
        if dialog.exec() == QDialog.Accepted:
            field, find_pat, repl_str, use_regex, filtered_only = dialog.get_data()
            if not find_pat:
                return
                
            if not self.backup_created:
                reply = show_dark_warning_yes_no_cancel(
                    self, 
                    "Warning: Immediate Changes", 
                    "Changes to the source file are immediate.\n\nDo you want to create a backup file (.bak) before proceeding?"
                )
                
                if reply == QMessageBox.Cancel:
                    return
                    
                if reply == QMessageBox.Yes:
                    import shutil, datetime
                    try:
                        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        shutil.copy2(self.selected_file_path, f"{self.selected_file_path}_{ts}.bak")
                        self.backup_created = True
                    except Exception as e:
                        show_dark_message(self, "Error", f"Failed to create backup:\n{str(e)}", QMessageBox.Critical)
                        return
            
            self.progress = QProgressDialog("Replacing data...", None, 0, 0, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            from PyQt5.QtCore import Qt
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Please Wait")
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
            
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            target_lines = self.preview_hits if filtered_only else None
            
            self.worker = ReplaceWorker(self.selected_file_path, field, find_pat, repl_str, enc, sep, qt, use_regex, target_lines)
            self.worker.finished.connect(self.on_replace_finished)
            self.worker.error.connect(self.on_error)
            self.worker.start()
            
    def on_replace_finished(self, count, error_count=0):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()
        self.handle_transform_errors(f"Replaced {count} instances.", error_count)
        self.load_preview_data()

    def show_format_date_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            return
            
        columns = [r["column"] for r in self.analysis_results]
        filtered_count = len(self.preview_hits) if getattr(self, 'preview_is_filtered_mode', False) else 0
        
        dialog = DateFormatDialog(columns, filtered_count, self)
        if dialog.exec() == QDialog.Accepted:
            cfg = dialog.get_data()
            
            if not self.backup_created:
                reply = show_dark_warning_yes_no_cancel(
                    self, 
                    "Warning: Immediate Changes", 
                    "Changes to the source file are immediate.\n\nDo you want to create a backup file (.bak) before proceeding?"
                )
                
                if reply == QMessageBox.Cancel:
                    return
                    
                if reply == QMessageBox.Yes:
                    import shutil, datetime
                    try:
                        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        shutil.copy2(self.selected_file_path, f"{self.selected_file_path}_{ts}.bak")
                        self.backup_created = True
                    except Exception as e:
                        show_dark_message(self, "Error", f"Failed to create backup:\n{str(e)}", QMessageBox.Critical)
                        return
            
            self.progress = QProgressDialog("Processing dates...", None, 0, 0, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            from PyQt5.QtCore import Qt
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Please Wait")
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
            
            from pyside_workers import FormatDateWorker
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            target_lines = self.preview_hits if cfg.get("filtered_only", False) else None
            
            self.worker = FormatDateWorker(self.selected_file_path, cfg, enc, sep, qt, target_lines)
            self.worker.finished.connect(self.on_format_finished)
            self.worker.error.connect(self.on_error)
            self.worker.start()
            
    def on_format_finished(self, count, error_count=0):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()
            
        worker = self.sender()
        if worker:
            cfg = getattr(worker, 'config', {})
            if cfg.get("mode") == "merge":
                new_field_name = cfg.get("new_field")
                new_col = {
                    "column": new_field_name,
                    "type": "Date/Time",
                    "max_len": 20,
                    "sample": "",
                    "selected": True
                }
                self.analysis_results.append(new_col)
                
                # Ensure system columns are in analysis results
                for sf in ["Error", "Modification"]:
                    if not any(r["column"].lower() == sf.lower() for r in self.analysis_results):
                        self.analysis_results.append({
                            "column": sf,
                            "type": "Fixed-length Text",
                            "max_len": 0,
                            "sample": "",
                            "system_field": True
                        })
                        
                self.schema_model.update_data(self.analysis_results)
                
                actual_cols = [r for r in self.analysis_results if not r.get("system_field", False) and not r.get("system_only", False)]
                self.card_cols.set_value(len(actual_cols))
                
                self.gap_all_columns = sorted([r["column"] for r in self.analysis_results], key=lambda x: x.lower())
                
        self.handle_transform_errors(f"Processed date operation for {count} records.", error_count)
        self.reload_file_schema()

    def show_mass_redaction_dialog(self):
        if not self.selected_file_path:
            return
            
        csv_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Mass Redaction Match File", 
            "", 
            "Delimited Files (*.csv *.dat *.txt);;All Files (*.*)"
        )
        if not csv_path:
            return
            
        import csv
        try:
            csv_encoding = processor.get_encoding(csv_path)
            csv_sep, csv_quote = processor.get_delimiters(csv_path, csv_encoding)
                
            with open(csv_path, 'r', encoding=csv_encoding, newline='', errors='ignore') as f:
                reader = csv.reader(f, delimiter=csv_sep, quotechar=csv_quote)
                csv_headers = next(reader)
        except Exception as e:
            show_dark_message(self, "Error", f"Failed to read headers from match file:\n{str(e)}", QMessageBox.Critical)
            return
            
        lf_headers = [item["column"] for item in self.analysis_results]
        
        dlg = MassRedactionDialog(lf_headers, csv_headers, csv_path, self)
        if dlg.exec() != QDialog.Accepted:
            return
            
        lf_match, csv_match, replacement_string, matched_fields = dlg.get_selections()
        if not matched_fields:
            show_dark_message(self, "Warning", "No target fields to process.", QMessageBox.Warning)
            return
            
        if not self.check_create_backup():
            return
            
        # Save run record to QSettings history list
        from PyQt5.QtCore import QSettings
        settings = QSettings("RelativityLoadFileAnalyzer", "MassRedactionHistory")
        history = settings.value("history", [])
        import datetime
        run_record = {
            "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "file": os.path.basename(self.selected_file_path),
            "csv": os.path.basename(csv_path),
            "fields": matched_fields,
            "value": replacement_string
        }
        history.insert(0, run_record)
        history = history[:10]
        settings.setValue("history", history)
            
        self.progress = QProgressDialog("Performing mass redactions...", None, 0, 0, self)
        self.progress.setStyleSheet(GLOBAL_STYLE)
        from PyQt5.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()
        
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        self.worker = MassRedactionWorker(
            self.selected_file_path, csv_path, replacement_string,
            lf_match, csv_match, matched_fields, enc, sep, qt
        )
        self.worker.finished.connect(self.on_mass_redaction_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def on_mass_redaction_finished(self, count, error_count=0):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()
        
        # Ensure system columns are in analysis results
        for sf in ["Error", "Modification"]:
            if not any(r["column"].lower() == sf.lower() for r in self.analysis_results):
                self.analysis_results.append({
                    "column": sf,
                    "type": "Fixed-length Text",
                    "max_len": 0,
                    "sample": "",
                    "system_field": True
                })
        self.schema_model.update_data(self.analysis_results)
        
        self.handle_transform_errors(f"Mass redaction complete: {count} records updated.", error_count)
        self.reload_file_schema()

    def filter_by_errors(self):
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        config = {"mode": "field", "field": "Error", "query": ".+", "regex": True}
        
        self.progress = QProgressDialog("Filtering errored records...", None, 0, 0, self)
        self.progress.setStyleSheet(GLOBAL_STYLE)
        from PyQt5.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()
        
        from pyside_workers import PreviewSearchWorker
        self.search_worker = PreviewSearchWorker(self.selected_file_path, config, enc, sep, qt)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.error.connect(self.on_error)
        self.search_worker.start()

    def handle_transform_errors(self, success_msg, error_count):
        if error_count > 0:
            reply = QMessageBox.question(
                self,
                "Transform Errors",
                f"{success_msg}\n\nTransform complete with errors ({error_count} failed). Would you like to filter the table to show only the errored records?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.filter_by_errors()
        else:
            show_dark_message(self, "Success", success_msg, QMessageBox.Information)

    def flash_button(self, btn):
        btn.setStyleSheet("border: 2px solid #3B82F6; background-color: #1E293B; color: #FFFFFF;")
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(600, lambda: btn.setStyleSheet(""))

    def on_encoding_selected(self, val):
        self.cb_encoding.setCurrentText(val)
        self.btn_encoding.setText(f"Encoding: {val}")
        self.flash_button(self.btn_encoding)
        if self.selected_file_path:
            self.start_analysis()

    def on_sep_selected(self, val):
        self.cb_sep.setCurrentText(val)
        self.update_delimiters_button_text()
        self.flash_button(self.btn_delimiters)
        if self.selected_file_path:
            self.start_analysis()

    def on_quote_selected(self, val):
        self.cb_quote.setCurrentText(val)
        self.update_delimiters_button_text()
        self.flash_button(self.btn_delimiters)
        if self.selected_file_path:
            self.start_analysis()

    def update_delimiters_button_text(self):
        short_seps = {
            "Auto": "Auto",
            "DC4 (chr20)": "DC4",
            "Comma (,)": ",",
            "Pipe (|)": "|",
            "Tab (\\t)": "\\t"
        }
        short_quotes = {
            "Auto": "Auto",
            "Thorn (chr254)": "Thorn",
            "Double Quote (\")": "\"",
            "None": "None"
        }
        sep_val = self.cb_sep.currentText()
        quote_val = self.cb_quote.currentText()
        s_short = short_seps.get(sep_val, sep_val)
        q_short = short_quotes.get(quote_val, quote_val)
        if s_short == "Auto" and q_short == "Auto":
            self.btn_delimiters.setText("Delimiters: Auto")
        else:
            self.btn_delimiters.setText(f"Delimiters: {s_short} / {q_short}")

    def check_create_backup(self):
        if self.backup_created:
            return True
        from PyQt5.QtWidgets import QMessageBox
        reply = show_dark_warning_yes_no_cancel(
            self, 
            "Warning: Immediate Changes", 
            "Changes to the source file are immediate.\n\nDo you want to create a backup file (.bak) before proceeding?"
        )
        if reply == QMessageBox.Cancel:
            return False
        if reply == QMessageBox.Yes:
            import shutil, datetime
            try:
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                shutil.copy2(self.selected_file_path, f"{self.selected_file_path}_{ts}.bak")
                self.backup_created = True
                return True
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to create backup:\n{str(e)}", QMessageBox.Critical)
                return False
        return True

    def run_quick_search(self):
        if not self.selected_file_path:
            return
            
        query = self.txt_quick_search.text().strip()
        if not query:
            self.preview_is_filtered_mode = False
            self.lbl_preview_hits.setText("0 hits")
            self.load_preview_data()
            return
            
        config = {"mode": "full", "query": query}
        
        self.progress = QProgressDialog("Searching file...", None, 0, 0, self)
        self.progress.setStyleSheet(GLOBAL_STYLE)
        from PyQt5.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()
        
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        self.search_worker = PreviewSearchWorker(self.selected_file_path, config, enc, sep, qt)
        self.search_worker.finished.connect(self.on_search_finished)
        self.search_worker.error.connect(self.on_error)
        self.search_worker.start()

    def clear_all_searches(self):
        self.txt_quick_search.clear()
        self.preview_is_filtered_mode = False
        self.preview_hits = []
        self.lbl_preview_hits.setText("0 hits")
        self.update_applied_search_card(None)
        self.load_preview_data()

    def update_applied_search_card(self, config=None):
        if not config:
            self.card_search.set_value("None")
            self.btn_clear_search.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
            self.search_status_container.setVisible(False)
            return
            
        mode = config.get("mode", "full")
        query = config.get("query", "")
        
        # Limit length of query shown in the card to keep it clean
        if len(query) > 50:
            query_disp = query[:47] + "..."
        else:
            query_disp = query
            
        if mode == "field":
            field = config.get("field", "")
            is_regex = config.get("regex", False)
            if is_regex:
                self.card_search.set_value(f"Field [{field}] matches regex '{query_disp}'")
            else:
                self.card_search.set_value(f"Field [{field}] contains '*{query_disp}*'")
        elif mode == "query":
            self.card_search.set_value(f"Boolean expression: '{query_disp}'")
        else:
            self.card_search.set_value(f"Record contains '*{query_disp}*'")
            
        self.btn_clear_search.setStyleSheet("background-color: #F97316; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.search_status_container.setVisible(True)

    def show_export_dialog(self):
        if not self.selected_file_path:
            return
            
        is_filtered_active = getattr(self, 'preview_is_filtered_mode', False) and bool(getattr(self, 'preview_hits', []))
        is_mapped_active = bool(getattr(self, 'rename_map', {}))
        
        dlg = ExportDialog(is_filtered_active, is_mapped_active, self)
        if dlg.exec() == QDialog.Accepted:
            use_filter_sort, use_mapped, limit_search, include_audit = dlg.get_data()
            self.run_export(use_filter_sort, use_mapped, limit_search, include_audit)

    def run_export(self, use_filter_sort, use_mapped, limit_search, include_audit=False):
        keep_columns = None
        if use_filter_sort:
            keep_columns = []
            for item in self.schema_model._data:
                col_name = item["column"]
                is_sys = item.get("system_field", False)
                if is_sys and not include_audit:
                    continue
                if item.get("selected", True):
                    keep_columns.append(col_name)
        elif not include_audit:
            keep_columns = [
                item["column"] for item in self.schema_model._data 
                if not item.get("system_field", False)
            ]
            
        cross_ref_path = self.cross_ref_path if use_mapped else None
        target_lines = self.preview_hits if limit_search else None
        
        filter_str = "DAT Files (*.dat);;CSV Files (*.csv);;Excel Files (*.xlsx)"
        path, _ = QFileDialog.getSaveFileName(self, "Export Final Load File", "", filter_str)
        if not path:
            return
            
        self.progress = QProgressDialog("Exporting load file...", None, 0, 0, self)
        self.progress.setStyleSheet(GLOBAL_STYLE)
        from PyQt5.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()
        
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        self.worker = RemapWorker(self.selected_file_path, cross_ref_path, path, keep_columns, enc, sep, qt, target_lines)
        self.worker.finished.connect(self.on_export_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()

    def show_append_field_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            return
        columns = [r["column"] for r in self.analysis_results]
        dialog = AppendFieldDialog(columns, self)
        if dialog.exec() == QDialog.Accepted:
            new_field_name, val_type, static_val, copy_field, prefix, padding = dialog.get_data()
            if not new_field_name:
                return
                
            if not self.check_create_backup():
                return
                
            self.progress = QProgressDialog("Appending field...", None, 0, 0, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            from PyQt5.QtCore import Qt
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Please Wait")
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
            
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            limit_filtered = getattr(self, 'preview_is_filtered_mode', False)
            target_lines = self.preview_hits if limit_filtered else None
            
            self.worker = AppendFieldWorker(
                self.selected_file_path,
                new_field_name,
                val_type,
                static_val=static_val,
                copy_field=copy_field,
                prefix=prefix,
                padding=padding,
                encoding=enc,
                sep=sep,
                quote=qt,
                target_line_numbers=target_lines
            )
            self.worker.new_field_name = new_field_name
            self.worker.val_type = val_type
            self.worker.static_val = static_val
            self.worker.copy_field = copy_field
            self.worker.prefix = prefix
            self.worker.padding = padding
            self.worker.finished.connect(self.on_append_finished)
            self.worker.error.connect(self.on_error)
            self.worker.start()

    def on_append_finished(self, count, error_count=0):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()
            
        worker = self.sender()
        if worker:
            new_field_name = worker.new_field_name
            val_type = worker.val_type
            static_val = worker.static_val
            copy_field = worker.copy_field
            prefix = worker.prefix
            padding = worker.padding
            
            inferred_type = "Fixed-length Text"
            inferred_max_len = 0
            inferred_sample = ""
            
            if val_type == "row_num":
                inferred_type = "Whole Number"
                inferred_max_len = len(prefix) + (padding if padding > 0 else 5)
                inferred_sample = prefix + ("1".zfill(padding) if padding > 0 else "1")
            elif val_type == "static":
                inferred_sample = static_val
                inferred_max_len = len(static_val)
                if static_val.isdigit():
                    inferred_type = "Whole Number"
                else:
                    try:
                        float(static_val)
                        inferred_type = "Decimal"
                    except ValueError:
                        inferred_type = "Fixed-length Text"
            elif val_type == "copy":
                src_col = next((r for r in self.analysis_results if r["column"].lower() == copy_field.lower()), None)
                if src_col:
                    inferred_type = src_col.get("type", "Fixed-length Text")
                    inferred_max_len = src_col.get("max_len", 0)
                    inferred_sample = src_col.get("sample", "")
            
            new_col = {
                "column": new_field_name,
                "type": inferred_type,
                "max_len": inferred_max_len,
                "sample": inferred_sample,
                "selected": True
            }
            self.analysis_results.append(new_col)
            
            # Ensure system columns are in analysis results
            for sf in ["Error", "Modification"]:
                if not any(r["column"].lower() == sf.lower() for r in self.analysis_results):
                    self.analysis_results.append({
                        "column": sf,
                        "type": "Fixed-length Text",
                        "max_len": 0,
                        "sample": "",
                        "system_field": True
                    })
                    
            self.schema_model.update_data(self.analysis_results)
            actual_cols = [r for r in self.analysis_results if not r.get("system_field", False) and not r.get("system_only", False)]
            self.card_cols.set_value(len(actual_cols))
            self.gap_all_columns = sorted([r["column"] for r in self.analysis_results], key=lambda x: x.lower())
            self.reload_file_schema()
            
        self.handle_transform_errors(f"Appended new field to {count} records.", error_count)

    def show_gap_report_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            show_dark_message(self, "Warning", "Please open a file and analyze it first.", QMessageBox.Warning)
            return
        dialog = GapReportDialog(self.selected_file_path, self.analysis_results, self)
        dialog.exec()

    def show_merge_fields_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            return
        columns = [r["column"] for r in self.analysis_results]
        dialog = MergeFieldsDialog(columns, self)
        if dialog.exec() == QDialog.Accepted:
            first_field, second_field, delimiter, new_field_name = dialog.get_data()
            if not new_field_name:
                return
                
            if not self.check_create_backup():
                return
                
            self.progress = QProgressDialog("Merging fields...", None, 0, 0, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            from PyQt5.QtCore import Qt
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Please Wait")
            self.progress.setWindowModality(Qt.WindowModal)
            self.progress.show()
            
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            limit_filtered = getattr(self, 'preview_is_filtered_mode', False)
            target_lines = self.preview_hits if limit_filtered else None
            
            self.worker = MergeFieldsWorker(
                self.selected_file_path,
                first_field,
                second_field,
                delimiter,
                new_field_name,
                encoding=enc,
                sep=sep,
                quote=qt,
                target_line_numbers=target_lines
            )
            self.worker.new_field_name = new_field_name
            self.worker.first_field = first_field
            self.worker.second_field = second_field
            self.worker.delimiter = delimiter
            self.worker.finished.connect(self.on_merge_finished)
            self.worker.error.connect(self.on_error)
            self.worker.start()
            
    def on_merge_finished(self, count, error_count=0):
        if hasattr(self, 'progress') and self.progress:
            self.progress.close()
            
        worker = self.sender()
        if worker:
            new_field_name = worker.new_field_name
            first_field = worker.first_field
            second_field = worker.second_field
            delimiter = worker.delimiter
            
            f1 = next((r for r in self.analysis_results if r["column"].lower() == first_field.lower()), None)
            f2 = next((r for r in self.analysis_results if r["column"].lower() == second_field.lower()), None)
            
            f1_len = f1.get("max_len", 0) if f1 else 0
            f2_len = f2.get("max_len", 0) if f2 else 0
            inferred_max_len = f1_len + len(delimiter) + f2_len
            
            f1_sample = f1.get("sample", "") if f1 else ""
            f2_sample = f2.get("sample", "") if f2 else ""
            inferred_sample = f1_sample + delimiter + f2_sample
            
            inferred_type = "Fixed-length Text"
            if inferred_max_len > 256:
                inferred_type = "Long Text"
                
            new_col = {
                "column": new_field_name,
                "type": inferred_type,
                "max_len": inferred_max_len,
                "sample": inferred_sample,
                "selected": True
            }
            self.analysis_results.append(new_col)
            
            # Ensure system columns are in analysis results
            for sf in ["Error", "Modification"]:
                if not any(r["column"].lower() == sf.lower() for r in self.analysis_results):
                    self.analysis_results.append({
                        "column": sf,
                        "type": "Fixed-length Text",
                        "max_len": 0,
                        "sample": "",
                        "system_field": True
                    })
                    
            self.schema_model.update_data(self.analysis_results)
            actual_cols = [r for r in self.analysis_results if not r.get("system_field", False) and not r.get("system_only", False)]
            self.card_cols.set_value(len(actual_cols))
            self.gap_all_columns = sorted([r["column"] for r in self.analysis_results], key=lambda x: x.lower())
            self.reload_file_schema()
            
        self.handle_transform_errors(f"Merged fields for {count} records.", error_count)

    def toggle_all_fields(self, state):
        self.schema_model.beginResetModel()
        is_checked = (state == Qt.Checked)
        for item in self.schema_model._data:
            item["selected"] = is_checked
        self.schema_model.endResetModel()

    def on_schema_table_clicked(self, proxy_idx):
        if not proxy_idx.isValid():
            return
        col_name = self.schema_model.headers[self.schema_proxy.mapToSource(proxy_idx).column()]
        if col_name == "Export":
            src_idx = self.schema_proxy.mapToSource(proxy_idx)
            row = src_idx.row()
            self.schema_model.beginResetModel()
            self.schema_model._data[row]["selected"] = not self.schema_model._data[row].get("selected", True)
            self.schema_model.endResetModel()

    def move_selected_field_up(self):
        idx = self.schema_table.selectionModel().currentIndex()
        if not idx.isValid():
            return
        src_idx = self.schema_proxy.mapToSource(idx)
        if not src_idx.isValid():
            return
        row = src_idx.row()
        if self.schema_model.move_row(row, -1):
            new_src_idx = self.schema_model.index(row - 1, idx.column())
            new_proxy_idx = self.schema_proxy.mapFromSource(new_src_idx)
            self.schema_table.setCurrentIndex(new_proxy_idx)

    def move_selected_field_down(self):
        idx = self.schema_table.selectionModel().currentIndex()
        if not idx.isValid():
            return
        src_idx = self.schema_proxy.mapToSource(idx)
        if not src_idx.isValid():
            return
        row = src_idx.row()
        if self.schema_model.move_row(row, 1):
            new_src_idx = self.schema_model.index(row + 1, idx.column())
            new_proxy_idx = self.schema_proxy.mapFromSource(new_src_idx)
            self.schema_table.setCurrentIndex(new_proxy_idx)

    def open_image_load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Image Load File", "", "Image Load Files (*.opt *.lfp *.dii *.smi);;Opticon (*.opt);;IPRO LFP (*.lfp);;Summation DII (*.dii);;Summation SMI (*.smi);;All Files (*.*)"
        )
        if not file_path:
            return
        self.import_image_load_file_path(file_path)

    def import_image_load_file_path(self, file_path: str):
        try:
            self.opt_store = parse_image_load_file(file_path)
            self.last_image_load_file_path = file_path

            # Clear out image viewer immediately
            self.studio_doc_viewer.clear_viewer()
            self.preview_doc_viewer.clear_viewer()

            # Populate DocID dropdown but default to BLANK, blocking signals so it doesn't trigger immediately
            fields = [""] + ([r["column"] for r in self.analysis_results] if self.analysis_results else [])
            self.cb_image_doc_id.blockSignals(True)
            self.cb_image_doc_id.clear()
            self.cb_image_doc_id.addItems(fields)
            self.cb_image_doc_id.setCurrentIndex(0)
            self.image_doc_id_field = ""
            self.cb_image_doc_id.blockSignals(False)

            # Universal load file population: list all flat page records immediately
            pages = self.opt_store.get_all_pages()
            self.image_table_model.update_pages(pages)

            if pages:
                self.image_table.selectRow(0)
                self.lbl_image_status_badge.setText(f"Loaded: {len(pages):,} pages (Unmapped)")
                self.lbl_image_status_badge.setStyleSheet("color: #FBBF24; font-weight: bold; padding: 4px 8px; background-color: #1E293B; border-radius: 4px;")
            else:
                self.lbl_image_status_badge.setText("No Images Found")
                self.lbl_image_status_badge.setStyleSheet("color: #F87171; font-weight: bold; padding: 4px 8px; background-color: #1E293B; border-radius: 4px;")

            show_dark_message(self, "Load File Imported", f"Successfully loaded {len(self.opt_store)} documents from {os.path.basename(file_path)}. Choose a DocID Field dropdown value to map paths and display images.")
        except Exception as e:
            show_dark_message(self, "Load File Error", str(e), QMessageBox.Critical)

    def update_image_studio_link_status(self):
        pages = self.opt_store.get_all_pages()
        self.image_table_model.update_pages(pages)

        if pages:
            self.image_table.selectRow(0)
            self.image_current_doc_idx = 0
            self.lbl_image_status_badge.setText(f"Linked: {len(pages):,} pages ({len(self.opt_store):,} docs)")
            self.lbl_image_status_badge.setStyleSheet("color: #4ADE80; font-weight: bold; padding: 4px 8px; background-color: #1E293B; border-radius: 4px;")
            self.update_nav_controls()
        else:
            self.lbl_image_status_badge.setText("No Images Linked")
            self.lbl_image_status_badge.setStyleSheet("color: #F87171; font-weight: bold; padding: 4px 8px; background-color: #1E293B; border-radius: 4px;")

    def on_doc_id_field_changed(self, text):
        self.image_doc_id_field = text
        if not text or not hasattr(self, "opt_store") or not self.opt_store:
            # Re-mapping to blank/invalid should clear viewer smoothly without index crashes
            self.studio_doc_viewer.clear_viewer()
            pages = self.opt_store.get_all_pages() if (hasattr(self, "opt_store") and self.opt_store) else []
            self.image_table_model.update_pages(pages)
            self.lbl_image_status_badge.setText("No Images Linked")
            self.lbl_image_status_badge.setStyleSheet("color: #F87171; font-weight: bold; padding: 4px 8px; background-color: #1E293B; border-radius: 4px;")
            return

        # Perform path verification and remapping logic now that user has explicitly chosen a DocID field
        base_dir = os.path.dirname(getattr(self, "last_image_load_file_path", ""))
        first_img = self.opt_store.get_first_image_path()
        if first_img:
            test_full_path = resolve_full_image_path(first_img, base_dir)
            if not os.path.exists(test_full_path):
                msg = (
                    f"The first image file was not found at expected location:\n\n"
                    f"{test_full_path}\n\n"
                    f"Expected relative path: {first_img}\n\n"
                    f"Would you like to browse and select the actual image file on disk to remap the base directory?"
                )
                res = show_dark_warning_yes_no_cancel(self, "Image Path Not Found", msg)
                if res == QMessageBox.Yes:
                    actual_img_path, _ = QFileDialog.getOpenFileName(
                        self, f"Locate Image ({os.path.basename(first_img)})", base_dir, "Images & PDFs (*.tif *.tiff *.jpg *.jpeg *.pdf *.png);;All Files (*.*)"
                    )
                    if actual_img_path:
                        base_dir = infer_base_dir(first_img, actual_img_path)

        self.studio_doc_viewer.set_stores(self.opt_store, base_dir=base_dir)
        self.preview_doc_viewer.set_stores(self.opt_store, base_dir=base_dir)

        # Trigger-based metadata synchronization: immediately update links and trigger first row selection to sync tabs
        self.update_image_studio_link_status()
        if hasattr(self, "image_table") and self.image_table_model.pages:
            self.image_table.selectRow(0)

    def on_image_table_row_selected(self, selected, deselected):
        indexes = self.image_table.selectionModel().selectedRows()
        if not indexes:
            return
        row = indexes[0].row()
        pages = self.image_table_model.pages
        if 0 <= row < len(pages):
            row_item = pages[row]
            if len(row_item) == 6:
                bates, doc_id, page_num, total_pages, vol, path = row_item
            else:
                bates, doc_id, page_num, vol, path = row_item
            page_idx = page_num - 1

            if hasattr(self, "opt_store") and self.opt_store and doc_id in self.opt_store.doc_id_list:
                self.image_current_doc_idx = self.opt_store.doc_id_list.index(doc_id)

            # Bidirectional cross-tab synchronization: Find record row index in preview_model and select it
            # Temporarily block signals to prevent selection recursion loops
            self.preview_table.selectionModel().blockSignals(True)
            try:
                for idx, r_data in enumerate(self.preview_model._data):
                    # Compare control field or first column
                    r_id = r_data[0] if len(r_data) > 0 else ""
                    if str(r_id).strip().lower() == str(doc_id).strip().lower():
                        self.preview_table.selectRow(idx)
                        break
            finally:
                self.preview_table.selectionModel().blockSignals(False)

            # Cross-tab binding: Find metadata record whose identifier matches the currently selected DocID
            record_dict = self.doc_id_metadata_map.get(doc_id)
            if not record_dict:
                # Case-insensitive search inside self.doc_id_metadata_map
                doc_id_lower = str(doc_id).strip().lower()
                for k, v in self.doc_id_metadata_map.items():
                    if str(k).strip().lower() == doc_id_lower:
                        record_dict = v
                        break

            if record_dict:
                self.studio_doc_viewer.set_stores(self.opt_store, {doc_id: record_dict}, base_dir=self.studio_doc_viewer.base_dir)
            
            self.studio_doc_viewer.record_selected(doc_id, page_idx=page_idx)
            self.update_nav_controls()

    def update_nav_controls(self):
        if not hasattr(self, 'lbl_nav_info'):
            return
        total_docs = len(self.opt_store.doc_id_list)
        if total_docs == 0:
            self.lbl_nav_info.setText("Doc 0 of 0 | Page 0 of 0")
            return

        doc_id = self.opt_store.doc_id_list[self.image_current_doc_idx]
        doc = self.opt_store.get_document(doc_id)
        current_page = self.studio_doc_viewer.current_page_idx + 1 if doc else 0
        total_pages = doc.page_count if doc else 0

        self.lbl_nav_info.setText(f"Doc {self.image_current_doc_idx + 1:,} of {total_docs:,} ({doc_id}) | Page {current_page} of {total_pages}")

    def nav_first_doc(self):
        if self.image_table_model.pages:
            self.image_table.selectRow(0)

    def nav_prev_doc(self):
        indexes = self.image_table.selectionModel().selectedRows()
        if not indexes:
            return
        cur_row = indexes[0].row()
        pages = self.image_table_model.pages
        # Search backwards for previous document break row (Bates == DocID)
        for r in range(cur_row - 1, -1, -1):
            row_item = pages[r]
            bates, doc_id = row_item[0], row_item[1]
            if str(bates).strip().lower() == str(doc_id).strip().lower():
                self.image_table.selectRow(r)
                return
        self.image_table.selectRow(0)

    def nav_next_doc(self):
        indexes = self.image_table.selectionModel().selectedRows()
        if not indexes:
            return
        cur_row = indexes[0].row()
        pages = self.image_table_model.pages
        # Search forwards for next document break row (Bates == DocID)
        for r in range(cur_row + 1, len(pages)):
            row_item = pages[r]
            bates, doc_id = row_item[0], row_item[1]
            if str(bates).strip().lower() == str(doc_id).strip().lower():
                self.image_table.selectRow(r)
                return

    def nav_last_doc(self):
        pages = self.image_table_model.pages
        if not pages:
            return
        # Find last document break row
        for r in range(len(pages) - 1, -1, -1):
            row_item = pages[r]
            bates, doc_id = row_item[0], row_item[1]
            if str(bates).strip().lower() == str(doc_id).strip().lower():
                self.image_table.selectRow(r)
                return
        self.image_table.selectRow(len(pages) - 1)

    def nav_prev_page(self):
        indexes = self.image_table.selectionModel().selectedRows()
        if not indexes:
            return
        cur_row = indexes[0].row()
        if cur_row > 0:
            self.image_table.selectRow(cur_row - 1)

    def nav_next_page(self):
        indexes = self.image_table.selectionModel().selectedRows()
        if not indexes:
            return
        cur_row = indexes[0].row()
        if cur_row + 1 < len(self.image_table_model.pages):
            self.image_table.selectRow(cur_row + 1)

    def handle_preview_nav(self, action: str):
        # Preview viewer bottom controls:
        # Document controls (first_doc, prev_doc, next_doc, last_doc) move selected row by 1 record.
        # Page controls (prev_page, next_page) traverse pages inside the active document.
        indexes = self.preview_table.selectionModel().selectedRows()
        if not indexes:
            return
        cur_row = indexes[0].row()
        total_rows = len(self.preview_model._data)

        if action == "prev_page":
            current_page = self.preview_doc_viewer.current_page_idx
            if current_page > 0:
                self.preview_doc_viewer.record_selected(self.preview_doc_viewer.current_doc_id, page_idx=current_page - 1)
        elif action == "next_page":
            current_page = self.preview_doc_viewer.current_page_idx
            if current_page + 1 < self.preview_doc_viewer.total_doc_pages:
                self.preview_doc_viewer.record_selected(self.preview_doc_viewer.current_doc_id, page_idx=current_page + 1)
        elif action == "prev_doc":
            if cur_row > 0:
                self.preview_table.selectRow(cur_row - 1)
            else:
                self.preview_prev() # Page grid back
        elif action == "next_doc":
            if cur_row + 1 < total_rows:
                self.preview_table.selectRow(cur_row + 1)
            else:
                self.preview_next() # Page grid forward
        elif action == "first_doc":
            self.preview_table.selectRow(0)
        elif action == "last_doc":
            if total_rows > 0:
                self.preview_table.selectRow(total_rows - 1)

    def handle_studio_nav(self, action: str):
        # Studio viewer navigation directly controls flat image table row selections
        if action == "first_doc": self.nav_first_doc()
        elif action == "prev_doc": self.nav_prev_doc()
        elif action == "prev_page": self.nav_prev_page()
        elif action == "next_page": self.nav_next_page()
        elif action == "next_doc": self.nav_next_doc()
        elif action == "last_doc": self.nav_last_doc()

    def on_preview_page_changed(self, doc_id, current_page, total_pages):
        pass

    def on_studio_page_changed(self, doc_id, current_page, total_pages):
        # Synchronize selectRow index in image table to match current_page index
        pages = self.image_table_model.pages
        for idx, page_tuple in enumerate(pages):
            p_doc_id = page_tuple[1]
            p_num = page_tuple[2]
            if str(p_doc_id).strip().lower() == str(doc_id).strip().lower() and p_num == current_page:
                self.image_table.selectionModel().blockSignals(True)
                try:
                    self.image_table.selectRow(idx)
                finally:
                    self.image_table.selectionModel().blockSignals(False)
                break

    def on_open_clicked(self):
        current_tab = self.tabs.currentIndex()
        if current_tab == 2:  # Image Preview Tab
            self.open_image_load_file()
        else:
            self.open_file()

    def on_tab_changed(self, index):
        if index == 2:
            self.btn_open.setText("Open Image Load File")
        else:
            self.btn_open.setText("Open Data Load File")

        if index == 1:
            self.load_preview_data()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(GLOBAL_STYLE)
    
    icon_path = get_asset_path("assets", "app_icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    window = RelativityApp()
    
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window.selected_file_path = sys.argv[1]
        window.start_analysis()
        
    window.show()
    sys.exit(app.exec())
