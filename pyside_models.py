from PyQt5.QtCore import Qt, QAbstractTableModel, QSortFilterProxyModel, QModelIndex
import processor

class SchemaTableModel(QAbstractTableModel):
    def __init__(self, data=None, rename_map=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        for item in self._data:
            if "selected" not in item:
                item["selected"] = True
        self.rename_map = rename_map or {}
        self.headers = ["Export", "Source Field", "Suggested Type", "Max Length", "Sample"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        row_data = self._data[index.row()]
        col_name = self.headers[index.column()]

        if role == Qt.DisplayRole:
            if col_name == "Export":
                return "☑" if row_data.get("selected", True) else "☐"
            elif col_name == "Source Field":
                return row_data.get("column", "")
            elif col_name == "Target Name":
                norm = processor.normalize_field_name(row_data.get("column", ""))
                return self.rename_map.get(norm, row_data.get("column", ""))
            elif col_name == "Suggested Type":
                return row_data.get("type", "")
            elif col_name == "Max Length":
                return str(row_data.get("max_len", ""))
            elif col_name == "Sample":
                return row_data.get("sample", "")
        
        elif role == Qt.ForegroundRole:
            if col_name == "Export":
                from PyQt5.QtGui import QColor
                return QColor("#3B82F6") if row_data.get("selected", True) else QColor("#6B7280")
            elif col_name == "Target Name":
                norm = processor.normalize_field_name(row_data.get("column", ""))
                if norm in self.rename_map:
                    from PyQt5.QtGui import QColor
                    return QColor("#FBBF24")  # Amber 400

        elif role == Qt.TextAlignmentRole:
            if col_name == "Export":
                return Qt.AlignCenter

        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def setData(self, index, value, role=Qt.EditRole):
        return False

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_data):
        self.beginResetModel()
        for item in new_data:
            if "selected" not in item:
                item["selected"] = True
        self._data = new_data
        self.endResetModel()

    def update_map(self, rename_map):
        has_target = "Target Name" in self.headers
        
        if rename_map and not has_target:
            self.beginInsertColumns(QModelIndex(), 1, 1)
            self.headers.insert(1, "Target Name")
            self.rename_map = rename_map
            self.endInsertColumns()
        elif not rename_map and has_target:
            self.beginRemoveColumns(QModelIndex(), 1, 1)
            self.headers.remove("Target Name")
            self.rename_map = rename_map
            self.endRemoveColumns()
        else:
            self.beginResetModel()
            self.rename_map = rename_map
            self.endResetModel()

    def move_row(self, row, direction):
        """Moves row up (-1) or down (1) in the underlying data list."""
        if direction == -1:
            if row <= 0 or row >= len(self._data):
                return False
            self.beginMoveRows(QModelIndex(), row, row, QModelIndex(), row - 1)
            self._data[row], self._data[row - 1] = self._data[row - 1], self._data[row]
            self.endMoveRows()
            return True
        elif direction == 1:
            if row < 0 or row >= len(self._data) - 1:
                return False
            self.beginMoveRows(QModelIndex(), row, row, QModelIndex(), row + 2)
            self._data[row], self._data[row + 1] = self._data[row + 1], self._data[row]
            self.endMoveRows()
            return True
        return False


class SchemaFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.f_src = ""
        self.f_tgt = ""
        self.f_typ = ""
        self.f_max = ""
        self.f_max_op = "="
        self.f_checked_filter = "All"

    def set_filters(self, src, tgt, typ, max_val, max_op, checked_filter="All"):
        self.f_src = src.lower()
        self.f_tgt = tgt.lower()
        self.f_typ = typ.lower()
        self.f_max = max_val.lower()
        self.f_max_op = max_op
        self.f_checked_filter = checked_filter
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        model = self.sourceModel()
        
        item = model._data[source_row] if source_row < len(model._data) else {}
        if item.get("system_field", False) or item.get("system_only", False):
            return False
            
        if self.f_checked_filter == "Checked":
            selected = item.get("selected", True)
            if not selected:
                return False
        elif self.f_checked_filter == "Unchecked":
            selected = item.get("selected", True)
            if selected:
                return False

        # Helper to get data by column name
        def get_data(col_name):
            try:
                idx = model.headers.index(col_name)
                val = model.data(model.index(source_row, idx, source_parent))
                return str(val).lower() if val else ""
            except ValueError:
                return ""

        src = get_data("Source Field")
        tgt = get_data("Target Name")
        typ = get_data("Suggested Type")
        max_str = get_data("Max Length")

        if self.f_src and self.f_src not in src: return False
        if self.f_tgt and self.f_tgt not in tgt: return False
        if self.f_typ and self.f_typ not in typ: return False

        if self.f_max:
            try:
                limit = int(self.f_max.strip())
                val_len = int(max_str)
                op = self.f_max_op
                if op == "=" and val_len != limit: return False
                elif op == ">" and val_len <= limit: return False
                elif op == "<" and val_len >= limit: return False
                elif op == ">=" and val_len < limit: return False
                elif op == "<=" and val_len > limit: return False
            except ValueError:
                if self.f_max.strip() not in max_str: return False

        return True


class GapTableModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self.headers = ["Prefix", "Gap Start", "Gap End", "Missing Count"]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        gap = self._data[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return gap.get("prefix", "")
            elif col == 1: return gap.get("gap_start", "")
            elif col == 2: return gap.get("gap_end", "")
            elif col == 3: return str(gap.get("missing_count", ""))

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.headers[section]
        return None

    def update_data(self, new_data):
        self.beginResetModel()
        self._data = new_data
        self.endResetModel()

class PreviewTableModel(QAbstractTableModel):
    def __init__(self, headers=None, data=None, parent=None):
        super().__init__(parent)
        self.headers = headers or []
        self._data = data or []

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        if role == Qt.DisplayRole:
            row_data = self._data[index.row()]
            col = index.column()
            if col < len(row_data):
                return str(row_data[col])
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < len(self.headers):
                return self.headers[section]
        elif role == Qt.DisplayRole and orientation == Qt.Vertical:
            return str(getattr(self, 'start_line', 1) + section)
        return None

    def update_data(self, new_headers, new_data, start_line=1):
        self.beginResetModel()
        self.headers = new_headers
        self._data = new_data
        self.start_line = start_line
        self.endResetModel()

class RecordTableModel(QAbstractTableModel):
    def __init__(self, headers=None, row_data=None, parent=None):
        super().__init__(parent)
        self.raw_headers = headers or []
        self.raw_row_data = row_data or []
        self.headers = []
        self.row_data = []
        self.model_headers = ["Field Name", "Field Value"]
        self.hide_empty = False
        self.rebuild_view()

    def rowCount(self, parent=QModelIndex()):
        return len(self.headers)

    def columnCount(self, parent=QModelIndex()):
        return 2

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        row = index.row()
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return str(self.headers[row])
            elif col == 1:
                if row < len(self.row_data):
                    return str(self.row_data[row])
                return ""
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.model_headers[section]
        return None

    def rebuild_view(self):
        new_headers = []
        new_row_data = []
        for i, h in enumerate(self.raw_headers):
            val = ""
            if i < len(self.raw_row_data):
                val = str(self.raw_row_data[i])
            if self.hide_empty and not val.strip():
                continue
            new_headers.append(h)
            new_row_data.append(val)
        self.headers = new_headers
        self.row_data = new_row_data

    def set_hide_empty(self, hide):
        self.beginResetModel()
        self.hide_empty = hide
        self.rebuild_view()
        self.endResetModel()

    def update_data(self, headers, row_data):
        self.beginResetModel()
        self.raw_headers = headers
        self.raw_row_data = row_data
        self.rebuild_view()
        self.endResetModel()


class ImagePageTableModel(QAbstractTableModel):
    """
    High-performance QAbstractTableModel designed to handle 500,000+ page rows
    (OPT-style: Bates, DocID, Page #, Doc Page Count, Volume, Image Path).
    Doc Page Count is displayed ONLY when Bates == DocID (document break).
    """
    def __init__(self, pages=None, parent=None):
        super().__init__(parent)
        self.pages = pages or []  # List of tuples: (bates, doc_id, page_num, total_pages, volume, path)
        self.headers = ["Bates", "DocID", "Page #", "Doc Page Count", "Volume", "Image Path"]

    def rowCount(self, parent=QModelIndex()):
        return len(self.pages)

    def columnCount(self, parent=QModelIndex()):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < self.rowCount()):
            return None

        row_item = self.pages[index.row()]
        if len(row_item) == 6:
            bates, doc_id, page_num, total_pages, volume, path = row_item
        else:
            bates, doc_id, page_num, volume, path = row_item
            total_pages = 0

        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0: return bates
            elif col == 1: return doc_id
            elif col == 2: return str(page_num)
            elif col == 3:
                # Show total page count field ONLY when Bates == DocID
                if str(bates).strip().lower() == str(doc_id).strip().lower():
                    return str(total_pages) if total_pages > 0 else ""
                return ""
            elif col == 4: return volume
            elif col == 5: return path

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if section < len(self.headers):
                return self.headers[section]
        elif role == Qt.DisplayRole and orientation == Qt.Vertical:
            return str(section + 1)
        return None

    def update_pages(self, pages):
        self.beginResetModel()
        self.pages = pages or []
        self.endResetModel()


