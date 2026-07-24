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

# Add DLL directories for PySide6 DLL resolution on Windows and keep cookies to prevent garbage collection
dll_cookies = []
if sys.platform == 'win32':
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
        internal_dir = os.path.join(base_dir, "_internal")
        if os.path.exists(internal_dir):
            for sub in ("", "PySide6", "shiboken6"):
                target_path = os.path.join(internal_dir, sub) if sub else internal_dir
                if os.path.exists(target_path):
                    try:
                        cookie = os.add_dll_directory(target_path)
                        dll_cookies.append(cookie)
                    except Exception:
                        pass
            
            # Diagnostic loader using ctypes to print exact DLL errors
            import ctypes
            dlls_to_test = [
                os.path.join(internal_dir, "shiboken6", "shiboken6.abi3.dll"),
                os.path.join(internal_dir, "PySide6", "pyside6.abi3.dll"),
                os.path.join(internal_dir, "PySide6", "Qt6Core.dll"),
                os.path.join(internal_dir, "PySide6", "Qt6Gui.dll"),
                os.path.join(internal_dir, "PySide6", "Qt6Widgets.dll"),
                os.path.join(internal_dir, "PySide6", "QtWidgets.pyd"),
            ]
            failed_dlls = []
            for dll_path in dlls_to_test:
                if os.path.exists(dll_path):
                    try:
                        ctypes.CDLL(dll_path)
                    except Exception as e:
                        failed_dlls.append(f"{os.path.basename(dll_path)}: {str(e)}")
                else:
                    failed_dlls.append(f"{os.path.basename(dll_path)} (does not exist)")
            
            if failed_dlls:
                os_ver = sys.getwindowsversion()
                os_info = f"Windows Version: {os_ver.major}.{os_ver.minor} (Build {os_ver.build})\n"
                has_std = hasattr(ctypes.windll.kernel32, "SetThreadDescription")
                os_info += f"Has SetThreadDescription API: {has_std}\n"
                
                msg = f"{os_info}\nDLL Load Diagnostic Failures:\n\n" + "\n".join(failed_dlls)
                ctypes.windll.user32.MessageBoxW(0, msg, "DLL Diagnostic Error", 0x10)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFileDialog, QTabWidget, QTableView,
    QHeaderView, QLineEdit, QComboBox, QFrame, QMessageBox, QProgressDialog,
    QDialog, QTextEdit, QSplitter, QMenu, QSpinBox, QFormLayout, QCheckBox,
    QGridLayout, QListWidget, QSizePolicy, QTableWidget, QTableWidgetItem,
    QProgressBar, QGroupBox
)
from PySide6.QtCore import Qt, QSize, QSettings
from PySide6.QtGui import QIcon, QFont, QPixmap, QKeySequence, QSyntaxHighlighter, QTextCharFormat, QColor, QAction, QTextCursor
import processor
import opt_engine
from opt_engine import OptDocumentStore, OptDocument, parse_image_load_file, infer_base_dir, resolve_full_image_path
from unified_document_viewer import UnifiedDocumentViewer
from pyside_workers import AnalysisWorker, RemapWorker, GapWorker, PreviewSearchWorker, ReplaceWorker, AppendFieldWorker, MergeFieldsWorker, MassRedactionWorker, VolumeMergeWorker
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

