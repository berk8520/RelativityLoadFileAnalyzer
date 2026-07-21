from PyQt5.QtCore import QThread, pyqtSignal as Signal
import processor
import traceback

class AnalysisWorker(QThread):
    finished = Signal(str, str, str, list)  # encoding, delimiter, row_count, schema_results
    error = Signal(str)

    def __init__(self, file_path, encoding=None, sep=None, quote=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.encoding = encoding
        self.sep = sep
        self.quote = quote

    def run(self):
        try:
            encoding, delimiter, row_count, schema_results = processor.analyze_load_file(
                self.file_path, self.encoding, self.sep, self.quote
            )
            self.finished.emit(encoding, delimiter, str(row_count), schema_results)
        except Exception as e:
            self.error.emit(str(e))


class RemapWorker(QThread):
    finished = Signal(int)  # count of fields mapped
    error = Signal(str)

    def __init__(self, file_path, cross_ref_path, output_path, keep_columns=None, encoding=None, sep=None, quote=None, target_line_numbers=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.cross_ref_path = cross_ref_path
        self.output_path = output_path
        self.keep_columns = keep_columns
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.target_line_numbers = target_line_numbers

    def run(self):
        try:
            count = processor.remap_headers(
                self.file_path, 
                self.cross_ref_path, 
                self.output_path, 
                keep_columns=self.keep_columns,
                encoding=self.encoding,
                sep=self.sep,
                quote=self.quote,
                target_line_numbers=self.target_line_numbers
            )
            self.finished.emit(count)
        except Exception as e:
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")


class GapWorker(QThread):
    finished = Signal(list)  # gap results
    error = Signal(str)

    def __init__(self, file_path, start_col, end_col, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.start_col = start_col
        self.end_col = end_col

    def run(self):
        try:
            results = processor.find_sequence_gaps(self.file_path, self.start_col, self.end_col)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class PreviewSearchWorker(QThread):
    finished = Signal(list)  # list of hits (line numbers)
    error = Signal(str)

    def __init__(self, file_path, config, encoding=None, sep=None, quote=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.config = config
        self.encoding = encoding
        self.sep = sep
        self.quote = quote

    def run(self):
        try:
            hits = processor.search_records(
                self.file_path, 
                self.config, 
                encoding=self.encoding, 
                sep=self.sep, 
                quote=self.quote
            )
            self.finished.emit(hits)
        except Exception as e:
            self.error.emit(str(e))


class ReplaceWorker(QThread):
    finished = Signal(int, int)  # number of replacements made, error_count
    error = Signal(str)

    def __init__(self, file_path, field_name, find_pattern, replace_string, encoding=None, sep=None, quote=None, use_regex=False, target_line_numbers=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.field_name = field_name
        self.find_pattern = find_pattern
        self.replace_string = replace_string
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.use_regex = use_regex
        self.target_line_numbers = target_line_numbers

    def run(self):
        try:
            count, error_count = processor.replace_field_data(
                self.file_path,
                self.field_name,
                self.find_pattern,
                self.replace_string,
                encoding=self.encoding,
                sep=self.sep,
                quote=self.quote,
                use_regex=self.use_regex,
                target_line_numbers=self.target_line_numbers
            )
            self.finished.emit(count, error_count)
        except Exception as e:
            self.error.emit(str(e))


class FormatDateWorker(QThread):
    finished = Signal(int, int)  # number of replacements made, error_count
    error = Signal(str)

    def __init__(self, file_path, config, encoding=None, sep=None, quote=None, target_line_numbers=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.config = config
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.target_line_numbers = target_line_numbers

    def run(self):
        try:
            if self.config["mode"] == "format":
                count, error_count = processor.format_date_field(
                    self.file_path,
                    self.config["field"],
                    self.config["format"],
                    encoding=self.encoding,
                    sep=self.sep,
                    quote=self.quote,
                    target_line_numbers=self.target_line_numbers
                )
            else:
                count, error_count = processor.merge_date_time_fields(
                    self.file_path,
                    self.config["date_field"],
                    self.config["time_field"],
                    self.config["new_field"],
                    self.config["format"],
                    encoding=self.encoding,
                    sep=self.sep,
                    quote=self.quote,
                    target_line_numbers=self.target_line_numbers
                )
            self.finished.emit(count, error_count)
        except Exception as e:
            self.error.emit(str(e))


class AppendFieldWorker(QThread):
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, file_path, new_field_name, val_type, static_val="", copy_field="", prefix="", padding=0, encoding=None, sep=None, quote=None, target_line_numbers=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.new_field_name = new_field_name
        self.val_type = val_type
        self.static_val = static_val
        self.copy_field = copy_field
        self.prefix = prefix
        self.padding = padding
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.target_line_numbers = target_line_numbers

    def run(self):
        try:
            count, error_count = processor.append_field_data(
                self.file_path,
                self.new_field_name,
                self.val_type,
                static_val=self.static_val,
                copy_field=self.copy_field,
                prefix=self.prefix,
                padding=self.padding,
                encoding=self.encoding,
                sep=self.sep,
                quote=self.quote,
                target_line_numbers=self.target_line_numbers
            )
            self.finished.emit(count, error_count)
        except Exception as e:
            self.error.emit(str(e))


class MergeFieldsWorker(QThread):
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, file_path, first_field, second_field, delimiter, new_field_name, encoding=None, sep=None, quote=None, target_line_numbers=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.first_field = first_field
        self.second_field = second_field
        self.delimiter = delimiter
        self.new_field_name = new_field_name
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.target_line_numbers = target_line_numbers

    def run(self):
        try:
            count, error_count = processor.merge_fields_data(
                self.file_path,
                self.first_field,
                self.second_field,
                self.delimiter,
                self.new_field_name,
                encoding=self.encoding,
                sep=self.sep,
                quote=self.quote,
                target_line_numbers=self.target_line_numbers
            )
            self.finished.emit(count, error_count)
        except Exception as e:
            self.error.emit(str(e))


class MassRedactionWorker(QThread):
    finished = Signal(int, int) # count of rows redacted, error_count
    error = Signal(str)

    def __init__(self, file_path, csv_path, replacement_string, lf_match_field, csv_match_field, matched_fields, encoding=None, sep=None, quote=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.csv_path = csv_path
        self.replacement_string = replacement_string
        self.lf_match_field = lf_match_field
        self.csv_match_field = csv_match_field
        self.matched_fields = matched_fields
        self.encoding = encoding
        self.sep = sep
        self.quote = quote

    def run(self):
        try:
            count, error_count = processor.mass_redact_records(
                self.file_path,
                self.csv_path,
                self.replacement_string,
                self.lf_match_field,
                self.csv_match_field,
                self.matched_fields,
                encoding=self.encoding,
                sep=self.sep,
                quote=self.quote
            )
            self.finished.emit(count, error_count)
        except Exception as e:
            self.error.emit(str(e))