def show_dark_message(parent, title, text, icon=QMessageBox.Icon.Information):
    from PySide6.QtCore import Qt
    msg = QMessageBox(icon, title, text, QMessageBox.StandardButton.Ok, parent)
    msg.setStyleSheet(GLOBAL_STYLE)
    msg.setWindowFlags(msg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
    apply_dark_titlebar(msg)
    return msg.exec()

def show_dark_warning_yes_no_cancel(parent, title, text):
    from PySide6.QtCore import Qt
    msg = QMessageBox(QMessageBox.Icon.Warning, title, text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel, parent)
    msg.setStyleSheet(GLOBAL_STYLE)
    msg.setWindowFlags(msg.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
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
QTableView, QTableWidget {
    background-color: #1E293B;
    alternate-background-color: #0F172A;
    border: none;
    gridline-color: #334155;
    outline: none;
}
QTableView::item, QTableWidget::item {
    outline: none;
    border: none;
}
QTableView::item:selected, QTableWidget::item:selected {
    background-color: #3B82F6;
    color: #FFFFFF;
    outline: none;
}
QTableView::item:focus, QTableWidget::item:focus {
    outline: none;
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
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    margin: 2px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #3B82F6;
    color: #FFFFFF;
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
        from PySide6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(5)
        
        title_label = QLabel("Applied Search:")
        title_label.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        title_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        
        self.val_label = QLabel("None")
        self.val_label.setStyleSheet("color: #60A5FA; font-size: 13px; font-weight: bold;")
        self.val_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        layout.addWidget(title_label)
        layout.addWidget(self.val_label)
        
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
        from PySide6.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Find & Replace")
        self.resize(400, 250)
        apply_dark_titlebar(self)
        
        layout = QFormLayout(self)
        
        self.cb_field = QComboBox()
        self.cb_field.addItems(sorted(columns, key=lambda x: x.lower()))
        
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
        
        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_replace = QPushButton("Replace")
        self.btn_replace.clicked.connect(self.accept)
        self.btn_replace.setStyleSheet("background-color: #10B981; color: white;")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        btn_layout.addWidget(self.btn_replace)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addRow("Target Field:", self.cb_field)
        layout.addRow("Find Pattern:", self.txt_find)
        layout.addRow("Replace With:", self.txt_replace)
        layout.addRow("", self.chk_regex)
        layout.addRow("", self.chk_filtered)
        layout.addRow(QLabel(""))
        layout.addRow(btn_layout)
        
    def closeEvent(self, event):
        self.reject()
        super().closeEvent(event)


    def get_data(self):
        return self.cb_field.currentText(), self.txt_find.text(), self.txt_replace.text(), self.chk_regex.isChecked(), self.chk_filtered.isChecked()


class DateFormatDialog(QDialog):
    def __init__(self, columns, filtered_count=0, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Format Dates")
        self.resize(450, 250)
        apply_dark_titlebar(self)
        
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        
        sorted_cols = sorted(columns, key=lambda x: x.lower())
        
        # Tab 1: Format Existing
        self.tab_format = QWidget()
        fmt_layout = QFormLayout(self.tab_format)
        self.cb_field = QComboBox()
        self.cb_field.addItems(sorted_cols)
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
        self.cb_date_field.addItems(sorted_cols)
        self.cb_time_field = QComboBox()
        self.cb_time_field.addItems(sorted_cols)
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
        
        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_format = QPushButton("Run")
        self.btn_format.clicked.connect(self.accept)
        self.btn_format.setStyleSheet("background-color: #10B981; color: white;")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        btn_layout.addWidget(self.btn_format)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
    def closeEvent(self, event):
        self.reject()
        super().closeEvent(event)


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
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QSpinBox
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Append New Field")
        self.resize(400, 240)
        apply_dark_titlebar(self)
        
        self.layout = QFormLayout(self)
        
        self.txt_field_name = QLineEdit()
        self.txt_field_name.setPlaceholderText("New Field Name")
        
        self.cb_val_type = QComboBox()
        self.cb_val_type.addItems(["Static Text", "Record Number (1-based)", "Copy from Field"])
        
        self.txt_static_val = QLineEdit()
        self.txt_static_val.setPlaceholderText("Static Value")
        
        self.cb_copy_field = QComboBox()
        self.cb_copy_field.addItems(sorted(columns, key=lambda x: x.lower()))
        
        self.txt_prefix = QLineEdit()
        self.txt_prefix.setPlaceholderText("e.g. DOC_")
        
        self.txt_padding = QLineEdit()
        self.txt_padding.setPlaceholderText("Enter numeric width (e.g. 5)")
        from PySide6.QtGui import QIntValidator
        self.txt_padding.setValidator(QIntValidator(0, 20, self))
        
        self.cb_val_type.currentTextChanged.connect(self.on_val_type_changed)
        
        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Append")
        self.btn_run.clicked.connect(self.accept)
        self.btn_run.setStyleSheet("background-color: #10B981; color: white;")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_cancel)
        
        self.layout.addRow("New Field Name:", self.txt_field_name)
        self.layout.addRow("Value Type:", self.cb_val_type)
        self.layout.addRow("Static Value:", self.txt_static_val)
        self.layout.addRow("Copy Source Field:", self.cb_copy_field)
        self.layout.addRow("Record Number Prefix:", self.txt_prefix)
        self.layout.addRow("Zero Padding Width (Numeric Hint):", self.txt_padding)
        self.layout.addRow(QLabel(""))
        self.layout.addRow(btn_layout)
        
        # Initialize default visibility
        self.on_val_type_changed("Static Text")
        
    def closeEvent(self, event):
        self.reject()
        super().closeEvent(event)
        
    def on_val_type_changed(self, text):
        # Dynamically show/hide fields based on type selection
        is_static = (text == "Static Text")
        is_copy = (text == "Copy from Field")
        is_rownum = (text == "Record Number (1-based)")
        
        # QFormLayout.setRowVisible is supported in PySide6
        self.layout.setRowVisible(self.txt_static_val, is_static)
        self.layout.setRowVisible(self.cb_copy_field, is_copy)
        self.layout.setRowVisible(self.txt_prefix, is_rownum)
        self.layout.setRowVisible(self.txt_padding, is_rownum)
        
        # Reset sizes dynamically
        self.adjustSize()
        
    def get_data(self):
        val_type_map = {
            "Static Text": "static",
            "Record Number (1-based)": "row_num",
            "Copy from Field": "copy"
        }
        padding_val = 0
        try:
            txt = self.txt_padding.text().strip()
            if txt:
                padding_val = int(txt)
        except ValueError:
            padding_val = 0
            
        return (
            self.txt_field_name.text().strip(),
            val_type_map[self.cb_val_type.currentText()],
            self.txt_static_val.text(),
            self.cb_copy_field.currentText(),
            self.txt_prefix.text(),
            padding_val
        )

class MergeFieldsDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Merge Two Fields")
        self.resize(400, 250)
        apply_dark_titlebar(self)
        
        layout = QFormLayout(self)
        
        sorted_cols = sorted(columns, key=lambda x: x.lower())
        
        self.cb_first = QComboBox()
        self.cb_first.addItems(sorted_cols)
        
        self.cb_second = QComboBox()
        self.cb_second.addItems(sorted_cols)
        
        self.txt_separator = QLineEdit()
        self.txt_separator.setPlaceholderText("e.g. _ or - or Space")
        
        self.txt_new_field = QLineEdit()
        self.txt_new_field.setPlaceholderText("New Merged Field Name")
        
        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Merge")
        self.btn_run.clicked.connect(self.accept)
        self.btn_run.setStyleSheet("background-color: #10B981; color: white;")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addRow("First Field:", self.cb_first)
        layout.addRow("Second Field:", self.cb_second)
        layout.addRow("Separator Between:", self.txt_separator)
        layout.addRow("New Field Name:", self.txt_new_field)
        layout.addRow(QLabel(""))
        layout.addRow(btn_layout)
        
    def closeEvent(self, event):
        self.reject()
        super().closeEvent(event)
        
    def get_data(self):
        return (
            self.cb_first.currentText(),
            self.cb_second.currentText(),
            self.txt_separator.text(),
            self.txt_new_field.text().strip()
        )

class FieldSortDialog(QDialog):
    def __init__(self, columns, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QRadioButton, QButtonGroup
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Sort Data Preview")
        self.resize(380, 240)
        apply_dark_titlebar(self)
        
        layout = QFormLayout(self)
        
        self.cb_field = QComboBox()
        self.cb_field.addItems(sorted(columns, key=lambda x: x.lower()))
        
        self.cb_type = QComboBox()
        self.cb_type.addItems(["Alphabetical", "Numeric", "Date", "DocID"])
        
        self.bg_order = QButtonGroup(self)
        self.rb_asc = QRadioButton("Ascending")
        self.rb_asc.setChecked(True)
        self.rb_desc = QRadioButton("Descending")
        self.bg_order.addButton(self.rb_asc)
        self.bg_order.addButton(self.rb_desc)
        
        order_layout = QHBoxLayout()
        order_layout.addWidget(self.rb_asc)
        order_layout.addWidget(self.rb_desc)
        
        btn_layout = QHBoxLayout()
        self.btn_sort = QPushButton("Sort")
        self.btn_sort.clicked.connect(self.accept)
        self.btn_sort.setStyleSheet("background-color: #10B981; color: white;")
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_cancel.setStyleSheet("background-color: #334155; color: white;")
        btn_layout.addWidget(self.btn_sort)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addRow("Sort Column:", self.cb_field)
        layout.addRow("Data Type:", self.cb_type)
        layout.addRow("Order:", order_layout)
        layout.addRow(QLabel(""))
        layout.addRow(btn_layout)
        
    def closeEvent(self, event):
        self.reject()
        super().closeEvent(event)
        
    def get_data(self):
        return (
            self.cb_field.currentText(),
            self.cb_type.currentText(),
            self.rb_asc.isChecked()
        )

class ExportDialog(QDialog):
    def __init__(self, is_filtered_active=False, is_mapped_active=False, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
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
        
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QListWidgetItem
        from PySide6.QtCore import QSettings
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
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
        
        sorted_lf_headers = sorted(self.lf_headers, key=lambda x: x.lower())
        sorted_csv_headers = sorted(self.csv_headers, key=lambda x: x.lower())
        
        grid.addWidget(QLabel("Load File Match Field:"), 0, 0)
        self.cb_lf_match = QComboBox()
        self.cb_lf_match.addItems(sorted_lf_headers)
        for idx, h in enumerate(sorted_lf_headers):
            if h.lower() in ("docid", "begdoc", "controlnumber", "control number"):
                self.cb_lf_match.setCurrentIndex(idx)
                break
        grid.addWidget(self.cb_lf_match, 0, 1)
        
        grid.addWidget(QLabel("CSV Match Field (Match Identifier):"), 1, 0)
        self.cb_csv_match = QComboBox()
        self.cb_csv_match.addItems(sorted_csv_headers)
        for idx, h in enumerate(sorted_csv_headers):
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
        
        for h in sorted_lf_headers:
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
        from PySide6.QtCore import QRegularExpression
        self.error_start = -1
        self.error_end = -1
        
        self.rules = []
        
        # 1. Field brackets: [Custodian] -> Cyan #22D3EE
        field_format = QTextCharFormat()
        field_format.setForeground(QColor("#22D3EE"))
        field_format.setFontWeight(QFont.Weight.Bold)
        self.rules.append((QRegularExpression(r"\[[^\]]*\]"), field_format))
        
        # 2. String values: "value" -> Amber #F59E0B
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#F59E0B"))
        self.rules.append((QRegularExpression(r'"[^"]*"'), str_format))
        
        # 3. Connectives & Operators -> Pink/Magenta #EC4899
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#EC4899"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            r"\bAND\b", r"\bOR\b", r"\bNOT\b",
            r"\bLIKE\b", r"\bCONTAINS\b", r"\bIS\b\s+\bSET\b",
            r"=", r"!="
        ]
        for kw in keywords:
            self.rules.append((QRegularExpression(kw, QRegularExpression.PatternOption.CaseInsensitiveOption), keyword_format))

    def set_error_span(self, start, end):
        self.error_start = start
        self.error_end = end
        self.rehighlight()

    def highlightBlock(self, text):
        # 1. Normal syntax coloring
        for expression, fmt in self.rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)
                
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
        from PySide6.QtWidgets import QCompleter
        from PySide6.QtCore import Qt
        
        self.headers = headers
        self.completer = QCompleter(self.headers, parent=self)
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
        from PySide6.QtCore import Qt
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
            cursor.setPosition(cursor_pos, QTextCursor.MoveMode.KeepAnchor)
            
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
        from PySide6.QtCore import Qt, QTimer
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
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
        self.cb_field.addItems(sorted(columns, key=lambda x: x.lower()))
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
        
        # Bottom Dialog buttons
        self.button_box_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_search = QPushButton("Search")
        self.btn_search.clicked.connect(self.accept)
        
        self.button_box_layout.addWidget(self.btn_cancel)
        self.button_box_layout.addWidget(self.btn_search)
        layout.addLayout(self.button_box_layout)

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

    def closeEvent(self, event):
        self.reject()
        super().closeEvent(event)


class PdfPrintDialog(QDialog):
    def __init__(self, metadata_fields, default_doc_id_field, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (QFormLayout, QLineEdit, QPushButton, QCheckBox, 
                                       QComboBox, QHBoxLayout, QVBoxLayout, QLabel, 
                                       QFileDialog, QMessageBox)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Print PDFs & Export Load File")
        self.resize(555, 390)
        apply_dark_titlebar(self)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        # Output folder
        self.txt_out_dir = QLineEdit()
        self.txt_out_dir.setPlaceholderText("Select root output directory")
        self.btn_browse_dir = QPushButton("Browse...")
        self.btn_browse_dir.setStyleSheet("background-color: #334155; color: white; padding: 4px 8px; border-radius: 4px;")
        self.btn_browse_dir.clicked.connect(self.browse_dir)
        
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self.txt_out_dir)
        dir_layout.addWidget(self.btn_browse_dir)
        form_layout.addRow("Root Output Dir:", dir_layout)

        # Group By
        self.cb_group_by = QComboBox()
        sorted_fields = sorted([str(f) for f in metadata_fields], key=str.lower)
        self.cb_group_by.addItems(sorted_fields)
        if default_doc_id_field in sorted_fields:
            self.cb_group_by.setCurrentText(default_doc_id_field)
        form_layout.addRow("Group By Field:", self.cb_group_by)

        # OCR Options
        self.chk_ocr = QCheckBox("Generate Searchable PDFs (OCR)")
        self.chk_ocr.setChecked(False)
        form_layout.addRow("", self.chk_ocr)

        self.cb_ocr_lang = QComboBox()
        self.cb_ocr_lang.addItems(["eng", "spa", "fra", "deu", "chi_sim"])
        self.cb_ocr_lang.setCurrentText("eng")
        form_layout.addRow("Primary OCR Language:", self.cb_ocr_lang)

        # Companion load file options
        self.chk_companion = QCheckBox("Generate Companion Load File")
        self.chk_companion.setChecked(True)
        form_layout.addRow("", self.chk_companion)

        self.cb_companion_format = QComboBox()
        self.cb_companion_format.addItems(["CSV", "LFP", "OPT"])
        self.cb_companion_format.setCurrentText("CSV")
        form_layout.addRow("Load File Format:", self.cb_companion_format)

        self.txt_companion_path = QLineEdit()
        self.txt_companion_path.setPlaceholderText("Auto-generated based on format and output directory")
        self.btn_browse_companion = QPushButton("Browse...")
        self.btn_browse_companion.setStyleSheet("background-color: #334155; color: white; padding: 4px 8px; border-radius: 4px;")
        self.btn_browse_companion.clicked.connect(self.browse_companion)

        companion_path_layout = QHBoxLayout()
        companion_path_layout.addWidget(self.txt_companion_path)
        companion_path_layout.addWidget(self.btn_browse_companion)
        form_layout.addRow("Companion Path:", companion_path_layout)

        layout.addLayout(form_layout)
        layout.addStretch()

        # Connect signals
        self.chk_companion.stateChanged.connect(self.toggle_companion_widgets)
        self.chk_ocr.stateChanged.connect(self.toggle_ocr_widgets)
        self.cb_companion_format.currentTextChanged.connect(self.update_default_companion_path)
        self.txt_out_dir.textChanged.connect(self.update_default_companion_path)

        # Actions
        buttons_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_export = QPushButton("Print & Export")
        self.btn_export.clicked.connect(self.validate_and_accept)
        self.btn_export.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px 12px; border-radius: 6px;")

        buttons_layout.addWidget(self.btn_cancel)
        buttons_layout.addWidget(self.btn_export)
        layout.addLayout(buttons_layout)

        self.toggle_companion_widgets()
        self.toggle_ocr_widgets()

    def toggle_companion_widgets(self):
        enabled = self.chk_companion.isChecked()
        self.cb_companion_format.setEnabled(enabled)
        self.txt_companion_path.setEnabled(enabled)
        self.btn_browse_companion.setEnabled(enabled)

    def toggle_ocr_widgets(self):
        enabled = self.chk_ocr.isChecked()
        self.cb_ocr_lang.setEnabled(enabled)

    def update_default_companion_path(self):
        if not self.txt_out_dir.text():
            return
        fmt = self.cb_companion_format.currentText().lower()
        default_path = os.path.join(self.txt_out_dir.text(), f"export_loadfile.{fmt}").replace("/", "\\")
        self.txt_companion_path.setText(default_path)

    def browse_dir(self):
        from PySide6.QtWidgets import QFileDialog
        dir_path = QFileDialog.getExistingDirectory(self, "Select Root Output Directory", self.txt_out_dir.text())
        if dir_path:
            self.txt_out_dir.setText(os.path.normpath(dir_path))
            self.update_default_companion_path()

    def browse_companion(self):
        from PySide6.QtWidgets import QFileDialog
        fmt = self.cb_companion_format.currentText().lower()
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Companion Load File", self.txt_companion_path.text(), f"Load Files (*.{fmt});;All Files (*.*)")
        if file_path:
            self.txt_companion_path.setText(os.path.normpath(file_path))

    def validate_and_accept(self):
        from PySide6.QtWidgets import QMessageBox
        if not self.txt_out_dir.text().strip() or not os.path.exists(self.txt_out_dir.text().strip()):
            QMessageBox.warning(self, "Validation Error", "Please select a valid root output directory.")
            return
        if self.chk_companion.isChecked() and not self.txt_companion_path.text().strip():
            QMessageBox.warning(self, "Validation Error", "Please specify a companion load file save path.")
            return
        self.accept()

    def get_data(self):
        return {
            "root_out_dir": self.txt_out_dir.text().strip(),
            "group_by_field": self.cb_group_by.currentText() if self.cb_group_by.currentText() else None,
            "generate_companion": self.chk_companion.isChecked(),
            "companion_format": self.cb_companion_format.currentText() if self.chk_companion.isChecked() else None,
            "companion_path": self.txt_companion_path.text().strip() if self.chk_companion.isChecked() else None,
            "generate_ocr": self.chk_ocr.isChecked(),
            "ocr_lang": self.cb_ocr_lang.currentText()
        }


class GapReportDialog(QDialog):
    def __init__(self, file_path, analysis_results, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
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
        from PySide6.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
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
            
    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
        self.reject()
        super().closeEvent(event)


class ManualDelimiterDialog(QDialog):
    def __init__(self, file_path, encoding, first_line, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QFormLayout
        import collections
        import csv
        import io

        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
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
        from PySide6.QtWidgets import QTableWidgetItem
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


class VolumeMergeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QTableWidget, QTableWidgetItem, QHeaderView, QFormLayout, QGroupBox, 
            QRadioButton, QButtonGroup, QProgressBar, QHBoxLayout, 
            QVBoxLayout, QPushButton, QLabel, QLineEdit, QComboBox, QCheckBox,
            QSizePolicy, QGridLayout
        )
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        self.setStyleSheet(GLOBAL_STYLE)
        self.setWindowTitle("Load File Merge & Volume Normalization")
        self.resize(1000, 550)
        apply_dark_titlebar(self)

        self.files_list = [] # list of dicts: {"path":, "volume_name":, "encoding":, "sep":, "quote":}
        
        # Main layout is horizontal to split Left Settings and Right Volumes
        main_layout = QHBoxLayout(self)

        # ================= LEFT SIDE: SETTINGS & CHOICES =================
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # Title
        title = QLabel("Load File Merge & Volume Normalization")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #38BDF8;")
        left_layout.addWidget(title)

        # 1. Field Mapping Config
        group_mapping = QGroupBox("Field Mapping")
        group_mapping.setStyleSheet("QGroupBox { font-weight: bold; }")
        map_layout = QFormLayout(group_mapping)

        self.cb_doc_id = QComboBox()
        self.cb_doc_id.setEditable(True)
        
        self.cb_text_path = QComboBox()
        self.cb_text_path.setEditable(True)
        self.cb_text_path.addItem("[Not Mapped]", "")
        
        self.cb_native_path = QComboBox()
        self.cb_native_path.setEditable(True)
        self.cb_native_path.addItem("[Not Mapped]", "")

        map_layout.addRow("Document ID Field (Required):", self.cb_doc_id)
        map_layout.addRow("Text File Path Field (Optional):", self.cb_text_path)
        map_layout.addRow("Native File Path Field (Optional):", self.cb_native_path)
        left_layout.addWidget(group_mapping)

        # 2. Duplicate Handling Config
        group_options = QGroupBox("Options")
        group_options.setStyleSheet("QGroupBox { font-weight: bold; }")
        options_layout = QFormLayout(group_options)

        self.cb_dup_mode = QComboBox()
        self.cb_dup_mode.addItems(["Strict Mode (Abort/Halt)", "First-In Wins", "Last-In Wins", "Suffix Append"])
        options_layout.addRow("Duplicate DocID Handling:", self.cb_dup_mode)
        left_layout.addWidget(group_options)

        # 3. Output Configuration (No log file prompt - generated next to output)
        group_output = QGroupBox("Output Settings")
        group_output.setStyleSheet("QGroupBox { font-weight: bold; }")
        output_layout = QFormLayout(group_output)

        self.txt_output_path = QLineEdit()
        self.btn_browse_output = QPushButton("Browse...")
        self.btn_browse_output.clicked.connect(self.browse_output)
        
        output_path_layout = QHBoxLayout()
        output_path_layout.addWidget(self.txt_output_path)
        output_path_layout.addWidget(self.btn_browse_output)
        output_layout.addRow("Consolidated Output File:", output_path_layout)
        left_layout.addWidget(group_output)

        left_layout.addStretch()

        # Progress elements
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setVisible(False)
        left_layout.addWidget(self.lbl_progress_status)
        left_layout.addWidget(self.progress_bar)

        # Left bottom buttons
        buttons_layout = QHBoxLayout()
        self.btn_help = QPushButton("Help")
        self.btn_help.setObjectName("BtnHelp")
        self.btn_help.clicked.connect(self.show_help)
        
        self.btn_run = QPushButton("Run Merge")
        self.btn_run.setStyleSheet("background-color: #15803D; color: white;")
        self.btn_run.clicked.connect(self.run_merge)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setStyleSheet("background-color: #475569; color: white;")
        self.btn_cancel.clicked.connect(self.reject)

        buttons_layout.addWidget(self.btn_help)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_run)
        buttons_layout.addWidget(self.btn_cancel)
        left_layout.addLayout(buttons_layout)

        main_layout.addWidget(left_widget, stretch=1)

        # ================= RIGHT SIDE: VOLUMES LIST =================
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        group_volumes = QGroupBox("Volume Load Files")
        group_volumes.setStyleSheet("QGroupBox { font-weight: bold; }")
        vol_box_layout = QVBoxLayout(group_volumes)
        
        self.table_volumes = QTableWidget(0, 2)
        self.table_volumes.setHorizontalHeaderLabels(["Volume Name (Editable)", "File Path"])
        self.table_volumes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_volumes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_volumes.setColumnWidth(0, 180)
        vol_box_layout.addWidget(self.table_volumes)

        vol_buttons = QHBoxLayout()
        self.btn_add_file = QPushButton("Add Volume File(s)...")
        self.btn_add_file.setStyleSheet("background-color: #1D4ED8; color: white;")
        self.btn_add_file.clicked.connect(self.add_volume_file)
        
        self.btn_remove_file = QPushButton("Remove Selected")
        self.btn_remove_file.setStyleSheet("background-color: #991B1B; color: white;")
        self.btn_remove_file.clicked.connect(self.remove_volume_file)
        
        vol_buttons.addWidget(self.btn_add_file)
        vol_buttons.addWidget(self.btn_remove_file)
        vol_buttons.addStretch()
        vol_box_layout.addLayout(vol_buttons)

        right_layout.addWidget(group_volumes)
        main_layout.addWidget(right_widget, stretch=1)

        # Connect cell change to update local volumes list
        self.table_volumes.cellChanged.connect(self.on_volume_name_changed)
    def on_volume_name_changed(self, row, col):
        if col == 0:
            item = self.table_volumes.item(row, col)
            if item and row < len(self.files_list):
                self.files_list[row]["volume_name"] = item.text().strip()

    def add_volume_file(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Volume Load Files", "", "Load Files (*.dat *.csv *.txt)")
        if not paths:
            return

        self.table_volumes.blockSignals(True)
        for path in paths:
            if any(f["path"] == path for f in self.files_list):
                continue
            
            # Suggest volume name from file name
            vol_name = os.path.splitext(os.path.basename(path))[0]
            
            file_info = {
                "path": path,
                "volume_name": vol_name,
                "encoding": None,
                "sep": None,
                "quote": None
            }
            self.files_list.append(file_info)
            
            row = self.table_volumes.rowCount()
            self.table_volumes.insertRow(row)
            
            item_vol = QTableWidgetItem(vol_name)
            item_path = QTableWidgetItem(path)
            item_path.setFlags(item_path.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_path.setToolTip(path)
            
            self.table_volumes.setItem(row, 0, item_vol)
            self.table_volumes.setItem(row, 1, item_path)
            
        self.table_volumes.blockSignals(False)

        # Update dynamic mapping dropdowns
        if self.files_list:
            self.update_mappings_and_dropdowns()
            
            # Automatically suggest output next to the first file if output path is empty
            if self.txt_output_path.text().strip() == "":
                parent_dir = os.path.dirname(self.files_list[0]["path"])
                self.txt_output_path.setText(os.path.join(parent_dir, "Consolidated_Master_LoadFile.dat"))

    def remove_volume_file(self):
        selected = self.table_volumes.currentRow()
        if selected != -1 and selected < len(self.files_list):
            self.files_list.pop(selected)
            self.table_volumes.removeRow(selected)
            self.update_mappings_and_dropdowns()

    def update_mappings_and_dropdowns(self):
        import csv
        all_headers = []
        
        # Keep track of current selections so we don't overwrite them
        current_doc_id = self.cb_doc_id.currentText()
        current_text_path = self.cb_text_path.currentText()
        current_native_path = self.cb_native_path.currentText()

        for file_info in self.files_list:
            f_path = file_info["path"]
            try:
                # Detect encoding and delimiters
                enc = file_info.get("encoding") or processor.get_encoding(f_path)
                sep = file_info.get("sep")
                qt = file_info.get("quote")
                if sep is None or qt is None:
                    d_sep, d_qt = processor.get_delimiters(f_path, enc)
                    sep = sep or d_sep
                    qt = qt or d_qt
                
                # Save detected parameters
                file_info["encoding"] = enc
                file_info["sep"] = sep
                file_info["quote"] = qt

                # Read headers
                with open(f_path, 'r', encoding=enc, errors='ignore') as f:
                    reader = csv.reader(f, delimiter=sep, quotechar=qt)
                    headers = next(reader)
                    headers = [h.lstrip('\ufeff').strip(qt + ' \t\r\n') for h in headers]
                    
                    for h in headers:
                        if h not in all_headers:
                            all_headers.append(h)
            except Exception:
                pass

        # Temporarily block signals of combo boxes to avoid noise
        self.cb_doc_id.blockSignals(True)
        self.cb_text_path.blockSignals(True)
        self.cb_native_path.blockSignals(True)

        self.cb_doc_id.clear()
        self.cb_text_path.clear()
        self.cb_native_path.clear()

        self.cb_text_path.addItem("[Not Mapped]", "")
        self.cb_native_path.addItem("[Not Mapped]", "")

        for h in all_headers:
            self.cb_doc_id.addItem(h)
            self.cb_text_path.addItem(h)
            self.cb_native_path.addItem(h)

        # Restore previous selection or auto-detect common fields
        if current_doc_id and self.cb_doc_id.findText(current_doc_id) != -1:
            self.cb_doc_id.setCurrentText(current_doc_id)
        else:
            h_lower = [h.lower() for h in all_headers]
            for common in ["control number", "controlno", "begbates", "docid", "documentid"]:
                if common in h_lower:
                    self.cb_doc_id.setCurrentIndex(h_lower.index(common))
                    break

        if current_text_path and self.cb_text_path.findText(current_text_path) != -1:
            self.cb_text_path.setCurrentText(current_text_path)
        else:
            h_lower = [h.lower() for h in all_headers]
            for common in ["extracted text", "textpath", "text_path", "text link", "textlink"]:
                if common in h_lower:
                    self.cb_text_path.setCurrentIndex(h_lower.index(common) + 1)
                    break

        if current_native_path and self.cb_native_path.findText(current_native_path) != -1:
            self.cb_native_path.setCurrentText(current_native_path)
        else:
            h_lower = [h.lower() for h in all_headers]
            for common in ["nativepath", "native path", "filepath", "file_path", "file link", "filelink"]:
                if common in h_lower:
                    self.cb_native_path.setCurrentIndex(h_lower.index(common) + 1)
                    break

        self.cb_doc_id.blockSignals(False)
        self.cb_text_path.blockSignals(False)
        self.cb_native_path.blockSignals(False)

    def browse_output(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Consolidated Load File", self.txt_output_path.text(), "DAT Load Files (*.dat);;CSV Files (*.csv);;All Files (*.*)")
        if path:
            self.txt_output_path.setText(path)

    def show_help(self):
        help_dialog = QDialog(self)
        help_dialog.setWindowTitle("Merge & Volume Normalization - Help")
        help_dialog.setWindowFlags(help_dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        help_dialog.setStyleSheet(GLOBAL_STYLE)
        help_dialog.resize(550, 480)
        apply_dark_titlebar(help_dialog)
        
        h_layout = QVBoxLayout(help_dialog)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setHtml("""
        <h3 style="color: #38BDF8; margin-top: 0px;">Load File Merge &amp; Volume Normalization Help</h3>
        <p>This utility enables you to consolidate multiple Relativity load files (representing distinct production volumes) into a single master load file with uniform delimiters and standardized relative paths.</p>
        
        <b style="color: #38BDF8;">Key Assumptions &amp; Standards:</b>
        <ul>
          <li>All volume load files should be delimited text files (such as .dat, .csv, or .txt).</li>
          <li>A Document ID field is strictly required to unique-identify and align records.</li>
          <li>Smart Path Normalization cleans absolute routes (like <code>C:\\Data\\ACMEPROD001\\...</code>) or relative paths and standardizes them into <code>.\\[VolumeName]\\[RelativePath]</code>.</li>
        </ul>

        <b style="color: #38BDF8;">Two-Phase Pre-Flight Validation:</b>
        <ol>
          <li><b>Phase 1: Validation Pass (Dry Run):</b>
            <ul>
              <li>Checks headers of each volume file for required mappings (DocID, Text Path, and Native Path). If missing, the process aborts.</li>
            </ul>
          </li>
          <li><b>Phase 2: Consolidating and Merging:</b>
            <ul>
              <li>Aggregates fields, standardizes paths, and outputs records using uniform delimiters (ASCII 20/254 delimiters for .dat or commas/quotes for .csv).</li>
            </ul>
          </li>
        </ol>

        <b style="color: #38BDF8;">Duplicate DocID Handling:</b>
        <ul>
          <li><b>Strict Mode:</b> Logs any duplicates to the Audit CSV and halts the merge immediately.</li>
          <li><b>First-In Wins:</b> Keeps the first record encountered for a duplicate DocID and ignores subsequent ones.</li>
          <li><b>Last-In Wins:</b> Overwrites the existing record with the last one encountered for that DocID.</li>
          <li><b>Suffix Append:</b> Renames duplicate records by appending an incremental suffix (e.g. <code>_001</code>, <code>_002</code>).</li>
        </ul>

        <b style="color: #38BDF8;">Error &amp; Audit Logging:</b>
        <p>A dedicated audit CSV is created automatically next to your output file named <code>[OutputFileName]_Merge_Audit_Log.csv</code>, and contains: <i>Error Type, Volume File Name, Volume File Path,</i> and <i>Error Description</i>.</p>
        """)
        
        h_layout.addWidget(help_text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(help_dialog.accept)
        h_layout.addWidget(close_btn)
        
        help_dialog.exec()

    def run_merge(self):
        import os
        # Validate inputs
        if not self.files_list:
            show_dark_message(self, "Validation Error", "Please add at least one volume load file.", QMessageBox.Icon.Warning)
            return

        doc_id = self.cb_doc_id.currentText().strip()
        if not doc_id:
            show_dark_message(self, "Validation Error", "Document ID Field must be mapped.", QMessageBox.Icon.Warning)
            return

        out_path = self.txt_output_path.text().strip()
        if not out_path:
            show_dark_message(self, "Validation Error", "Please select a Consolidated Output File path.", QMessageBox.Icon.Warning)
            return

        # Auto-compute audit log path next to output file
        audit_path = os.path.splitext(out_path)[0] + "_Merge_Audit_Log.csv"

        text_path = self.cb_text_path.currentText().strip()
        if text_path == "[Not Mapped]":
            text_path = ""
        native_path = self.cb_native_path.currentText().strip()
        if native_path == "[Not Mapped]":
            native_path = ""

        # Check duplicate options mapping
        dup_mapping = {
            "Strict Mode (Abort/Halt)": "Strict",
            "First-In Wins": "First-In Wins",
            "Last-In Wins": "Last-In Wins",
            "Suffix Append": "Suffix Append"
        }
        dup_mode = dup_mapping.get(self.cb_dup_mode.currentText(), "Strict")

        # Disable buttons
        self.btn_run.setEnabled(False)
        self.btn_add_file.setEnabled(False)
        self.btn_remove_file.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.lbl_progress_status.setVisible(True)
        self.lbl_progress_status.setText("Initializing Merge...")
        
        self.worker = VolumeMergeWorker(
            files=self.files_list,
            doc_id_field=doc_id,
            text_path_field=text_path,
            native_path_field=native_path,
            dup_mode=dup_mode,
            output_path=out_path,
            audit_path=audit_path,
            parent=self
        )
        
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_worker_progress(self, message, phase, value):
        self.lbl_progress_status.setText(message)
        self.progress_bar.setValue(value)

    def on_worker_error(self, err_msg):
        self.btn_run.setEnabled(True)
        self.btn_add_file.setEnabled(True)
        self.btn_remove_file.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress_status.setVisible(False)
        
        show_dark_message(self, "Merge Error", err_msg, QMessageBox.Icon.Critical)

    def on_worker_finished(self, total_vols, unique_recs, errors_caught, audit_path, output_path):
        self.progress_bar.setVisible(False)
        self.lbl_progress_status.setVisible(False)
        self.accept()
        
        self.merged_output_path = output_path
        
        # Display completion summary
        summary_dialog = QDialog(self.parent())
        summary_dialog.setWindowTitle("Merge Complete")
        summary_dialog.setWindowFlags(summary_dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        summary_dialog.setStyleSheet(GLOBAL_STYLE)
        summary_dialog.resize(450, 250)
        apply_dark_titlebar(summary_dialog)
        
        s_layout = QVBoxLayout(summary_dialog)
        
        lbl_info = QLabel(
            f"<b>Consolidation Summary:</b><br><br>"
            f"Total Volumes Merged: {total_vols}<br>"
            f"Unique Records Consolidated: {unique_recs}<br>"
            f"Errors / Warnings Caught: {errors_caught}<br><br>"
            f"Output Load File: {os.path.basename(output_path)}"
        )
        lbl_info.setStyleSheet("font-size: 14px;")
        s_layout.addWidget(lbl_info)
        
        btn_layout = QHBoxLayout()
        btn_audit = QPushButton("Open Audit Log CSV")
        btn_audit.setStyleSheet("background-color: #8B5CF6; color: white;")
        
        def open_csv():
            import subprocess
            try:
                if os.name == 'nt':
                    os.startfile(audit_path)
                else:
                    subprocess.call(('xdg-open', audit_path))
            except Exception as e:
                show_dark_message(summary_dialog, "Error", f"Could not open audit file: {str(e)}")
                
        btn_audit.clicked.connect(open_csv)
        
        btn_close = QPushButton("OK")
        btn_close.clicked.connect(summary_dialog.accept)
        
        btn_layout.addWidget(btn_audit)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        s_layout.addLayout(btn_layout)
        
        summary_dialog.exec()


class ImageVolumeMergeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Image Load File Merge & Path Normalization")
        self.setStyleSheet(GLOBAL_STYLE)
        self.resize(1000, 600)
        apply_dark_titlebar(self)
        
        self.files_list = []  # list of dicts: {"path":, "volume_name":}
        self.merged_output_path = None
        
        main_layout = QHBoxLayout(self)
        
        # Left Panel (Settings)
        left_panel = QVBoxLayout()
        
        # Load File Type Group
        type_group = QGroupBox("Load File Type")
        type_layout = QVBoxLayout(type_group)
        self.cb_file_type = QComboBox()
        self.cb_file_type.addItems(["OPT (Opticon)", "LFP (IPRO)"])
        type_layout.addWidget(self.cb_file_type)
        left_panel.addWidget(type_group)
        
        # Options Group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        self.cb_dup_handling = QComboBox()
        self.cb_dup_handling.addItems([
            "Strict Mode (Abort/Halt)",
            "First-In Wins",
            "Last-In Wins",
            "Suffix Append"
        ])
        options_layout.addWidget(QLabel("Duplicate Bates handling:"))
        options_layout.addWidget(self.cb_dup_handling)
        left_panel.addWidget(options_group)
        
        # Output Destination Group
        dest_group = QGroupBox("Output Settings")
        dest_layout = QVBoxLayout(dest_group)
        self.txt_output_path = QLineEdit()
        self.txt_output_path.setReadOnly(True)
        self.txt_output_path.setPlaceholderText("Specify consolidated output file...")
        self.btn_browse_output = QPushButton("Browse...")
        self.btn_browse_output.clicked.connect(self.browse_output)
        
        dest_layout.addWidget(QLabel("Consolidated Output File:"))
        dest_layout.addWidget(self.txt_output_path)
        dest_layout.addWidget(self.btn_browse_output)
        left_panel.addWidget(dest_group)
        
        # Action Buttons
        btn_action_layout = QHBoxLayout()
        self.btn_help = QPushButton("Help")
        self.btn_help.setStyleSheet("background-color: #334155; color: white;")
        self.btn_help.clicked.connect(self.show_help)
        self.btn_run = QPushButton("Run Merge")
        self.btn_run.setStyleSheet("background-color: #15803D; color: white;")
        self.btn_run.clicked.connect(self.run_merge)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        btn_action_layout.addWidget(self.btn_help)
        btn_action_layout.addStretch()
        btn_action_layout.addWidget(self.btn_run)
        btn_action_layout.addWidget(self.btn_cancel)
        left_panel.addLayout(btn_action_layout)
        
        # Progress Indicators
        self.lbl_progress_status = QLabel("")
        self.lbl_progress_status.setVisible(False)
        left_panel.addWidget(self.lbl_progress_status)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_panel.addWidget(self.progress_bar)
        
        main_layout.addLayout(left_panel, 2)
        
        # Right Panel (Selected Files Table)
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Selected Volume Load Files:"))
        
        self.table_volumes = QTableWidget(0, 2)
        self.table_volumes.setHorizontalHeaderLabels(["Volume Name (Editable)", "File Path"])
        self.table_volumes.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_volumes.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_volumes.setColumnWidth(0, 180)
        self.table_volumes.cellChanged.connect(self.on_volume_name_changed)
        right_panel.addWidget(self.table_volumes)
        
        right_btn_layout = QHBoxLayout()
        self.btn_add_file = QPushButton("Add Volume File(s)...")
        self.btn_add_file.setStyleSheet("background-color: #2563EB; color: white;")
        self.btn_add_file.clicked.connect(self.add_volume_files)
        
        self.btn_remove_file = QPushButton("Remove Selected")
        self.btn_remove_file.setStyleSheet("background-color: #DC2626; color: white;")
        self.btn_remove_file.clicked.connect(self.remove_selected_files)
        
        right_btn_layout.addWidget(self.btn_add_file)
        right_btn_layout.addWidget(self.btn_remove_file)
        right_panel.addLayout(right_btn_layout)
        
        main_layout.addLayout(right_panel, 3)

    def show_help(self):
        help_text = (
            "<b>Image Load File Merge & Path Normalization Tool Help</b><br><br>"
            "This tool consolidates multiple volume-level image load files (OPT or LFP) "
            "into a single consolidated master load file, automatically normalizing image paths "
            "and resolving duplicate Bates keys.<br><br>"
            "<b>1. Select Load File Type:</b> Choose whether to consolidate OPT or LFP files.<br>"
            "<b>2. Add Volume Files:</b> Click 'Add Volume File(s)...' to load the files. The tool "
            "automatically extracts the Volume Name from the filename. You can edit this name in the table if needed.<br>"
            "<b>3. Path Normalization:</b> All image file paths will be cleaned up and normalized relative to the "
            "respective volume directory (e.g. <code>.\\ACMEPROD001\\IMAGES\\0001\\img01.tif</code>).<br>"
            "<b>4. Duplicate Bates handling:</b> Choose how to resolve duplicate page Bates keys across volumes:<br>"
            " - <i>Strict Mode</i>: Aborts the merge and logs details to the CSV audit log.<br>"
            " - <i>First-In / Last-In Wins</i>: Keeps the first or last instance respectively.<br>"
            " - <i>Suffix Append</i>: Appends the volume name (e.g., <code>_ACMEPROD001</code>) to duplicate page keys.<br>"
            "<b>5. Output Settings:</b> Choose the target location for the consolidated load file. "
            "The CSV audit log will be written next to the output file automatically."
        )
        QMessageBox.information(self, "Tool Help", help_text)

    def browse_output(self):
        file_type = "opt" if "OPT" in self.cb_file_type.currentText() else "lfp"
        path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Consolidated Image Load File", 
            "", 
            f"Image Load Files (*.{file_type});;All Files (*.*)"
        )
        if path:
            self.txt_output_path.setText(path)

    def add_volume_files(self):
        file_type = "opt" if "OPT" in self.cb_file_type.currentText() else "lfp"
        paths, _ = QFileDialog.getOpenFileNames(
            self, 
            "Select Volume Image Load Files", 
            "", 
            f"Image Load Files (*.{file_type});;All Files (*.*)"
        )
        if not paths:
            return
            
        self.table_volumes.blockSignals(True)
        for path in paths:
            if any(f["path"] == path for f in self.files_list):
                continue
                
            vol_name = os.path.splitext(os.path.basename(path))[0]
            self.files_list.append({"path": path, "volume_name": vol_name})
            
            row = self.table_volumes.rowCount()
            self.table_volumes.insertRow(row)
            
            item_vol = QTableWidgetItem(vol_name)
            item_path = QTableWidgetItem(path)
            item_path.setFlags(item_path.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_path.setToolTip(path)
            
            self.table_volumes.setItem(row, 0, item_vol)
            self.table_volumes.setItem(row, 1, item_path)
            
        self.table_volumes.blockSignals(False)

    def remove_selected_files(self):
        selected_rows = sorted(set(index.row() for index in self.table_volumes.selectedIndexes()), reverse=True)
        if not selected_rows:
            return
            
        self.table_volumes.blockSignals(True)
        for row in selected_rows:
            if row < len(self.files_list):
                self.files_list.pop(row)
            self.table_volumes.removeRow(row)
        self.table_volumes.blockSignals(False)

    def on_volume_name_changed(self, row, column):
        if column == 0 and row < len(self.files_list):
            item = self.table_volumes.item(row, column)
            if item:
                new_vol = item.text().strip()
                if new_vol:
                    self.files_list[row]["volume_name"] = new_vol

    def run_merge(self):
        if not self.files_list:
            show_dark_message(self, "Validation Error", "Please select at least one volume load file.", QMessageBox.Icon.Warning)
            return
            
        out_path = self.txt_output_path.text().strip()
        if not out_path:
            show_dark_message(self, "Validation Error", "Please select the consolidated output file location.", QMessageBox.Icon.Warning)
            return
            
        # Set up audit log path automatically next to the output load file
        base_no_ext = os.path.splitext(out_path)[0]
        audit_path = f"{base_no_ext}_Image_Merge_Audit_Log.csv"
        
        file_type = "OPT" if "OPT" in self.cb_file_type.currentText() else "LFP"
        dup_text = self.cb_dup_handling.currentText()
        if "Strict" in dup_text:
            dup_mode = "Strict"
        elif "First" in dup_text:
            dup_mode = "First-In Wins"
        elif "Last" in dup_text:
            dup_mode = "Last-In Wins"
        else:
            dup_mode = "Suffix Append"
            
        # Disable inputs
        self.btn_run.setEnabled(False)
        self.btn_add_file.setEnabled(False)
        self.btn_remove_file.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.lbl_progress_status.setVisible(True)
        self.lbl_progress_status.setText("Initializing Image Merge...")
        
        from pyside_workers import ImageVolumeMergeWorker
        
        self.worker = ImageVolumeMergeWorker(
            files=self.files_list,
            file_type=file_type,
            dup_mode=dup_mode,
            output_path=out_path,
            audit_path=audit_path,
            parent=self
        )
        
        self.worker.progress.connect(self.on_worker_progress)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.error.connect(self.on_worker_error)
        self.worker.start()

    def on_worker_progress(self, message, phase, value):
        self.lbl_progress_status.setText(message)
        self.progress_bar.setValue(value)

    def on_worker_error(self, err_msg):
        self.btn_run.setEnabled(True)
        self.btn_add_file.setEnabled(True)
        self.btn_remove_file.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress_status.setVisible(False)
        
        show_dark_message(self, "Merge Error", err_msg, QMessageBox.Icon.Critical)

    def on_worker_finished(self, total_vols, unique_recs, errors_caught, audit_path, output_path):
        self.progress_bar.setVisible(False)
        self.lbl_progress_status.setVisible(False)
        self.accept()
        
        self.merged_output_path = output_path
        
        # Display completion summary
        summary_dialog = QDialog(self.parent())
        summary_dialog.setWindowTitle("Image Merge Complete")
        summary_dialog.setWindowFlags(summary_dialog.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint | Qt.WindowType.WindowCloseButtonHint)
        summary_dialog.setStyleSheet(GLOBAL_STYLE)
        summary_dialog.resize(450, 250)
        apply_dark_titlebar(summary_dialog)
        
        s_layout = QVBoxLayout(summary_dialog)
        
        lbl_info = QLabel(
            f"<b>Consolidation Summary:</b><br><br>"
            f"Total Volumes Merged: {total_vols}<br>"
            f"Unique Records Consolidated: {unique_recs}<br>"
            f"Errors / Warnings Caught: {errors_caught}<br><br>"
            f"Output Load File: {os.path.basename(output_path)}"
        )
        lbl_info.setStyleSheet("font-size: 14px;")
        s_layout.addWidget(lbl_info)
        
        btn_layout = QHBoxLayout()
        btn_audit = QPushButton("Open Audit Log CSV")
        btn_audit.setStyleSheet("background-color: #8B5CF6; color: white;")
        
        def open_csv():
            import subprocess
            try:
                if os.name == 'nt':
                    os.startfile(audit_path)
                else:
                    subprocess.call(('xdg-open', audit_path))
            except Exception as e:
                show_dark_message(summary_dialog, "Error", f"Could not open audit file: {str(e)}")
                
        btn_audit.clicked.connect(open_csv)
        
        btn_close = QPushButton("OK")
        btn_close.clicked.connect(summary_dialog.accept)
        
        btn_layout.addWidget(btn_audit)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        s_layout.addLayout(btn_layout)
        
        summary_dialog.exec()


class DataSplitDialog(QDialog):
    def __init__(self, file_path, encoding, sep, quote, columns, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Split Data Load File")
        self.setStyleSheet(GLOBAL_STYLE)
        self.resize(500, 450)
        apply_dark_titlebar(self)
        
        self.file_path = file_path
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.columns = columns
        
        layout = QVBoxLayout(self)
        
        # Root Volume Name
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Root Volume Name:"))
        self.txt_root_vol = QLineEdit()
        self.txt_root_vol.setPlaceholderText("e.g. ACMEPROD")
        vol_name = os.path.splitext(os.path.basename(file_path))[0]
        self.txt_root_vol.setText(vol_name)
        vol_layout.addWidget(self.txt_root_vol)
        layout.addLayout(vol_layout)
        
        # Destination Directory
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(QLabel("Destination Directory:"))
        self.txt_dest_dir = QLineEdit()
        self.txt_dest_dir.setReadOnly(True)
        self.txt_dest_dir.setText(os.path.dirname(file_path))
        self.btn_browse_dest = QPushButton("Browse...")
        self.btn_browse_dest.clicked.connect(self.browse_dest)
        dest_layout.addWidget(self.txt_dest_dir)
        dest_layout.addWidget(self.btn_browse_dest)
        layout.addLayout(dest_layout)
        
        # Output Format
        fmt_layout = QHBoxLayout()
        fmt_layout.addWidget(QLabel("Output File Format:"))
        self.cb_format = QComboBox()
        self.cb_format.addItems(["DAT", "CSV"])
        if file_path.lower().endswith(".csv"):
            self.cb_format.setCurrentText("CSV")
        fmt_layout.addWidget(self.cb_format)
        layout.addLayout(fmt_layout)
        
        # Splitting Criteria Group
        criteria_group = QGroupBox("Splitting Criteria")
        c_layout = QVBoxLayout(criteria_group)
        
        self.cb_split_type = QComboBox()
        self.cb_split_type.addItems(["Line Count", "File Size", "Field Value"])
        self.cb_split_type.currentTextChanged.connect(self.on_split_type_changed)
        c_layout.addWidget(QLabel("Split by:"))
        c_layout.addWidget(self.cb_split_type)
        
        # Line count layout
        self.line_widget = QWidget()
        l_lay = QHBoxLayout(self.line_widget)
        l_lay.setContentsMargins(0, 0, 0, 0)
        self.spin_lines = QSpinBox()
        self.spin_lines.setRange(1, 1000000)
        self.spin_lines.setValue(10000)
        l_lay.addWidget(QLabel("Maximum records per file:"))
        l_lay.addWidget(self.spin_lines)
        c_layout.addWidget(self.line_widget)
        
        # File size layout
        self.size_widget = QWidget()
        s_lay = QHBoxLayout(self.size_widget)
        s_lay.setContentsMargins(0, 0, 0, 0)
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 10000)
        self.spin_size.setValue(50)
        s_lay.addWidget(QLabel("Maximum size per file (MB):"))
        s_lay.addWidget(self.spin_size)
        c_layout.addWidget(self.size_widget)
        self.size_widget.hide()
        
        # Field value layout
        self.field_widget = QWidget()
        f_lay = QHBoxLayout(self.field_widget)
        f_lay.setContentsMargins(0, 0, 0, 0)
        self.cb_field = QComboBox()
        self.cb_field.addItems(self.columns)
        f_lay.addWidget(QLabel("Group / split by field:"))
        f_lay.addWidget(self.cb_field)
        c_layout.addWidget(self.field_widget)
        self.field_widget.hide()
        
        layout.addWidget(criteria_group)
        
        # Progress Indicators
        self.lbl_progress = QLabel("")
        self.lbl_progress.setVisible(False)
        layout.addWidget(self.lbl_progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run Split")
        self.btn_run.setStyleSheet("background-color: #15803D; color: white;")
        self.btn_run.clicked.connect(self.run_split)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def browse_dest(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.txt_dest_dir.text())
        if dir_path:
            self.txt_dest_dir.setText(dir_path)

    def on_split_type_changed(self, text):
        self.line_widget.setVisible(text == "Line Count")
        self.size_widget.setVisible(text == "File Size")
        self.field_widget.setVisible(text == "Field Value")

    def run_split(self):
        root_vol = self.txt_root_vol.text().strip()
        if not root_vol:
            show_dark_message(self, "Validation Error", "Please specify a Root Volume Name.", QMessageBox.Icon.Warning)
            return
            
        dest_dir = self.txt_dest_dir.text().strip()
        if not dest_dir or not os.path.exists(dest_dir):
            show_dark_message(self, "Validation Error", "Please select a valid destination directory.", QMessageBox.Icon.Warning)
            return
            
        split_type = self.cb_split_type.currentText()
        if split_type == "Line Count":
            split_val = self.spin_lines.value()
            field_name = None
        elif split_type == "File Size":
            split_val = self.spin_size.value()
            field_name = None
        else:
            split_val = 0
            field_name = self.cb_field.currentText()
            if not field_name:
                show_dark_message(self, "Validation Error", "Please select a field to split by.", QMessageBox.Icon.Warning)
                return
                
        out_format = self.cb_format.currentText()
        
        # Disable controls
        self.btn_run.setEnabled(False)
        self.btn_browse_dest.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.lbl_progress.setVisible(True)
        self.lbl_progress.setText("Initializing Split...")
        
        from pyside_workers import DataSplitWorker
        
        self.worker = DataSplitWorker(
            file_path=self.file_path,
            encoding=self.encoding,
            sep=self.sep,
            quote=self.quote,
            root_vol_name=root_vol,
            dest_dir=dest_dir,
            split_type=split_type,
            split_val=split_val,
            out_format=out_format,
            field_name=field_name,
            parent=self
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, msg, val):
        self.lbl_progress.setText(msg)
        self.progress_bar.setValue(val)

    def on_error(self, err):
        self.btn_run.setEnabled(True)
        self.btn_browse_dest.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress.setVisible(False)
        show_dark_message(self, "Split Error", err, QMessageBox.Icon.Critical)

    def on_finished(self, total_splits, split_files_info, summary_report_path):
        self.progress_bar.setVisible(False)
        self.lbl_progress.setVisible(False)
        self.accept()
        
        summary = (
            f"<b>Data File Split Completed Successfully!</b><br><br>"
            f"Total Splits Created: {total_splits}<br><br>"
            f"Summary Report: {os.path.basename(summary_report_path)}"
        )
        
        summary_dialog = QDialog(self.parent())
        summary_dialog.setWindowTitle("Split Complete")
        summary_dialog.setStyleSheet(GLOBAL_STYLE)
        summary_dialog.resize(400, 220)
        apply_dark_titlebar(summary_dialog)
        
        s_layout = QVBoxLayout(summary_dialog)
        lbl_info = QLabel(summary)
        lbl_info.setStyleSheet("font-size: 13px;")
        s_layout.addWidget(lbl_info)
        
        btn_layout = QHBoxLayout()
        btn_report = QPushButton("Open Summary Report")
        btn_report.setStyleSheet("background-color: #8B5CF6; color: white;")
        
        def open_report():
            import subprocess
            try:
                if os.name == 'nt':
                    os.startfile(summary_report_path)
                else:
                    subprocess.call(('xdg-open', summary_report_path))
            except Exception as e:
                show_dark_message(summary_dialog, "Error", f"Could not open report: {str(e)}")
                
        btn_report.clicked.connect(open_report)
        btn_close = QPushButton("OK")
        btn_close.clicked.connect(summary_dialog.accept)
        
        btn_layout.addWidget(btn_report)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        s_layout.addLayout(btn_layout)
        summary_dialog.exec()


class ImageSplitDialog(QDialog):
    def __init__(self, file_path, file_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Split Image Load File")
        self.setStyleSheet(GLOBAL_STYLE)
        self.resize(500, 420)
        apply_dark_titlebar(self)
        
        self.file_path = file_path
        self.file_type = file_type  # "OPT" or "LFP"
        
        layout = QVBoxLayout(self)
        
        # Root Volume Name
        vol_layout = QHBoxLayout()
        vol_layout.addWidget(QLabel("Root Volume Name:"))
        self.txt_root_vol = QLineEdit()
        self.txt_root_vol.setPlaceholderText("e.g. ACMEPROD_IMG")
        vol_name = os.path.splitext(os.path.basename(file_path))[0]
        self.txt_root_vol.setText(vol_name)
        vol_layout.addWidget(self.txt_root_vol)
        layout.addLayout(vol_layout)
        
        # Destination Directory
        dest_layout = QHBoxLayout()
        dest_layout.addWidget(QLabel("Destination Directory:"))
        self.txt_dest_dir = QLineEdit()
        self.txt_dest_dir.setReadOnly(True)
        self.txt_dest_dir.setText(os.path.dirname(file_path))
        self.btn_browse_dest = QPushButton("Browse...")
        self.btn_browse_dest.clicked.connect(self.browse_dest)
        dest_layout.addWidget(self.txt_dest_dir)
        dest_layout.addWidget(self.btn_browse_dest)
        layout.addLayout(dest_layout)
        
        # Splitting Criteria Group
        criteria_group = QGroupBox("Splitting Criteria")
        c_layout = QVBoxLayout(criteria_group)
        
        self.cb_split_type = QComboBox()
        self.cb_split_type.addItems(["Line Count", "File Size", "Document Boundaries", "Volume"])
        self.cb_split_type.currentTextChanged.connect(self.on_split_type_changed)
        c_layout.addWidget(QLabel("Split by:"))
        c_layout.addWidget(self.cb_split_type)
        
        # Line count layout
        self.line_widget = QWidget()
        l_lay = QHBoxLayout(self.line_widget)
        l_lay.setContentsMargins(0, 0, 0, 0)
        self.spin_lines = QSpinBox()
        self.spin_lines.setRange(1, 1000000)
        self.spin_lines.setValue(10000)
        l_lay.addWidget(QLabel("Maximum records/pages per file:"))
        l_lay.addWidget(self.spin_lines)
        c_layout.addWidget(self.line_widget)
        
        # File size layout
        self.size_widget = QWidget()
        s_lay = QHBoxLayout(self.size_widget)
        s_lay.setContentsMargins(0, 0, 0, 0)
        self.spin_size = QSpinBox()
        self.spin_size.setRange(1, 10000)
        self.spin_size.setValue(50)
        s_lay.addWidget(QLabel("Maximum size per file (MB):"))
        s_lay.addWidget(self.spin_size)
        c_layout.addWidget(self.size_widget)
        self.size_widget.hide()
        
        # Document boundaries layout
        self.doc_widget = QWidget()
        d_lay = QHBoxLayout(self.doc_widget)
        d_lay.setContentsMargins(0, 0, 0, 0)
        self.spin_docs = QSpinBox()
        self.spin_docs.setRange(1, 500000)
        self.spin_docs.setValue(5000)
        d_lay.addWidget(QLabel("Maximum documents per file:"))
        d_lay.addWidget(self.spin_docs)
        c_layout.addWidget(self.doc_widget)
        self.doc_widget.hide()
        
        layout.addWidget(criteria_group)
        
        # Progress Indicators
        self.lbl_progress = QLabel("")
        self.lbl_progress.setVisible(False)
        layout.addWidget(self.lbl_progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run Split")
        self.btn_run.setStyleSheet("background-color: #15803D; color: white;")
        self.btn_run.clicked.connect(self.run_split)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def browse_dest(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.txt_dest_dir.text())
        if dir_path:
            self.txt_dest_dir.setText(dir_path)

    def on_split_type_changed(self, text):
        self.line_widget.setVisible(text == "Line Count")
        self.size_widget.setVisible(text == "File Size")
        self.doc_widget.setVisible(text == "Document Boundaries")

    def run_split(self):
        root_vol = self.txt_root_vol.text().strip()
        if not root_vol:
            show_dark_message(self, "Validation Error", "Please specify a Root Volume Name.", QMessageBox.Icon.Warning)
            return
            
        dest_dir = self.txt_dest_dir.text().strip()
        if not dest_dir or not os.path.exists(dest_dir):
            show_dark_message(self, "Validation Error", "Please select a valid destination directory.", QMessageBox.Icon.Warning)
            return
            
        split_type = self.cb_split_type.currentText()
        if split_type == "Line Count":
            split_val = self.spin_lines.value()
        elif split_type == "File Size":
            split_val = self.spin_size.value()
        elif split_type == "Document Boundaries":
            split_val = self.spin_docs.value()
        else:
            split_val = 0
            
        # Disable controls
        self.btn_run.setEnabled(False)
        self.btn_browse_dest.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.lbl_progress.setVisible(True)
        self.lbl_progress.setText("Initializing Split...")
        
        from pyside_workers import ImageSplitWorker
        
        self.worker = ImageSplitWorker(
            file_path=self.file_path,
            file_type=self.file_type,
            root_vol_name=root_vol,
            dest_dir=dest_dir,
            split_type=split_type,
            split_val=split_val,
            parent=self
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, msg, val):
        self.lbl_progress.setText(msg)
        self.progress_bar.setValue(val)

    def on_error(self, err):
        self.btn_run.setEnabled(True)
        self.btn_browse_dest.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress.setVisible(False)
        show_dark_message(self, "Split Error", err, QMessageBox.Icon.Critical)

    def on_finished(self, total_splits, split_files_info, summary_report_path):
        self.progress_bar.setVisible(False)
        self.lbl_progress.setVisible(False)
        self.accept()
        
        summary = (
            f"<b>Image Load File Split Completed Successfully!</b><br><br>"
            f"Total Splits Created: {total_splits}<br><br>"
            f"Summary Report: {os.path.basename(summary_report_path)}"
        )
        
        summary_dialog = QDialog(self.parent())
        summary_dialog.setWindowTitle("Split Complete")
        summary_dialog.setStyleSheet(GLOBAL_STYLE)
        summary_dialog.resize(400, 220)
        apply_dark_titlebar(summary_dialog)
        
        s_layout = QVBoxLayout(summary_dialog)
        lbl_info = QLabel(summary)
        lbl_info.setStyleSheet("font-size: 13px;")
        s_layout.addWidget(lbl_info)
        
        btn_layout = QHBoxLayout()
        btn_report = QPushButton("Open Summary Report")
        btn_report.setStyleSheet("background-color: #8B5CF6; color: white;")
        
        def open_report():
            import subprocess
            try:
                if os.name == 'nt':
                    os.startfile(summary_report_path)
                else:
                    subprocess.call(('xdg-open', summary_report_path))
            except Exception as e:
                show_dark_message(summary_dialog, "Error", f"Could not open report: {str(e)}")
                
        btn_report.clicked.connect(open_report)
        btn_close = QPushButton("OK")
        btn_close.clicked.connect(summary_dialog.accept)
        
        btn_layout.addWidget(btn_report)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        s_layout.addLayout(btn_layout)
        summary_dialog.exec()


class TiffRemediationDialog(QDialog):
    def __init__(self, load_file_path, file_type, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bad TIFF Detection & Conversion")
        self.setStyleSheet(GLOBAL_STYLE)
        self.resize(500, 380)
        apply_dark_titlebar(self)
        
        self.load_file_path = load_file_path
        self.file_type = file_type
        
        layout = QVBoxLayout(self)
        
        # Load file path display
        layout.addWidget(QLabel("Target Load File:"))
        self.lbl_load_file = QLabel(os.path.basename(load_file_path))
        self.lbl_load_file.setStyleSheet("font-weight: bold; color: #60A5FA; background-color: #1E293B; padding: 6px; border-radius: 4px;")
        layout.addWidget(self.lbl_load_file)
        
        # Target volume directory selection
        layout.addWidget(QLabel("Top-Level Volume Image Directory to Scan:"))
        dir_layout = QHBoxLayout()
        self.txt_scan_dir = QLineEdit()
        self.txt_scan_dir.setReadOnly(True)
        self.txt_scan_dir.setPlaceholderText("Select directory...")
        self.btn_browse_scan = QPushButton("Browse...")
        self.btn_browse_scan.clicked.connect(self.browse_scan_dir)
        dir_layout.addWidget(self.txt_scan_dir)
        dir_layout.addWidget(self.btn_browse_scan)
        layout.addLayout(dir_layout)
        
        # Backup Preferences Checkbox
        self.chk_backup = QCheckBox("Create original TIFF backups before conversion (Recommended)")
        self.chk_backup.setChecked(True)
        self.chk_backup.setEnabled(False) # Always forced true for safety
        layout.addWidget(self.chk_backup)
        
        # Progress Indicators
        self.lbl_progress = QLabel("")
        self.lbl_progress.setVisible(False)
        layout.addWidget(self.lbl_progress)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Run Detection & Conversion")
        self.btn_run.setStyleSheet("background-color: #15803D; color: white;")
        self.btn_run.clicked.connect(self.run_remediation)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def browse_scan_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Volume Directory", os.path.dirname(self.load_file_path))
        if dir_path:
            self.txt_scan_dir.setText(dir_path)

    def run_remediation(self):
        scan_dir = self.txt_scan_dir.text().strip()
        if not scan_dir:
            show_dark_message(self, "Validation Error", "Please select a volume image directory to scan.", QMessageBox.Icon.Warning)
            return

        # Disable dialog controls
        self.btn_run.setEnabled(False)
        self.btn_browse_scan.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.lbl_progress.setVisible(True)
        
        from pyside_workers import TiffRemediationWorker
        self.worker = TiffRemediationWorker(self.load_file_path, self.file_type, [scan_dir], self)
        self.worker.progress.connect(self.on_progress)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, msg, val):
        self.lbl_progress.setText(msg)
        self.progress_bar.setValue(val)

    def on_error(self, err):
        self.btn_run.setEnabled(True)
        self.btn_browse_scan.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.lbl_progress.setVisible(False)
        show_dark_message(self, "Remediation Error", err, QMessageBox.Icon.Critical)

    def on_finished(self, remediated, errors, audit_log_path):
        self.progress_bar.setVisible(False)
        self.lbl_progress.setVisible(False)
        self.accept()
        
        summary = (
            f"<b>TIFF Remediation Completed!</b><br><br>"
            f"Remediated Files: {remediated}<br>"
            f"Errors / Missing Files: {errors}<br><br>"
            f"Audit Log: {os.path.basename(audit_log_path) if audit_log_path else 'N/A'}"
        )
        
        summary_dialog = QDialog(self.parent())
        summary_dialog.setWindowTitle("Remediation Summary")
        summary_dialog.setStyleSheet(GLOBAL_STYLE)
        summary_dialog.resize(400, 220)
        apply_dark_titlebar(summary_dialog)
        
        s_layout = QVBoxLayout(summary_dialog)
        lbl_info = QLabel(summary)
        lbl_info.setStyleSheet("font-size: 13px;")
        s_layout.addWidget(lbl_info)
        
        btn_layout = QHBoxLayout()
        btn_log = QPushButton("Open Audit Log")
        btn_log.setStyleSheet("background-color: #8B5CF6; color: white;")
        
        def open_log():
            import subprocess
            try:
                if os.name == 'nt':
                    os.startfile(audit_log_path)
                else:
                    subprocess.call(('xdg-open', audit_log_path))
            except Exception as e:
                show_dark_message(summary_dialog, "Error", f"Could not open audit log: {str(e)}")
                
        btn_log.clicked.connect(open_log)
        btn_close = QPushButton("OK")
        btn_close.clicked.connect(summary_dialog.accept)
        
        btn_layout.addWidget(btn_log)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        s_layout.addLayout(btn_layout)
        summary_dialog.exec()


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
        self.pending_edits = {} # {(row_num, field_name): new_val}
        self.new_columns = [] # List of appended field names
        
        self.settings = QSettings("PageOneLegal", "PageOneRelativityLoadFileTools")
        self.preview_start_line = 1
        self.preview_headers = []
        self.preview_hits = []
        self.preview_current_hit_index = -1
        self.sorted_line_numbers = None  # Full-dataset sorted row numbers [1, 2, ...]

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
        main_layout.setContentsMargins(20, 20, 35, 20)

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

        title_label = QLabel("Relativity Load File Tools")
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
        self.btn_preview_prev = QPushButton("< Prev 10,000")
        self.btn_preview_next = QPushButton("Next 10,000 >")
        
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
        self.btn_clear_search.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
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
        self.act_sort = self.transform_menu.addAction("Sort...")
        self.transform_menu.addSeparator()
        self.act_gap_report = self.transform_menu.addAction("Gap Report...")
        self.transform_menu.addSeparator()
        self.act_merge_volumes = self.transform_menu.addAction("Load File Merge & Volume Normalization...")
        self.transform_menu.addSeparator()
        self.act_split_data = self.transform_menu.addAction("Split Data File...")
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
        
        self.btn_clear_sort = QPushButton("Clear Sort")
        self.btn_clear_sort.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.btn_clear_sort.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_clear_sort.clicked.connect(self.clear_sort)
        
        self.card_sort = InlineSearchCard()
        self.card_sort.set_value("None")
        
        status_layout.addWidget(self.btn_clear_sort)
        status_layout.addWidget(self.card_sort)
        self.search_status_container.setVisible(False)
        
        preview_layout.addWidget(self.search_status_container)
        
        # Splitter
        self.preview_splitter = QSplitter(Qt.Horizontal)
        
        # Left Table
        self.preview_table = CopyableTableView()
        self.preview_table.setSortingEnabled(False)
        self.preview_model = PreviewTableModel()
        self.preview_table.setModel(self.preview_model)
        self.preview_table.setSelectionBehavior(QTableView.SelectRows)
        self.preview_table.setSelectionMode(QTableView.SingleSelection)
        self.preview_table.horizontalHeader().setStretchLastSection(False)
        self.preview_splitter.addWidget(self.preview_table)
        
        # Right Record View using UnifiedDocumentViewer
        self.preview_doc_viewer = UnifiedDocumentViewer()
        self.preview_doc_viewer.setMinimumWidth(200)
        self.preview_splitter.addWidget(self.preview_doc_viewer)
        self.preview_splitter.setSizes([900, 300])
        self.preview_splitter.setStretchFactor(0, 3)
        self.preview_splitter.setStretchFactor(1, 1)
        
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

        self.btn_image_tools = QPushButton("Tools")
        self.btn_image_tools.setObjectName("BtnTools")
        self.image_tools_menu = QMenu(self)
        self.act_image_replace = self.image_tools_menu.addAction("Replace...")
        self.act_image_search = self.image_tools_menu.addAction("Search...")
        self.act_image_print = self.image_tools_menu.addAction("Print PDFs...")
        self.image_tools_menu.addSeparator()
        self.act_image_merge = self.image_tools_menu.addAction("Merge Image Load Files (OPT/LFP)...")
        self.image_tools_menu.addSeparator()
        self.act_image_split = self.image_tools_menu.addAction("Split Image Load File...")
        self.image_tools_menu.addSeparator()
        self.act_image_remediate = self.image_tools_menu.addAction("Bad TIFF Detection & Conversion...")
        self.btn_image_tools.setMenu(self.image_tools_menu)

        img_header_layout.addWidget(lbl_doc_id)
        img_header_layout.addWidget(self.cb_image_doc_id)
        img_header_layout.addSpacing(15)
        img_header_layout.addWidget(self.lbl_image_status_badge)
        img_header_layout.addWidget(self.btn_image_tools)
        img_header_layout.addStretch()

        img_preview_layout.addWidget(img_header_box)

        # Applied Search Bar container widget for Image Preview (hidden by default)
        self.image_search_status_container = QWidget()
        image_status_layout = QHBoxLayout(self.image_search_status_container)
        image_status_layout.setContentsMargins(0, 4, 0, 4)
        image_status_layout.setSpacing(10)
        
        self.btn_image_clear_search = QPushButton("Clear Search")
        self.btn_image_clear_search.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        self.btn_image_clear_search.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.btn_image_clear_search.clicked.connect(self.clear_image_search)
        
        self.card_image_search = InlineSearchCard()
        
        image_status_layout.addWidget(self.btn_image_clear_search)
        image_status_layout.addWidget(self.card_image_search)
        image_status_layout.addStretch()
        self.image_search_status_container.setVisible(False)
        
        img_preview_layout.addWidget(self.image_search_status_container)

        # Body Splitter (Left: Table, Right: Viewer)
        self.image_splitter = QSplitter(Qt.Horizontal)
        self.image_table = QTableView()
        self.image_table.setStyleSheet("background-color: #1E293B; gridline-color: #334155; color: #FFFFFF;")
        self.image_table_model = ImagePageTableModel()
        self.image_table.setModel(self.image_table_model)
        self.image_table.setSelectionBehavior(QTableView.SelectRows)
        self.image_table.setSelectionMode(QTableView.SingleSelection)
        self.image_table.horizontalHeader().setStretchLastSection(False)

        self.studio_doc_viewer = UnifiedDocumentViewer()
        self.studio_doc_viewer.setMinimumWidth(200)

        self.image_splitter.addWidget(self.image_table)
        self.image_splitter.addWidget(self.studio_doc_viewer)
        self.image_splitter.setSizes([900, 300])
        self.image_splitter.setStretchFactor(0, 3)
        self.image_splitter.setStretchFactor(1, 1)

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
        self.header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.header.setStretchLastSection(True)
        
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
        self.act_sort.triggered.connect(self.show_sort_dialog)
        self.act_gap_report.triggered.connect(self.show_gap_report_dialog)
        self.act_merge_volumes.triggered.connect(self.show_volume_merge_dialog)
        self.act_split_data.triggered.connect(self.show_data_split_dialog)
        self.act_image_replace.triggered.connect(self.show_image_replace_dialog)
        self.act_image_search.triggered.connect(self.show_image_search_dialog)
        self.act_image_print.triggered.connect(self.show_pdf_print_dialog)
        self.act_image_merge.triggered.connect(self.show_image_merge_dialog)
        self.act_image_split.triggered.connect(self.show_image_split_dialog)
        self.act_image_remediate.triggered.connect(self.show_image_remediate_dialog)
        self.preview_line_spin.editingFinished.connect(self.preview_go)
        self.preview_table.selectionModel().selectionChanged.connect(self.preview_row_selected)


    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Avoid calling sync_filter_widths recursively on every resize event

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
            
        self.header.setStretchLastSection(True)
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
        self.preview_doc_viewer.meta_table.setColumnWidth(0, 150)
        self.studio_doc_viewer.meta_table.setColumnWidth(0, 150)
        
        self.sync_filter_widths()

    def sync_filter_widths(self, *args):
        self.header.blockSignals(True)
        self.cb_checked_filter.setFixedWidth(self.header.sectionSize(0))
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
        self.header.blockSignals(False)

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
        dlg.setWindowTitle("Page One Relativity Load File Tools - Help Center")
        dlg.resize(850, 650)
        apply_dark_titlebar(dlg)
        dlg.setStyleSheet(GLOBAL_STYLE)
        
        main_layout = QHBoxLayout(dlg)
        
        # Left Panel: List & Search
        left_layout = QVBoxLayout()
        self.help_search = QLineEdit()
        self.help_search.setPlaceholderText("Search help topics...")
        self.help_search.textChanged.connect(self.filter_help_topics)
        left_layout.addWidget(self.help_search)
        
        self.help_list = QListWidget()
        self.help_list.setStyleSheet("""
            QListWidget { background-color: #0F172A; border: 1px solid #334155; border-radius: 4px; padding: 4px; }
            QListWidget::item { padding: 8px; color: #E2E8F0; border-radius: 4px; }
            QListWidget::item:selected { background-color: #3B82F6; color: #FFFFFF; }
            QListWidget::item:hover { background-color: #1E293B; }
        """)
        self.help_list.currentRowChanged.connect(self.display_help_topic)
        left_layout.addWidget(self.help_list)
        
        main_layout.addLayout(left_layout, 1)
        
        # Right Panel: Content Viewer
        self.help_viewer = QTextEdit()
        self.help_viewer.setReadOnly(True)
        self.help_viewer.setStyleSheet("""
            QTextEdit { background-color: #1E293B; border: 1px solid #334155; border-radius: 4px; padding: 12px; color: #F1F5F9; }
        """)
        main_layout.addWidget(self.help_viewer, 2)
        
        # Populate topics
        self.help_topics = {
            "00. Application Overview & Tab Layout": {
                "desc": "Primary workstation for high-performance e-discovery processing, analytics, and quality control. Designed to inspect large load files, perform metadata diagnostics, sanitize paths, and review native/image page layouts.",
                "inst": "Navigate the application using the four core tabs:<br>"
                       " - <b>Schema Analysis Tab:</b> Inspects headers, delimiter structures, encodings, and column integrity.<br>"
                       " - <b>Data Preview Tab:</b> Browses loaded records in paginated grids of 10,000 with quick/advanced searching and type-safe sorting.<br>"
                       " - <b>Image Preview Tab:</b> Controls OPT/LFP image maps, rendering TIF/JPG/PDF pages side-by-side with documents.<br>"
                       " - <b>Metadata Tab:</b> Inspects key-value fields for selected records with context-menu copying."
            },
            "01. Auto Delimiter & Encoding Detection": {
                "desc": "Automatically scans and determines text encodings (e.g., UTF-8-SIG, ASCII) and delimiters (e.g. Comma, Tab, Pipe, DC4 separators) on import to ensure error-free parsing of structured text.",
                "inst": "1. Drag-and-drop or select a load file.<br>"
                       "2. The system scans the initial lines to detect delimiters and sets combobox settings automatically.<br>"
                       "3. If detection fails or is ambiguous, the system defaults to standard parsing or prompts you to select delimiter/quote/encoding properties manually via the schema manager."
            },
            "02. Saving & Exporting Load Files": {
                "desc": "Saves modifications, splits large datasets (by line count, size, or metadata field), and merges multiple volume load files. Maintains strict RelativityOne compatibility formats.",
                "inst": "1. Save modifications by choosing your export target and click <b>Export Load File</b>.<br>"
                       "2. Normalization processes relative paths cleanly to <code>.\\VolumeName\\...</code>.<br>"
                       "3. Detailed CSV audit logs are generated automatically next to the destination file to ensure data compliance and trace ingestion errors."
            },
            "03. DocID & Image Synchronization": {
                "desc": "Links document identifiers (DocID) across the Data Preview grid and Image Preview viewer for real-time synchronization. Selecting a row in the data preview instantly updates and displays corresponding document pages.",
                "inst": "1. Load both a data load file and an image load file.<br>"
                       "2. Map the DocID field in the Image Preview tab.<br>"
                       "3. Click or navigate any record in the Data Preview grid; the Image Preview automatically syncs and displays the first page of the selected document."
            },
            "04. Image Path Mapping & Fallbacks": {
                "desc": "Resolves image paths read from OPT/LFP load files and normalizes them relative to their source volume directories, handling absolute/relative path mappings.",
                "inst": "1. During validation, the path resolution engine searches for image files under the source volume directory.<br>"
                       "2. If an image path is missing, malformed, or points outside the volume directory, the system records it in the CSV audit log.<br>"
                       "3. Pre-flight checks alert you of any path issues before running merges to protect production integrity."
            },
            "05. Bad TIFF Detection & Conversion": {
                "desc": "Scans volume directories for incompatible TIFF compression types or multi-page structures, remediating them to standard single-page structures (JPG for color, CCITT Group 4 for bitonal), backing up originals, and updating the OPT/LFP load file.",
                "inst": "1. Load an OPT or LFP file, click <b>Tools</b> in the Image Preview tab and select <b>Bad TIFF Detection & Conversion...</b>.<br>"
                       "2. Select target volume directories to scan. Original files are backed up automatically to a <code>_backup</code> directory.<br>"
                       "3. Click <b>Run Detection & Conversion</b>. The tool splits multi-page TIFFs into sequential single-page files, standardizes compressions, updates the load file mappings, and reloads the dataset."
            },
            "Data Preview & Navigation": {
                "desc": "Provides high-performance line-by-line page browsing and global search across the loaded data load file. Used in e-discovery workflows to visually verify mapped columns, examine document records, and perform quick text queries.",
                "inst": "1. Open a DAT or CSV data load file.<br>2. Use the <b>Go to Line</b> spinbox or click <b>&lt; Prev 10,000</b> / <b>Next 10,000 &gt;</b> to navigate the grid.<br>3. Enter search terms in the <b>Quick Search</b> bar and click <b>Search</b> or press Enter to filter visible rows.<br>4. Click <b>Advanced Search</b> to perform complex queries targeting specific metadata columns."
            },
            "Image Preview & Rendering": {
                "desc": "Integrates a premium HTML5 canvas page viewer to display linked images (TIF, JPG, or PDF). Allows verification of Bates number stamps and document layout alignment in a side-by-side view.",
                "inst": "1. Open an image load file (OPT or LFP) via <b>Open Image Load File</b> on the Image Preview tab.<br>2. Select the correct <b>DocID Field</b> dropdown option to map the image load file keys to your data.<br>3. Select any document row in the preview table to automatically load and render its pages.<br>4. Use the toolbar buttons (<b>Fit Page</b>, <b>Fit Width</b>, <b>+</b>, <b>-</b>) to adjust the zoom level."
            },
            "Data Preview: Replace Tool": {
                "desc": "Performs fast find-and-replace text updates on a selected metadata column. Used to clean up spelling mistakes, update custody designations, or swap metadata values in bulk.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Replace...</b>.<br>2. Select the target column in the <b>Field to Update</b> dropdown.<br>3. Input the value to find in <b>Find What</b> and the new value in <b>Replace With</b>.<br>4. Select your preferred match mode: <i>Exact Match</i>, <i>Wildcard (* or ?)</i>, or <i>Regular Expression (Regex)</i>.<br>5. Click <b>Apply Replace</b> to modify the field in memory. Confirm the changes by exporting the file."
            },
            "Data Preview: Format Dates Tool": {
                "desc": "Normalizes date metadata to a standard e-discovery format (YYYY-MM-DD). Useful for correcting date format inconsistencies (e.g. MDY vs DMY) and merging separate date and time columns.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Format Dates...</b>.<br>2. Select the target column containing date values.<br>3. Choose the current source date format pattern, or combine separate Date & Time columns by checking the option.<br>4. Select the target output date format (e.g., YYYY-MM-DD).<br>5. Click <b>Format</b> to execute the conversion."
            },
            "Data Preview: Append Field Tool": {
                "desc": "Appends a brand new metadata column to the end of the load file. Used to generate sequential row/sorting indexes, set static values (e.g. Custodian), or duplicate existing columns for mapping.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Append Field...</b>.<br>2. Enter the new column name and select the value type (Static Text, Row Index, or Copy Field).<br>3. Configure custom options such as index prefixing and zero-padding (e.g. 0001).<br>4. Click <b>Append</b> to write the new column."
            },
            "Data Preview: Merge Fields Tool": {
                "desc": "Combines values from two columns together into a single merged column using a custom delimiter. Used in workflows such as joining Date and Time columns or compiling composite keys.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Merge Fields...</b>.<br>2. Choose the first and second source columns to merge.<br>3. Enter the character(s) to use as a separator (e.g., a space or semicolon).<br>4. Select whether to overwrite the first field or create a new column.<br>5. Click <b>Merge</b> to execute."
            },
            "Data Preview: Mass Field Redaction Tool": {
                "desc": "Applies bulk privilege redactions and modifications based on a cross-reference CSV list of document IDs. Features persistent run histories and import/export lists.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Mass Field Redaction...</b>.<br>2. Load the cross-reference CSV containing document identifiers.<br>3. Map the match fields and select the target fields to redact.<br>4. Enter the replacement string (e.g., <i>*REDACTED*</i> or <i>PRIVILEGED</i>).<br>5. Click <b>Run Mass Redaction</b> to update the files."
            },
            "Data Preview: Sort Tool": {
                "desc": "Sorts the data table globally based on numeric, date, or text columns. Essential for organizing records chronologically or sorting by Bates/Control numbers.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Sort...</b>.<br>2. Choose the sort column and select the data type (Text, Numeric, or Date) for type-safe sorting.<br>3. Select Ascending or Descending order.<br>4. Click <b>Sort</b> to apply the global ordering."
            },
            "Data Preview: Gap Report Tool": {
                "desc": "Identifies alphanumeric or numeric sequence gaps in Bates or Control Number ranges. Used to audit incoming production sets for completeness.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Gap Report...</b>.<br>2. Select the prefix and number fields in the dialog.<br>3. Click <b>Run</b> to analyze the ranges.<br>4. Open the generated CSV gap report next to the load file."
            },
            "Data File Split Tool": {
                "desc": "Splits a large consolidated data load file into multiple smaller volumes. Used to divide production sets into manageable packages.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Split Data File...</b>.<br>2. Define the Root Volume Name (e.g. ACMEPROD) and destination folder.<br>3. Select the split method: <i>Line Count</i> (number of records), <i>File Size</i> (MB), or <i>Field Value</i> (whenever a field changes, e.g. Custodian).<br>4. Click <b>Run Split</b> to start the process."
            },
            "Load File Merge & Volume Normalization": {
                "desc": "Consolidates multiple volume-level data load files into a single master load file. Automatically normalizes file paths relative to the volume name directory structure and logs issues to a CSV audit log.",
                "inst": "1. Click the <b>Tools</b> menu on the Data Preview tab and select <b>Load File Merge & Volume Normalization...</b>.<br>2. Click <b>Add Volume File(s)...</b> to select the load files.<br>3. Define mapped fields (DocID, Text Path, Native Path) and choose duplicate handling (Strict, First-In Wins, Last-In Wins, Suffix Append).<br>4. Click <b>Run Merge</b>. Open the generated summary and audit log CSV."
            },
            "Image Preview: Replace Tool": {
                "desc": "Performs find-and-replace string substitutions on image paths within the OPT/LFP image load file.",
                "inst": "1. Click the <b>Tools</b> menu on the Image Preview tab and select <b>Replace...</b>.<br>2. Input the search text and replacement path string.<br>3. Click <b>Apply</b> to replace path strings in memory."
            },
            "Image Preview: Search Tool": {
                "desc": "Finds specific Bates numbers or page ranges inside the image load file.",
                "inst": "1. Click the <b>Tools</b> menu on the Image Preview tab and select <b>Search...</b>.<br>2. Type the Bates key or image file name in the search box.<br>3. Click <b>Search</b> to jump directly to the matching record."
            },
            "Image Preview: Batch PDF Printing": {
                "desc": "Bulk prints and exports mapped images into PDF format. Standardizes layouts by grouping images in zero-padded directories (e.g. 0001) and compiling companion load files.",
                "inst": "1. Click the <b>Tools</b> menu on the Image Preview tab and select <b>Print PDFs...</b>.<br>2. Select the target output directory.<br>3. Configure maximum documents per subfolder, check <i>Zero-pad subfolder names</i>, and check companion load file options.<br>4. Click <b>Print</b> to run the export."
            },
            "Image Load File Merge (OPT/LFP)": {
                "desc": "Consolidates multiple OPT or LFP files, automatically normalizes paths to <code>.\\VolumeName\\...</code>, and resolves Bates key duplicates.",
                "inst": "1. Click the <b>Tools</b> menu on the Image Preview tab and select <b>Merge Image Load Files (OPT/LFP)...</b>.<br>2. Select the source volume files and choose duplicate handling modes.<br>3. Click <b>Run Merge</b> to output the master OPT/LFP."
            },
            "Image Load File Split Tool": {
                "desc": "Divides OPT or LFP image load files into smaller volumes while keeping document boundaries intact.",
                "inst": "1. Click the <b>Tools</b> menu on the Image Preview tab and select <b>Split Image Load File...</b>.<br>2. Choose the root volume name, output directory, and splitting criteria (Line Count, File Size, or Document Boundaries).<br>3. Click <b>Run Split</b> to partition the file."
            },
            "Schema Analysis: Replace Field Names": {
                "desc": "Renames headers/columns in bulk using custom mappings or reference templates. Used to align incoming production fields to database standards.",
                "inst": "1. Click <b>Schema Tools</b> in the Schema Analysis tab and select <b>Replace Field Names...</b>.<br>2. Load a mapping reference file or enter header names manually.<br>3. Apply the mapping to update columns."
            },
            "Metadata Tab Interaction": {
                "desc": "Displays key-value record property metadata in a premium, searchable layout. Useful for copying specific field values quickly during audits.",
                "inst": "1. Select any record row in the Data Preview table.<br>2. Double-click the row or look at the right side panel to browse fields in the Metadata tab.<br>3. Right-click any cell value inside the table and click <b>Copy Field Value</b> to copy the text to your clipboard."
            }
        }
        
        for topic in sorted(self.help_topics.keys()):
            self.help_list.addItem(topic)
            
        # Select first topic by default
        self.help_list.setCurrentRow(0)
        
        close_layout = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        close_layout.addStretch()
        close_layout.addWidget(close_btn)
        left_layout.addLayout(close_layout)
        
        dlg.exec()

    def filter_help_topics(self, text):
        query = text.lower()
        self.help_list.clear()
        for topic in sorted(self.help_topics.keys()):
            if query in topic.lower() or query in self.help_topics[topic]["desc"].lower():
                self.help_list.addItem(topic)
        if self.help_list.count() > 0:
            self.help_list.setCurrentRow(0)

    def display_help_topic(self, index):
        if index < 0 or index >= self.help_list.count():
            self.help_viewer.clear()
            return
        topic = self.help_list.item(index).text()
        info = self.help_topics.get(topic, {})
        if info:
            html = f"""
            <h2 style="color: #60A5FA; font-size: 18px; margin-top: 0; margin-bottom: 12px; font-weight: 600;">{topic}</h2>
            <h3 style="color: #3B82F6; font-size: 13px; margin-top: 15px; margin-bottom: 6px; font-weight: 600; text-transform: uppercase;">Description</h3>
            <p style="color: #E2E8F0; font-size: 13px; margin-top: 0; margin-bottom: 20px; line-height: 1.5;">{info['desc']}</p>
            <h3 style="color: #3B82F6; font-size: 13px; margin-top: 15px; margin-bottom: 6px; font-weight: 600; text-transform: uppercase;">Instructions</h3>
            <p style="color: #E2E8F0; font-size: 13px; margin-top: 0; margin-bottom: 10px; line-height: 1.6;">{info['inst']}</p>
            """
            self.help_viewer.setHtml(html)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Load File", "", "Load Files (*.dat *.csv *.txt);;All Files (*.*)")
        if not path:
            return
            
        self.selected_file_path = path
        self.backup_created = False
        self.sorted_line_numbers = None
        
        # Reset delimiters back to Auto for fresh file analysis
        self.cb_sep.setCurrentText("Auto")
        self.cb_quote.setCurrentText("Auto")
        self.update_delimiters_button_text()
        
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
        from PySide6.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
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
                self.sorted_line_numbers = None
                
                # Reset delimiters back to Auto for fresh file analysis
                self.cb_sep.setCurrentText("Auto")
                self.cb_quote.setCurrentText("Auto")
                self.update_delimiters_button_text()
                
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
        
        # Update Image DocID Field selection dropdown
        if hasattr(self, 'cb_image_doc_id'):
            current_doc_id = self.cb_image_doc_id.currentText()
            fields = [""] + ([r["column"] for r in self.analysis_results] if self.analysis_results else [])
            self.cb_image_doc_id.blockSignals(True)
            self.cb_image_doc_id.clear()
            self.cb_image_doc_id.addItems(fields)
            if current_doc_id in fields:
                self.cb_image_doc_id.setCurrentText(current_doc_id)
            else:
                self.cb_image_doc_id.setCurrentIndex(0)
            self.cb_image_doc_id.blockSignals(False)
                
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
        from PySide6.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()

        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        self.worker = RemapWorker(
            self.selected_file_path, 
            cross_ref_path, 
            path, 
            keep_columns=keep_columns, 
            encoding=enc, 
            sep=sep, 
            quote=qt,
            pending_edits=self.pending_edits,
            new_columns=self.new_columns
        )
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
            # 1. Determine active base dataset index row numbers sequence
            active_dataset = self.preview_hits if getattr(self, 'preview_is_filtered_mode', False) and getattr(self, 'preview_hits', []) else None
            
            # If sorted order exists, re-index active dataset sequence
            if self.sorted_line_numbers is not None:
                if active_dataset is not None:
                    # Intersect current search hits with sorting order
                    hits_set = set(active_dataset)
                    active_dataset = [r for r in self.sorted_line_numbers if r in hits_set]
                else:
                    active_dataset = self.sorted_line_numbers

            if active_dataset is not None:
                start_idx = self.preview_current_hit_index if getattr(self, 'preview_is_filtered_mode', False) else (self.preview_start_line - 1)
                start_idx = max(0, min(start_idx, len(active_dataset) - 1)) if active_dataset else 0
                end_idx = min(start_idx + 10000, len(active_dataset))
                target_lines = active_dataset[start_idx:end_idx]
                headers, records = processor.read_specific_records(self.selected_file_path, target_lines, enc, sep, qt)
                if target_lines and self.sorted_line_numbers is None:
                    self.preview_start_line = target_lines[0]
                    self.preview_line_spin.setValue(self.preview_start_line)
                elif self.sorted_line_numbers is not None:
                    self.preview_line_spin.setValue(self.preview_start_line)
            else:
                self.preview_line_spin.setValue(self.preview_start_line)
                headers, records = processor.read_records(self.selected_file_path, self.preview_start_line, 10000, enc, sep, qt)
            self.preview_headers = headers
            
            # Dynamic dynamic column/edit overlay:
            # 1) Append any new columns tracked in self.new_columns if not already in headers
            for new_col in self.new_columns:
                if new_col not in self.preview_headers:
                    self.preview_headers.append(new_col)
                    
            # 2) For each record, align values and overlay pending edits from self.pending_edits
            overlaid_records = []
            for r_idx, rec in enumerate(records):
                # Row index in pristine file (1-indexed base)
                file_row_num = self.preview_start_line + r_idx
                if active_dataset is not None:
                    file_row_num = target_lines[r_idx]
                
                # Expand record to match total header length (for newly appended columns)
                record_list = list(rec)
                while len(record_list) < len(self.preview_headers):
                    record_list.append("")
                
                for col_idx, h in enumerate(self.preview_headers):
                    edit_key = (file_row_num, h)
                    if edit_key in self.pending_edits:
                        record_list[col_idx] = self.pending_edits[edit_key]
                overlaid_records.append(record_list)

            # Generate absolute line number labels for vertical header display
            absolute_lines = []
            for r_idx in range(len(records)):
                line_val = self.preview_start_line + r_idx
                if active_dataset is not None:
                    line_val = target_lines[r_idx]
                absolute_lines.append(line_val)

            self.preview_model.update_data(
                self.preview_headers, 
                overlaid_records, 
                start_line=self.preview_start_line, 
                line_numbers=absolute_lines
            )

            # Build metadata lookup map for dynamic binding
            self.doc_id_metadata_map = {}
            for rec in overlaid_records:
                row_dict = {}
                for idx, h in enumerate(self.preview_headers):
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
                if not doc_id and self.preview_headers:
                    doc_id = row_dict.get(self.preview_headers[0], "")
                if doc_id:
                    self.doc_id_metadata_map[doc_id] = row_dict

            if records:
                self.preview_table.selectionModel().blockSignals(True)
                try:
                    self.preview_table.selectRow(0)
                finally:
                    self.preview_table.selectionModel().blockSignals(False)
            self.preview_table.viewport().update()
            self.preview_table.update()
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
            self.preview_current_hit_index = max(0, self.preview_current_hit_index - 10000)
        elif self.sorted_line_numbers is not None:
            # When sorting is active, self.preview_start_line is a 1-based index in the sorted list
            self.preview_start_line = max(1, self.preview_start_line - 10000)
        else:
            self.preview_start_line = max(1, self.preview_start_line - 10000)
        self.load_preview_data()

    def preview_next(self):
        if getattr(self, 'preview_is_filtered_mode', False):
            if self.preview_current_hit_index + 10000 < len(self.preview_hits):
                self.preview_current_hit_index += 10000
        elif self.sorted_line_numbers is not None:
            if self.preview_start_line + 10000 <= len(self.sorted_line_numbers):
                self.preview_start_line += 10000
        else:
            self.preview_start_line += 10000
        self.load_preview_data()

    def preview_search_open(self):
        if not self.selected_file_path or not self.analysis_results:
            return
            
        columns = [r["column"] for r in self.analysis_results]
        dialog = SearchDialog(columns, self)
        if dialog.exec() == QDialog.Accepted:
            config = dialog.get_data()
            if not config.get("query"):
                # User submitted an empty query - clear search state
                self.preview_is_filtered_mode = False
                self.lbl_preview_hits.setText("0 hits")
                self.update_applied_search_card(None)
                self.load_preview_data()
                return
                
            self.progress = QProgressDialog("Searching file...", None, 0, 0, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            from PySide6.QtCore import Qt
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Please Wait")
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)
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
            if self.image_doc_id_field:
                self.update_image_studio_link_status()
        else:
            self.update_applied_search_card(None)
            if self.image_doc_id_field:
                self.update_image_studio_link_status()
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

            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            import re
            import fnmatch
            
            # Retrieve all rows or filtered subset
            # Read pristine file rows to make calculations, then apply edits to the in-memory structure
            try:
                headers, records = processor.read_records(self.selected_file_path, 1, 999999, enc, sep, qt)
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to load records for transformation:\n{str(e)}", QMessageBox.Critical)
                return

            field_idx = -1
            for i, h in enumerate(headers):
                if h.lower() == field.lower():
                    field_idx = i
                    break
            if field_idx == -1:
                return

            target_set = set(self.preview_hits) if filtered_only else None
            regex_pat = re.compile(find_pat) if use_regex else None

            count = 0
            error_count = 0

            for r_idx, rec in enumerate(records):
                file_row_num = 1 + r_idx
                if target_set is not None and file_row_num not in target_set:
                    continue

                if field_idx < len(rec):
                    # Fetch pristine or current pending edit value
                    old_val = self.pending_edits.get((file_row_num, field), str(rec[field_idx]))
                    try:
                        if use_regex:
                            if regex_pat.search(old_val):
                                new_val = repl_str
                            else:
                                new_val = old_val
                        else:
                            if "*" in find_pat or "?" in find_pat:
                                if fnmatch.fnmatchcase(old_val, find_pat):
                                    new_val = repl_str
                                else:
                                    new_val = old_val
                            else:
                                new_val = old_val.replace(find_pat, repl_str)

                        if new_val != old_val:
                            self.pending_edits[(file_row_num, field)] = new_val
                            count += 1
                    except Exception:
                        error_count += 1

            self.handle_transform_errors(f"Replaced {count} instances in-memory.", error_count)
            self.load_preview_data()

    def show_image_replace_dialog(self):
        if not hasattr(self, 'opt_store') or not self.opt_store:
            show_dark_message(self, "Warning", "Please load an image file first.", QMessageBox.Warning)
            return
        
        headers = self.image_table_model.headers
        dialog = ReplaceDialog(headers, 0, self)
        
        if dialog.exec() == QDialog.Accepted:
            field, find_pat, repl_str, use_regex, _ = dialog.get_data()
            if not find_pat:
                return
            
            import re
            import fnmatch
            regex_pat = re.compile(find_pat) if use_regex else None
            
            count = 0
            # Perform search and replace on self.opt_store documents
            for doc_id in list(self.opt_store.documents.keys()):
                doc = self.opt_store.documents[doc_id]
                
                # Check / Replace Bates
                if field == "Bates":
                    new_bates_list = []
                    for bates in doc.bates_list:
                        old_val = str(bates)
                        if use_regex and regex_pat.search(old_val):
                            new_val = old_val.replace(regex_pat.search(old_val).group(0), repl_str)
                        elif not use_regex and find_pat in old_val:
                            new_val = old_val.replace(find_pat, repl_str)
                        else:
                            new_val = old_val
                        if new_val != old_val:
                            count += 1
                        new_bates_list.append(new_val)
                    doc.bates_list = new_bates_list
                    # Secondary Bates index update
                    self.opt_store.bates_to_doc_id = {b: doc.doc_id for b in new_bates_list}
                    
                # Check / Replace DocID
                elif field == "DocID":
                    old_val = str(doc.doc_id)
                    if use_regex and regex_pat.search(old_val):
                        new_val = old_val.replace(regex_pat.search(old_val).group(0), repl_str)
                    elif not use_regex and find_pat in old_val:
                        new_val = old_val.replace(find_pat, repl_str)
                    else:
                        new_val = old_val
                    if new_val != old_val:
                        count += 1
                        doc.doc_id = new_val
                        
                # Check / Replace Volume
                elif field == "Volume":
                    old_val = str(doc.volume_name)
                    if use_regex and regex_pat.search(old_val):
                        new_val = old_val.replace(regex_pat.search(old_val).group(0), repl_str)
                    elif not use_regex and find_pat in old_val:
                        new_val = old_val.replace(find_pat, repl_str)
                    else:
                        new_val = old_val
                    if new_val != old_val:
                        count += 1
                        doc.volume_name = new_val

                # Check / Replace Image Path
                elif field == "Image Path":
                    new_paths_list = []
                    for ip in doc.image_paths:
                        old_val = str(ip)
                        if use_regex and regex_pat.search(old_val):
                            new_val = old_val.replace(regex_pat.search(old_val).group(0), repl_str)
                        elif not use_regex and find_pat in old_val:
                            new_val = old_val.replace(find_pat, repl_str)
                        else:
                            new_val = old_val
                        if new_val != old_val:
                            count += 1
                        new_paths_list.append(new_val)
                    doc.image_paths = new_paths_list

            show_dark_message(self, "Success", f"Replaced {count} instances in image preview store.", QMessageBox.Information)
            self.update_image_studio_link_status()

    def show_image_search_dialog(self):
        if not hasattr(self, 'opt_store') or not self.opt_store:
            show_dark_message(self, "Warning", "Please load an image file first.", QMessageBox.Warning)
            return
        
        headers = self.image_table_model.headers
        dialog = SearchDialog(headers, self)
        if dialog.exec() == QDialog.Accepted:
            config = dialog.get_data()
            query = config.get("query")
            if not query:
                # Clear active filters
                self.clear_image_search()
                return
            
            import fnmatch
            field = config.get("field")
            is_regex = config.get("regex", False)
            
            all_pages = self.opt_store.get_all_pages()
            filtered_pages = []
            
            for item in all_pages:
                bates, doc_id, page_num, total_pages, volume, img_path = item
                val_to_check = ""
                if field == "Bates": val_to_check = bates
                elif field == "DocID": val_to_check = doc_id
                elif field == "Page #": val_to_check = str(page_num)
                elif field == "Doc Page Count": val_to_check = str(total_pages)
                elif field == "Volume": val_to_check = volume
                elif field == "Image Path": val_to_check = img_path
                
                match = False
                if is_regex:
                    import re
                    try:
                        match = bool(re.search(query, val_to_check, re.IGNORECASE))
                    except Exception:
                        pass
                else:
                    match = fnmatch.fnmatchcase(val_to_check.lower(), f"*{query.lower()}*")
                    
                if match:
                    filtered_pages.append(item)
                    
            self.image_table_model.update_pages(filtered_pages)
            self.lbl_image_status_badge.setText(f"Filtered: {len(filtered_pages):,} pages")
            
            # Show image search details
            if len(query) > 50:
                query_disp = query[:47] + "..."
            else:
                query_disp = query
                
            if is_regex:
                self.card_image_search.set_value(f"Field [{field}] matches regex '{query_disp}'")
            else:
                self.card_image_search.set_value(f"Field [{field}] contains '*{query_disp}*'")
            self.image_search_status_container.setVisible(True)
            
            if filtered_pages:
                self.image_table.selectRow(0)

    def show_pdf_print_dialog(self):
        if not hasattr(self, 'opt_store') or not self.opt_store:
            show_dark_message(self, "Warning", "Please load an image file first.", QMessageBox.Warning)
            return

        metadata_fields = [r["column"] for r in self.analysis_results] if self.analysis_results else []
        default_doc_id_field = self.image_doc_id_field or ""

        dialog = PdfPrintDialog(metadata_fields, default_doc_id_field, self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            root_out_dir = data["root_out_dir"]
            group_by_field = data["group_by_field"]
            generate_companion = data["generate_companion"]
            companion_format = data["companion_format"] if generate_companion else None
            companion_path = data["companion_path"] if generate_companion else None

            base_dir = getattr(self, "base_dir", "")
            if not base_dir and hasattr(self, "opt_store") and self.opt_store:
                first_img = self.opt_store.get_first_image_path()
                if first_img and hasattr(self, "last_image_load_file_path"):
                    from opt_engine import infer_base_dir
                    base_dir = infer_base_dir(first_img, self.last_image_load_file_path)

            from PySide6.QtWidgets import QProgressDialog
            from PySide6.QtCore import Qt

            # Determine active base dataset index row numbers sequence to respect search filters
            active_lines = self.preview_hits if getattr(self, 'preview_is_filtered_mode', False) and getattr(self, 'preview_hits', []) else None
            if self.sorted_line_numbers is not None:
                if active_lines is not None:
                    hits_set = set(active_lines)
                    active_lines = [r for r in self.sorted_line_numbers if r in hits_set]
                else:
                    active_lines = self.sorted_line_numbers

            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            doc_id_field = self.image_doc_id_field

            # Estimate total output item count
            total_items = len(active_lines) if active_lines is not None else len(self.opt_store.doc_id_list)

            self.progress = QProgressDialog("Initializing PDF export...", "Cancel", 0, total_items, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Printing PDFs")
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress.show()

            from pyside_workers import PdfPrintWorker
            self.pdf_worker = PdfPrintWorker(
                opt_store=self.opt_store,
                base_dir=base_dir,
                root_out_dir=root_out_dir,
                group_by_field=group_by_field,
                doc_id_metadata_map=self.doc_id_metadata_map,
                companion_format=companion_format,
                companion_path=companion_path,
                data_file_path=self.selected_file_path,
                active_lines=active_lines,
                encoding=enc,
                sep=sep,
                quote=qt,
                doc_id_field=doc_id_field,
                generate_ocr=data.get("generate_ocr", False),
                ocr_lang=data.get("ocr_lang", "eng"),
                parent=self
            )
            self.progress.canceled.connect(self.pdf_worker.cancel)
            self.pdf_worker.progress.connect(self.on_pdf_print_progress)
            self.pdf_worker.finished.connect(self.on_pdf_print_finished)
            self.pdf_worker.error.connect(self.on_pdf_print_error)
            self.pdf_worker.start()

    def on_pdf_print_progress(self, index, total, message):
        self.progress.setValue(index)
        self.progress.setLabelText(f"[{index}/{total}] Compiled PDFs created. {message}")

    def on_pdf_print_finished(self, count, errors):
        self.progress.accept()
        msg = f"Export completed successfully!\n\nCompiled PDFs created: {count}"
        if errors > 0:
            msg += f"\nDocuments with errors: {errors}"
        show_dark_message(self, "Export Finished", msg, QMessageBox.Information)

    def on_pdf_print_error(self, err_msg):
        self.progress.accept()
        show_dark_message(self, "Export Error", err_msg, QMessageBox.Critical)

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
            
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            try:
                headers, records = processor.read_records(self.selected_file_path, 1, 999999, enc, sep, qt)
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to read records: {str(e)}", QMessageBox.Critical)
                return

            target_set = set(self.preview_hits) if cfg.get("filtered_only", False) else None
            
            count = 0
            error_count = 0
            
            mode = cfg.get("mode")
            if mode == "format":
                field_name = cfg.get("field")
                field_idx = -1
                for i, h in enumerate(headers):
                    if h.lower() == field_name.lower():
                        field_idx = i
                        break
                if field_idx == -1:
                    return
                
                for r_idx, rec in enumerate(records):
                    file_row_num = 1 + r_idx
                    if target_set is not None and file_row_num not in target_set:
                        continue
                    if field_idx < len(rec):
                        old_val = self.pending_edits.get((file_row_num, field_name), str(rec[field_idx]))
                        if old_val.strip():
                            dt = processor.parse_datetime_flexible(old_val)
                            if dt:
                                try:
                                    py_fmt = processor.get_strftime_format(cfg.get("format"))
                                    new_val = dt.strftime(py_fmt)
                                    if new_val != old_val:
                                        self.pending_edits[(file_row_num, field_name)] = new_val
                                        count += 1
                                except Exception:
                                    error_count += 1
            else:
                # Mode: Merge
                date_field = cfg.get("date_field")
                time_field = cfg.get("time_field")
                new_field = cfg.get("new_field")
                
                date_idx = next((i for i, h in enumerate(headers) if h.lower() == date_field.lower()), -1)
                time_idx = next((i for i, h in enumerate(headers) if h.lower() == time_field.lower()), -1)
                
                if new_field not in self.new_columns:
                    self.new_columns.append(new_field)
                
                for r_idx, rec in enumerate(records):
                    file_row_num = 1 + r_idx
                    if target_set is not None and file_row_num not in target_set:
                        continue
                    
                    date_val = self.pending_edits.get((file_row_num, date_field), str(rec[date_idx]) if date_idx != -1 and date_idx < len(rec) else "")
                    time_val = self.pending_edits.get((file_row_num, time_field), str(rec[time_idx]) if time_idx != -1 and time_idx < len(rec) else "")
                    
                    merged_val, error_msg = processor.validate_and_format_datetime(date_val, time_val, cfg.get("format"))
                    if error_msg:
                        error_count += 1
                    elif merged_val:
                        self.pending_edits[(file_row_num, new_field)] = merged_val
                        count += 1
                
                # Append to active schema fields list
                new_col = {
                    "column": new_field,
                    "type": "Date/Time",
                    "max_len": 20,
                    "sample": "",
                    "selected": True
                }
                self.analysis_results.append(new_col)
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
                
            self.handle_transform_errors(f"Processed date operation for {count} records in-memory.", error_count)
            self.reload_file_schema()
            
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

        # Save run record to QSettings history list
        from PySide6.QtCore import QSettings
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
            
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        # 1. Read cross reference keys
        csv_keys = set()
        try:
            with open(csv_path, 'r', encoding=csv_encoding, newline='', errors='ignore') as f:
                reader = csv.reader(f, delimiter=csv_sep, quotechar=csv_quote)
                csv_headers = next(reader)
                csv_cols_lower = [c.lower() for c in csv_headers]
                if csv_match.lower() not in csv_cols_lower:
                    raise ValueError(f"Match field '{csv_match}' not found in cross-reference headers.")
                csv_match_idx = csv_cols_lower.index(csv_match.lower())
                
                for row in reader:
                    if csv_match_idx < len(row):
                        val = row[csv_match_idx]
                        if val is not None and val != "":
                            csv_keys.add(str(val).strip().lower())
        except Exception as e:
            show_dark_message(self, "Error", f"Failed to read match file: {str(e)}", QMessageBox.Critical)
            return

        # 2. Read load file rows and compare
        try:
            headers, records = processor.read_records(self.selected_file_path, 1, 999999, enc, sep, qt)
        except Exception as e:
            show_dark_message(self, "Error", f"Failed to read load file: {str(e)}", QMessageBox.Critical)
            return

        lf_match_idx = next((i for i, h in enumerate(headers) if h.lower() == lf_match.lower()), -1)
        if lf_match_idx == -1:
            show_dark_message(self, "Error", f"Column '{lf_match}' not found in load file headers.", QMessageBox.Critical)
            return

        header_indices = {h.lower().strip(): idx for idx, h in enumerate(headers)}
        fields_to_replace_indices = []
        for field in matched_fields:
            f_lower = field.lower().strip()
            if f_lower in header_indices:
                fields_to_replace_indices.append(header_indices[f_lower])

        count = 0
        error_count = 0

        for r_idx, rec in enumerate(records):
            file_row_num = 1 + r_idx
            if lf_match_idx < len(rec):
                lf_val = str(rec[lf_match_idx]).strip().lower()
                if lf_val in csv_keys:
                    row_modified = False
                    for f_idx in fields_to_replace_indices:
                        f_name = headers[f_idx]
                        try:
                            self.pending_edits[(file_row_num, f_name)] = replacement_string
                            row_modified = True
                        except Exception:
                            error_count += 1
                    if row_modified:
                        count += 1

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
        
        self.handle_transform_errors(f"Mass redaction complete in-memory: {count} records updated.", error_count)
        self.reload_file_schema()

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
        from PySide6.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
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
        from PySide6.QtCore import QTimer
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
        from PySide6.QtWidgets import QMessageBox
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
        from PySide6.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModality.WindowModal)
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
        if getattr(self, "image_doc_id_field", None):
            self.update_image_studio_link_status()

    def clear_image_search(self):
        if hasattr(self, 'card_image_search'):
            self.card_image_search.set_value("None")
        if hasattr(self, 'image_search_status_container'):
            self.image_search_status_container.setVisible(False)
        if hasattr(self, 'opt_store') and self.opt_store:
            self.update_image_studio_link_status()

    def clear_sort(self):
        self.sorted_line_numbers = None
        if hasattr(self, "card_sort"):
            self.card_sort.set_value("None")
            self.btn_clear_sort.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
        
        # Check if we need to hide the container
        has_search = getattr(self, 'preview_is_filtered_mode', False) and bool(getattr(self, 'preview_hits', []))
        if not has_search:
            self.search_status_container.setVisible(False)
            
        self.preview_start_line = 1
        self.preview_current_hit_index = 0
        self.load_preview_data()

    def update_applied_search_card(self, config=None):
        if not config:
            self.card_search.set_value("None")
            self.btn_clear_search.setStyleSheet("background-color: #334155; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
            has_sort = getattr(self, 'sorted_line_numbers', None) is not None
            if not has_sort:
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
        current_tab = self.tabs.currentIndex()
        if current_tab == 2:  # Image Preview tab
            if not hasattr(self, 'opt_store') or not self.opt_store:
                show_dark_message(self, "Warning", "Please load an image file first.", QMessageBox.Warning)
                return
            
            filter_str = "Opticon Files (*.opt);;IPRO LFP Files (*.lfp)"
            path, selected_filter = QFileDialog.getSaveFileName(self, "Export Image Load File", "", filter_str)
            if not path:
                return
                
            try:
                # Retrieve current image pages displayed in the table model
                pages = self.image_table_model.pages
                from opt_engine import write_opt_file, write_lfp_file
                
                if ".lfp" in path.lower() or "lfp" in selected_filter.lower():
                    write_lfp_file(path, pages)
                else:
                    write_opt_file(path, pages)
                    
                show_dark_message(self, "Success", f"Successfully exported {len(pages):,} pages to image load file.", QMessageBox.Information)
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to export image load file:\n{str(e)}", QMessageBox.Critical)
            return

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
        from PySide6.QtCore import Qt
        self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        apply_dark_titlebar(self.progress)
        self.progress.setWindowTitle("Please Wait")
        self.progress.setWindowModality(Qt.WindowModal)
        self.progress.show()
        
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        self.worker = RemapWorker(
            self.selected_file_path, 
            cross_ref_path, 
            path, 
            keep_columns=keep_columns, 
            encoding=enc, 
            sep=sep, 
            quote=qt, 
            target_line_numbers=target_lines,
            pending_edits=self.pending_edits,
            new_columns=self.new_columns
        )
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
                
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            try:
                headers, records = processor.read_records(self.selected_file_path, 1, 999999, enc, sep, qt)
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to read records: {str(e)}", QMessageBox.Critical)
                return

            limit_filtered = getattr(self, 'preview_is_filtered_mode', False)
            target_set = set(self.preview_hits) if limit_filtered else None

            if new_field_name not in self.new_columns:
                self.new_columns.append(new_field_name)

            copy_idx = next((i for i, h in enumerate(headers) if h.lower() == copy_field.lower()), -1)

            count = 0
            error_count = 0

            for r_idx, rec in enumerate(records):
                file_row_num = 1 + r_idx
                if target_set is not None and file_row_num not in target_set:
                    continue

                val_to_append = ""
                try:
                    if val_type == "static":
                        val_to_append = static_val
                        count += 1
                    elif val_type == "row_num":
                        val_to_append = prefix + (str(file_row_num).zfill(padding) if padding > 0 else str(file_row_num))
                        count += 1
                    elif val_type == "copy":
                        if copy_idx != -1 and copy_idx < len(rec):
                            val_to_append = self.pending_edits.get((file_row_num, copy_field), str(rec[copy_idx]))
                            count += 1
                except Exception:
                    error_count += 1
                
                self.pending_edits[(file_row_num, new_field_name)] = val_to_append

            # Update Metadata info and schema list
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
            
            self.handle_transform_errors(f"Appended new field {new_field_name} to {count} records in-memory.", error_count)

    def show_gap_report_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            show_dark_message(self, "Warning", "Please open a file and analyze it first.", QMessageBox.Warning)
            return
        dialog = GapReportDialog(self.selected_file_path, self.analysis_results, self)
        dialog.exec()

    def show_volume_merge_dialog(self):
        dialog = VolumeMergeDialog(self)
        if dialog.exec() == QDialog.Accepted:
            if hasattr(dialog, "merged_output_path") and dialog.merged_output_path:
                self.selected_file_path = dialog.merged_output_path
                self.backup_created = False
                self.sorted_line_numbers = None
                
                # Reset delimiters to Auto
                self.cb_sep.setCurrentText("Auto")
                self.cb_quote.setCurrentText("Auto")
                self.update_delimiters_button_text()
                
                # Start analysis to load into the interface
                self.start_analysis()

    def show_image_merge_dialog(self):
        dialog = ImageVolumeMergeDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.merged_output_path:
            self.import_image_load_file_path(dialog.merged_output_path)

    def show_data_split_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            show_dark_message(self, "Warning", "Please open a file and analyze it first.", QMessageBox.Warning)
            return
            
        enc = self.get_override_val(self.cb_encoding)
        sep = self.get_override_val(self.cb_sep)
        qt = self.get_override_val(self.cb_quote)
        
        # Resolve 'Auto' delimiters if selected
        if not enc or not sep or not qt:
            det_enc, det_sep, det_quote, _, _ = processor.infer_and_validate_format(self.selected_file_path)
            enc = enc or det_enc or 'utf-8'
            sep = sep or det_sep or ','
            qt = qt or det_quote or '"'
            
        columns = [r["column"] for r in self.analysis_results]
        
        dialog = DataSplitDialog(self.selected_file_path, enc, sep, qt, columns, self)
        dialog.exec()

    def show_image_split_dialog(self):
        if not hasattr(self, 'last_image_load_file_path') or not self.last_image_load_file_path:
            show_dark_message(self, "Warning", "Please load an image load file first.", QMessageBox.Warning)
            return
            
        ext = os.path.splitext(self.last_image_load_file_path)[1].lower()
        file_type = "OPT" if ext == ".opt" else "LFP"
        
        dialog = ImageSplitDialog(self.last_image_load_file_path, file_type, self)
        dialog.exec()

    def show_image_remediate_dialog(self):
        if not hasattr(self, 'last_image_load_file_path') or not self.last_image_load_file_path:
            show_dark_message(self, "Warning", "Please load an image load file first.", QMessageBox.Warning)
            return
            
        ext = os.path.splitext(self.last_image_load_file_path)[1].lower()
        file_type = "OPT" if ext == ".opt" else "LFP"
        
        dialog = TiffRemediationDialog(self.last_image_load_file_path, file_type, self)
        if dialog.exec() == QDialog.Accepted:
            self.import_image_load_file_path(self.last_image_load_file_path)

    def show_sort_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            return
        columns = [r["column"] for r in self.analysis_results]
        dialog = FieldSortDialog(columns, self)
        if dialog.exec() == QDialog.Accepted:
            sort_col, sort_type, ascending = dialog.get_data()
            if not sort_col:
                return
                
            self.progress = QProgressDialog("Sorting entire dataset...", None, 0, 0, self)
            self.progress.setStyleSheet(GLOBAL_STYLE)
            from PySide6.QtCore import Qt
            self.progress.setWindowFlags(self.progress.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
            apply_dark_titlebar(self.progress)
            self.progress.setWindowTitle("Please Wait")
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress.show()
            QApplication.processEvents()
            
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            try:
                headers, records = processor.read_records(self.selected_file_path, 1, 999999, enc, sep, qt)
            except Exception as e:
                self.progress.close()
                show_dark_message(self, "Error", f"Failed to read dataset: {str(e)}", QMessageBox.Critical)
                return
                
            # Align headers list
            col_idx = next((i for i, h in enumerate(headers) if h.lower() == sort_col.lower()), -1)
            
            # Map elements with their 1-based original line number indexes
            indexed_records = []
            for r_idx, rec in enumerate(records):
                file_row_num = 1 + r_idx
                # Fetch overlaid values from pending edits
                val = self.pending_edits.get((file_row_num, sort_col), str(rec[col_idx]) if col_idx != -1 and col_idx < len(rec) else "")
                indexed_records.append((file_row_num, val))
                
            # Sort types matching PreviewTableModel
            def safe_float(val):
                cleaned = str(val).strip().replace('$', '').replace(',', '')
                # Find trailing decimal formatting
                import re
                match = re.search(r'[-+]?\d*\.\d+|\d+', cleaned)
                if match:
                    try:
                        return float(match.group(0))
                    except ValueError:
                        pass
                return float('-inf') if ascending else float('inf')

            def safe_date(val):
                from dateutil import parser
                import datetime
                try:
                    return parser.parse(str(val).strip())
                except Exception:
                    return datetime.datetime.min if ascending else datetime.datetime.max

            if sort_type == "Numeric":
                key_func = lambda item: safe_float(item[1])
            elif sort_type == "Date":
                key_func = lambda item: safe_date(item[1])
            elif sort_type == "DocID":
                import re
                def split_doc_id(val):
                    val_str = str(val).strip()
                    # Find last numeric sequence
                    match = re.search(r'^(.*?)(\d+)$', val_str)
                    if match:
                        prefix = match.group(1).lower()
                        num_part = int(match.group(2))
                        return (prefix, num_part)
                    else:
                        return (val_str.lower(), 0)
                key_func = lambda item: split_doc_id(item[1])
            else:
                key_func = lambda item: str(item[1]).strip().lower()
                
            indexed_records.sort(key=key_func, reverse=not ascending)
            
            # Populate sorted line numbers array
            self.sorted_line_numbers = [item[0] for item in indexed_records]
            
            self.progress.close()
            
            # Update Sort Card visual indicator
            ord_str = "Ascending" if ascending else "Descending"
            if hasattr(self, "card_sort"):
                self.card_sort.set_value(f"Sorted on [{sort_col}] ({sort_type}, {ord_str})")
                self.btn_clear_sort.setStyleSheet("background-color: #F97316; color: white; padding: 6px 12px; border-radius: 6px; font-weight: bold;")
                self.search_status_container.setVisible(True)
            
            # Reset paging index to start from beginning of sorted dataset
            self.preview_start_line = 1
            self.preview_current_hit_index = 0
            self.load_preview_data()

    def show_merge_fields_dialog(self):
        if not self.selected_file_path or not self.analysis_results:
            return
        columns = [r["column"] for r in self.analysis_results]
        dialog = MergeFieldsDialog(columns, self)
        if dialog.exec() == QDialog.Accepted:
            first_field, second_field, delimiter, new_field_name = dialog.get_data()
            if not new_field_name:
                return
                
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            
            try:
                headers, records = processor.read_records(self.selected_file_path, 1, 999999, enc, sep, qt)
            except Exception as e:
                show_dark_message(self, "Error", f"Failed to read records: {str(e)}", QMessageBox.Critical)
                return

            limit_filtered = getattr(self, 'preview_is_filtered_mode', False)
            target_set = set(self.preview_hits) if limit_filtered else None

            if new_field_name not in self.new_columns:
                self.new_columns.append(new_field_name)

            f1_idx = next((i for i, h in enumerate(headers) if h.lower() == first_field.lower()), -1)
            f2_idx = next((i for i, h in enumerate(headers) if h.lower() == second_field.lower()), -1)

            count = 0
            error_count = 0

            for r_idx, rec in enumerate(records):
                file_row_num = 1 + r_idx
                if target_set is not None and file_row_num not in target_set:
                    continue

                v1 = self.pending_edits.get((file_row_num, first_field), str(rec[f1_idx]) if f1_idx != -1 and f1_idx < len(rec) else "")
                v2 = self.pending_edits.get((file_row_num, second_field), str(rec[f2_idx]) if f2_idx != -1 and f2_idx < len(rec) else "")

                self.pending_edits[(file_row_num, new_field_name)] = f"{v1}{delimiter}{v2}"
                count += 1

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
            
            self.handle_transform_errors(f"Merged fields into {new_field_name} for {count} records in-memory.", error_count)
            
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
            if hasattr(self, 'card_image_search'):
                self.card_image_search.set_value("None")
            if hasattr(self, 'image_search_status_container'):
                self.image_search_status_container.setVisible(False)

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
                self.image_table.resizeColumnsToContents()
                self.pad_table_columns(self.image_table, padding=15)
                self.btn_export_remapped.setEnabled(True)
            else:
                self.lbl_image_status_badge.setText("No Images Found")
                self.lbl_image_status_badge.setStyleSheet("color: #F87171; font-weight: bold; padding: 4px 8px; background-color: #1E293B; border-radius: 4px;")
                self.btn_export_remapped.setEnabled(False)

            show_dark_message(self, "Load File Imported", f"Successfully loaded {len(self.opt_store)} documents from {os.path.basename(file_path)}. Choose a DocID Field dropdown value to map paths and display images.")
        except Exception as e:
            show_dark_message(self, "Load File Error", str(e), QMessageBox.Critical)

    def update_image_studio_link_status(self):
        pages = self.opt_store.get_all_pages()
        
        # If we have an active search filter, only show pages whose DocID matches the active search subset
        if getattr(self, "preview_is_filtered_mode", False) and getattr(self, "preview_hits", []):
            enc = self.get_override_val(self.cb_encoding)
            sep = self.get_override_val(self.cb_sep)
            qt = self.get_override_val(self.cb_quote)
            try:
                # Retrieve the active DocID strings of the searched hits
                headers, records = processor.read_specific_records(self.selected_file_path, self.preview_hits, enc, sep, qt)
                active_doc_ids = set()
                for rec in records:
                    row_dict = {h: str(rec[i]) for i, h in enumerate(headers) if i < len(rec)}
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
                        active_doc_ids.add(str(doc_id).strip().lower())
                        
                # Filter optical page list down to match doc ids in active_doc_ids set
                pages = [p for p in pages if str(p[1]).strip().lower() in active_doc_ids]
            except Exception:
                pass

        self.image_table_model.update_pages(pages)

        if pages:
            self.image_table.selectRow(0)
            self.image_current_doc_idx = 0
            self.lbl_image_status_badge.setText(f"Linked: {len(pages):,} pages ({len(self.opt_store):,} docs)")
            self.lbl_image_status_badge.setStyleSheet("color: #4ADE80; font-weight: bold; padding: 4px 8px; background-color: #1E293B; border-radius: 4px;")
            self.image_table.resizeColumnsToContents()
            self.pad_table_columns(self.image_table, padding=15)
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
            is_loaded = bool(getattr(self, 'opt_store', None)) and len(self.opt_store) > 0
            self.btn_export_remapped.setEnabled(is_loaded)
        else:
            self.btn_open.setText("Open Data Load File")
            is_loaded = bool(getattr(self, 'selected_file_path', None))
            self.btn_export_remapped.setEnabled(is_loaded)

        if index == 1:
            self.load_preview_data()

    def closeEvent(self, event):
        if hasattr(self, "pending_edits") and self.pending_edits:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes in memory. Closing the application now will discard these edits.\n\nDo you want to exit anyway?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

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
