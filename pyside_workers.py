from PySide6.QtCore import QThread, Signal
import processor
import traceback
import path_utility

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

    def __init__(self, file_path, cross_ref_path, output_path, keep_columns=None, encoding=None, sep=None, quote=None, target_line_numbers=None, pending_edits=None, new_columns=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.cross_ref_path = cross_ref_path
        self.output_path = output_path
        self.keep_columns = keep_columns
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.target_line_numbers = target_line_numbers
        self.pending_edits = pending_edits or {}
        self.new_columns = new_columns or []

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
                target_line_numbers=self.target_line_numbers,
                pending_edits=self.pending_edits,
                new_columns=self.new_columns
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


class PdfPrintWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(int, int)
    error = Signal(str)

    def __init__(self, opt_store, base_dir, root_out_dir, group_by_field=None, doc_id_metadata_map=None,
                 companion_format=None, companion_path=None, data_file_path=None, active_lines=None,
                 encoding=None, sep=None, quote=None, doc_id_field=None, generate_ocr=False, ocr_lang="eng", parent=None):
        super().__init__(parent)
        self.opt_store = opt_store
        self.base_dir = base_dir
        self.root_out_dir = root_out_dir
        self.group_by_field = group_by_field
        self.doc_id_metadata_map = doc_id_metadata_map or {}
        self.companion_format = companion_format
        self.companion_path = companion_path
        self.data_file_path = data_file_path
        self.active_lines = active_lines
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.doc_id_field = doc_id_field
        self.generate_ocr = generate_ocr
        self.ocr_lang = ocr_lang
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            import fitz
            import math
            import os
            import csv
            import traceback
            from opt_engine import resolve_full_image_path

            def sanitize_folder_name(name):
                if not name:
                    return "Unassigned"
                invalid = r'\/:*?"<>|'
                for char in invalid:
                    name = name.replace(char, "_")
                return name.strip()

            def compile_page_into_pdf(target_pdf, full_path, occ_idx):
                ext = os.path.splitext(full_path)[1].lower()
                try:
                    if ext == ".pdf":
                        src_pdf = fitz.open(full_path)
                        page_idx = occ_idx if len(src_pdf) > occ_idx else 0
                        
                        ocr_success = False
                        if self.generate_ocr:
                            try:
                                import pytesseract
                                from PIL import Image
                                import io
                                
                                page = src_pdf[page_idx]
                                pix = page.get_pixmap(dpi=150)
                                pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
                                
                                pdf_bytes = pytesseract.image_to_pdf_or_hocr(pil_img, extension='pdf', lang=self.ocr_lang)
                                ocr_pdf = fitz.open("pdf", pdf_bytes)
                                if len(ocr_pdf) > 0:
                                    target_pdf.insert_pdf(ocr_pdf)
                                    ocr_pdf.close()
                                    ocr_success = True
                            except Exception as ocr_ex:
                                print(f"OCR warning: Tesseract error or missing. Falling back to non-searchable PDF. Details: {str(ocr_ex)}")
                        
                        if not ocr_success:
                            target_pdf.insert_pdf(src_pdf, from_page=page_idx, to_page=page_idx)
                        src_pdf.close()
                        return True
                    else:
                        from PIL import Image
                        with Image.open(full_path) as pil_img:
                            total_frames = getattr(pil_img, "n_frames", 1)
                            frame_to_use = min(occ_idx, total_frames - 1)
                            pil_img.seek(frame_to_use)
                            
                            ocr_success = False
                            if self.generate_ocr:
                                try:
                                    import pytesseract
                                    pdf_bytes = pytesseract.image_to_pdf_or_hocr(pil_img, extension='pdf', lang=self.ocr_lang)
                                    ocr_pdf = fitz.open("pdf", pdf_bytes)
                                    if len(ocr_pdf) > 0:
                                        target_pdf.insert_pdf(ocr_pdf)
                                        ocr_pdf.close()
                                        ocr_success = True
                                except Exception as ocr_ex:
                                    print(f"OCR warning: Tesseract error or missing. Falling back to non-searchable PDF. Details: {str(ocr_ex)}")
                            
                            if not ocr_success:
                                rgb_img = pil_img.convert("RGB")
                                import io
                                pdf_io = io.BytesIO()
                                rgb_img.save(pdf_io, format="PDF")
                                pdf_io.seek(0)
                                src_pdf = fitz.open("pdf", pdf_io.read())
                                target_pdf.insert_pdf(src_pdf)
                                src_pdf.close()
                            return True
                except Exception as ex:
                    print(f"Failed to process page: {str(ex)}")
                    return False

            doc_ids = self.opt_store.doc_id_list
            total_docs = len(doc_ids)
            if total_docs == 0:
                self.finished.emit(0, 0)
                return

            # Respect active search filters and build metadata if active_lines is specified
            if self.active_lines is not None:
                self.progress.emit(0, 100, "Applying active search filters...")
                import processor
                headers, records = processor.read_specific_records(
                    self.data_file_path, self.active_lines, self.encoding, self.sep, self.quote
                )
                
                doc_id_idx = 0
                if self.doc_id_field and self.doc_id_field in headers:
                    doc_id_idx = headers.index(self.doc_id_field)
                else:
                    for cand in ("Control Number", "DocID", "BegBates", "Bates", "ID"):
                        for idx, h in enumerate(headers):
                            if cand.lower() in h.lower():
                                doc_id_idx = idx
                                break
                        else:
                            continue
                        break
                
                filtered_set = set()
                filtered_ordered = []
                for rec in records:
                    if doc_id_idx < len(rec):
                        doc_id = str(rec[doc_id_idx])
                        filtered_set.add(doc_id)
                        filtered_ordered.append(doc_id)
                        
                        # Build metadata mapping for this doc_id
                        row_dict = {}
                        for h_idx, h in enumerate(headers):
                            if h_idx < len(rec):
                                row_dict[h] = str(rec[h_idx])
                        self.doc_id_metadata_map[doc_id] = row_dict
                
                # Intersect with opt_store doc_ids preserving search order
                doc_ids = [d for d in filtered_ordered if d in self.opt_store.documents]
                total_docs = len(doc_ids)
                if total_docs == 0:
                    self.finished.emit(0, 0)
                    return

            # Grouping compiled PDF compilation
            use_grouping = bool(self.group_by_field)
            
            # Setup directory structure
            pdf_dir = os.path.join(self.root_out_dir, "PDF")
            os.makedirs(pdf_dir, exist_ok=True)

            docs_printed = 0
            errors = 0
            companion_records = []

            if use_grouping:
                grouped_docs = {}  # {group_name: [doc_ids]}
                for doc_id in doc_ids:
                    meta = self.doc_id_metadata_map.get(doc_id, {})
                    raw_val = meta.get(self.group_by_field, "")
                    group_val = sanitize_folder_name(str(raw_val))
                    if group_val not in grouped_docs:
                        grouped_docs[group_val] = []
                    grouped_docs[group_val].append(doc_id)
                
                sorted_groups = sorted(grouped_docs.keys())
                total_output_files = len(sorted_groups)
                pad_width = max(4, len(str(total_output_files)))

                for g_idx, group_name in enumerate(sorted_groups):
                    if self._is_cancelled:
                        break

                    self.progress.emit(docs_printed, total_output_files, f"Compiling Group PDF for {group_name}...")
                    
                    folder_idx = (g_idx // 1000) + 1
                    folder_name = f"IMAGE{str(folder_idx).zfill(pad_width)}"
                    subfolder_path = os.path.join(pdf_dir, folder_name)
                    os.makedirs(subfolder_path, exist_ok=True)

                    pdf_filename = f"{group_name}.pdf"
                    dest_pdf_path = os.path.join(subfolder_path, pdf_filename)

                    group_pdf = fitz.open()
                    doc_has_pages = False
                    first_doc_volume = None

                    # Sort docs in group strictly by DocID
                    group_docs_sorted = sorted(grouped_docs[group_name])
                    for doc_id in group_docs_sorted:
                        doc = self.opt_store.get_document(doc_id)
                        if not doc:
                            continue
                        
                        if first_doc_volume is None:
                            first_doc_volume = doc.volume_name

                        path_counts = {}
                        for img_path in doc.image_paths:
                            full_path = resolve_full_image_path(img_path, self.base_dir)
                            if not os.path.exists(full_path):
                                continue

                            ext = os.path.splitext(full_path)[1].lower()
                            occ_idx = path_counts.get(img_path, 0)
                            path_counts[img_path] = occ_idx + 1

                            if compile_page_into_pdf(group_pdf, full_path, occ_idx):
                                doc_has_pages = True

                    if doc_has_pages and len(group_pdf) > 0:
                        try:
                            group_pdf.save(dest_pdf_path)
                            docs_printed += 1
                            
                            rel_pdf_path = os.path.join("PDF", folder_name, pdf_filename).replace("/", "\\")
                            companion_records.append({
                                "doc_id": group_name,
                                "path": rel_pdf_path,
                                "volume": first_doc_volume or "VOL01",
                                "page_count": len(group_pdf)
                            })
                        except Exception:
                            errors += 1
                    else:
                        errors += 1

                    group_pdf.close()
            else:
                # No grouping
                total_output_files = len(doc_ids)
                pad_width = max(4, len(str(total_output_files)))
                sorted_doc_ids = sorted(doc_ids)

                for idx, doc_id in enumerate(sorted_doc_ids):
                    if self._is_cancelled:
                        break

                    self.progress.emit(docs_printed, total_output_files, f"Compiling PDF for {doc_id}...")

                    folder_idx = (idx // 1000) + 1
                    folder_name = f"IMAGE{str(folder_idx).zfill(pad_width)}"
                    subfolder_path = os.path.join(pdf_dir, folder_name)
                    os.makedirs(subfolder_path, exist_ok=True)

                    pdf_filename = f"{doc_id}.pdf"
                    dest_pdf_path = os.path.join(subfolder_path, pdf_filename)

                    doc_pdf = fitz.open()
                    path_counts = {}
                    doc_has_pages = False
                    doc = self.opt_store.get_document(doc_id)

                    if doc:
                        for img_path in doc.image_paths:
                            full_path = resolve_full_image_path(img_path, self.base_dir)
                            if not os.path.exists(full_path):
                                continue

                            ext = os.path.splitext(full_path)[1].lower()
                            occ_idx = path_counts.get(img_path, 0)
                            path_counts[img_path] = occ_idx + 1

                            if compile_page_into_pdf(doc_pdf, full_path, occ_idx):
                                doc_has_pages = True

                    if doc_has_pages and len(doc_pdf) > 0:
                        try:
                            doc_pdf.save(dest_pdf_path)
                            docs_printed += 1
                            
                            rel_pdf_path = os.path.join("PDF", folder_name, pdf_filename).replace("/", "\\")
                            companion_records.append({
                                "doc_id": doc_id,
                                "path": rel_pdf_path,
                                "volume": doc.volume_name or "VOL01",
                                "page_count": len(doc_pdf)
                            })
                        except Exception:
                            errors += 1
                    else:
                        errors += 1

                    doc_pdf.close()

            # Write companion file if format is specified
            if companion_records and self.companion_format and self.companion_path:
                fmt = self.companion_format.upper()
                if fmt == "CSV":
                    with open(self.companion_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["DocID", "File Path"])
                        for rec in companion_records:
                            writer.writerow([rec["doc_id"], rec["path"]])
                elif fmt == "LFP":
                    with open(self.companion_path, "w", newline="", encoding="utf-8") as f:
                        for rec in companion_records:
                            f.write(f"IM,{rec['doc_id']},D,{rec['volume']},{rec['path']},0,{rec['page_count']}\n")
                elif fmt == "OPT":
                    with open(self.companion_path, "w", newline="", encoding="utf-8") as f:
                        for rec in companion_records:
                            f.write(f'"{rec["doc_id"]}","{rec["volume"]}","{rec["path"]}","Y","","","{rec["page_count"]}"\n')

            self.finished.emit(docs_printed, errors)
        except Exception as e:
            self.error.emit(f"Export Error: {str(e)}\n{traceback.format_exc()}")


class VolumeMergeWorker(QThread):
    progress = Signal(str, str, int)  # status message, phase, progress_percent
    finished = Signal(int, int, int, str, str)  # total_volumes, unique_records, errors_caught, audit_log_path, output_file_path
    error = Signal(str)

    def __init__(self, files, doc_id_field, text_path_field, native_path_field, dup_mode, output_path, audit_path, parent=None):
        super().__init__(parent)
        self.files = files  # list of dicts: {"path": ..., "volume_name": ..., "encoding": ..., "sep": ..., "quote": ...}
        self.doc_id_field = doc_id_field
        self.text_path_field = text_path_field
        self.native_path_field = native_path_field
        self.dup_mode = dup_mode
        self.output_path = output_path
        self.audit_path = audit_path

    def run(self):
        import csv
        import os
        import path_utility

        errors_list = []  # items: (Error Type, Volume File Name, Volume File Path, Error Description)
        abort_merge = False
        file_row_counts = {}  # file_path -> row_count (to use for smooth Phase 2 progress)

        try:
            total_files = len(self.files)
            
            # 1. Phase 1: Dry-Run Pre-Flight Validation
            self.progress.emit("Phase 1: Pre-Flight Validation...", "validation", 5)
            
            # First, check headers in all files
            all_headers = []
            file_headers = {} # file_path -> list of headers
            
            for file_idx, file_info in enumerate(self.files):
                f_path = file_info["path"]
                vol_name = file_info["volume_name"]
                
                self.progress.emit(f"Checking headers for volume {file_idx + 1}/{total_files}: {vol_name}...", "validation", 5 + int(10 * file_idx / total_files))
                
                enc = file_info.get("encoding") or processor.get_encoding(f_path)
                sep = file_info.get("sep")
                qt = file_info.get("quote")
                if sep is None or qt is None:
                    d_sep, d_qt = processor.get_delimiters(f_path, enc)
                    sep = sep or d_sep
                    qt = qt or d_qt
                file_info["encoding"] = enc
                file_info["sep"] = sep
                file_info["quote"] = qt

                # Read header
                try:
                    with open(f_path, 'r', encoding=enc, errors='ignore') as f:
                        reader = csv.reader(f, delimiter=sep, quotechar=qt)
                        headers = next(reader)
                        headers = [h.lstrip('\ufeff').strip(qt + ' \t\r\n') for h in headers]
                        file_headers[f_path] = headers
                        
                        # Accumulate headers to build union master header
                        for h in headers:
                            if h not in all_headers:
                                all_headers.append(h)
                except Exception as e:
                    errors_list.append((
                        "Missing Field",
                        os.path.basename(f_path),
                        f_path,
                        f"Failed to read headers: {str(e)}"
                    ))
                    abort_merge = True
                    continue

                # Verify mapped fields exist in header
                h_lower = [h.lower() for h in headers]
                if self.doc_id_field.lower() not in h_lower:
                    errors_list.append((
                        "Missing Field",
                        os.path.basename(f_path),
                        f_path,
                        f"Required DocID field '{self.doc_id_field}' not found in header."
                    ))
                    abort_merge = True

                if self.text_path_field and self.text_path_field.lower() not in h_lower:
                    errors_list.append((
                        "Missing Field",
                        os.path.basename(f_path),
                        f_path,
                        f"Mapped Text Path field '{self.text_path_field}' not found in header."
                    ))
                    abort_merge = True

                if self.native_path_field and self.native_path_field.lower() not in h_lower:
                    errors_list.append((
                        "Missing Field",
                        os.path.basename(f_path),
                        f_path,
                        f"Mapped Native Path field '{self.native_path_field}' not found in header."
                    ))
                    abort_merge = True

            # Append MergedSourceVolume to headers list if not already present
            if "MergedSourceVolume" not in all_headers:
                all_headers.append("MergedSourceVolume")

            if abort_merge:
                self.write_audit_log(errors_list)
                self.error.emit(f"Merge aborted: One or more required mapped fields are missing from the load files' headers. Checked the audit log at {self.audit_path} for details.")
                return

            # Check duplicate DocIDs
            seen_doc_ids = set()
            duplicate_doc_ids = set()
            
            for file_idx, file_info in enumerate(self.files):
                f_path = file_info["path"]
                vol_name = file_info["volume_name"]
                enc = file_info["encoding"]
                sep = file_info["sep"]
                qt = file_info["quote"]
                headers = file_headers[f_path]
                
                self.progress.emit(f"Scanning records for duplicates in {vol_name}...", "validation", 15 + int(35 * file_idx / total_files))
                
                doc_idx = next((i for i, h in enumerate(headers) if h.lower() == self.doc_id_field.lower()), -1)
                row_count = 0

                try:
                    with open(f_path, 'r', encoding=enc, errors='ignore') as f:
                        reader = csv.reader(f, delimiter=sep, quotechar=qt)
                        next(reader)  # skip header
                        
                        line_num = 1
                        for row in reader:
                            line_num += 1
                            if not row:
                                continue
                            
                            row_count += 1
                            doc_id = row[doc_idx] if doc_idx < len(row) else ""
                            if not doc_id:
                                continue
                            
                            # Check duplicates
                            if doc_id in seen_doc_ids:
                                duplicate_doc_ids.add(doc_id)
                                errors_list.append((
                                    "Duplicate DocID",
                                    os.path.basename(f_path),
                                    f_path,
                                    f"Duplicate DocID '{doc_id}' found at line {line_num}."
                                ))
                                if self.dup_mode == "Strict":
                                    abort_merge = True
                            else:
                                seen_doc_ids.add(doc_id)
                except Exception as e:
                    errors_list.append((
                        "File Read Error",
                        os.path.basename(f_path),
                        f_path,
                        f"Error reading records: {str(e)}"
                    ))
                    abort_merge = True
                
                file_row_counts[f_path] = row_count

            if abort_merge:
                self.write_audit_log(errors_list)
                if self.dup_mode == "Strict" and duplicate_doc_ids:
                    self.error.emit(f"Merge aborted: Strict Mode enabled and duplicate DocIDs were detected. Checked the audit log at {self.audit_path} for details.")
                else:
                    self.error.emit(f"Merge aborted due to critical validation errors. Checked the audit log at {self.audit_path} for details.")
                return

            # 2. Phase 2: Consolidated Write / Merge
            self.progress.emit("Phase 2: Consolidating and Merging Load Files...", "merging", 50)
            
            merged_records = {}
            total_rows_to_merge = sum(file_row_counts.values())
            rows_processed = 0

            for file_info in self.files:
                f_path = file_info["path"]
                vol_name = file_info["volume_name"]
                enc = file_info["encoding"]
                sep = file_info["sep"]
                qt = file_info["quote"]
                headers = file_headers[f_path]
                
                doc_idx = next((i for i, h in enumerate(headers) if h.lower() == self.doc_id_field.lower()), -1)
                text_idx = next((i for i, h in enumerate(headers) if self.text_path_field and h.lower() == self.text_path_field.lower()), -1)
                native_idx = next((i for i, h in enumerate(headers) if self.native_path_field and h.lower() == self.native_path_field.lower()), -1)

                with open(f_path, 'r', encoding=enc, errors='ignore') as f:
                    reader = csv.reader(f, delimiter=sep, quotechar=qt)
                    next(reader) # skip header
                    
                    for row in reader:
                        if not row:
                            continue
                        
                        rows_processed += 1
                        if rows_processed % 1000 == 0 or rows_processed == total_rows_to_merge:
                            pct = 50 + int(40 * rows_processed / max(1, total_rows_to_merge))
                            self.progress.emit(f"Merging records: {rows_processed}/{total_rows_to_merge}...", "merging", pct)

                        doc_id = row[doc_idx] if doc_idx < len(row) else ""
                        if not doc_id:
                            continue

                        # Build a dictionary for the current record mapped to all_headers
                        rec_dict = {}
                        for h in all_headers:
                            h_idx = next((i for i, orig_h in enumerate(headers) if orig_h.lower() == h.lower()), -1)
                            val = row[h_idx] if (h_idx != -1 and h_idx < len(row)) else ""
                            rec_dict[h] = val

                        # Add MergedSourceVolume field
                        rec_dict["MergedSourceVolume"] = vol_name

                        # Path normalization
                        if self.text_path_field and self.text_path_field in rec_dict and rec_dict[self.text_path_field]:
                            rec_dict[self.text_path_field] = path_utility.normalize_path(rec_dict[self.text_path_field], vol_name)
                        if self.native_path_field and self.native_path_field in rec_dict and rec_dict[self.native_path_field]:
                            rec_dict[self.native_path_field] = path_utility.normalize_path(rec_dict[self.native_path_field], vol_name)

                        # Handle duplicate resolution
                        if doc_id in merged_records:
                            if self.dup_mode == "First-In Wins":
                                continue
                            elif self.dup_mode == "Last-In Wins":
                                merged_records[doc_id] = rec_dict
                            elif self.dup_mode == "Suffix Append":
                                base_new_doc_id = f"{doc_id}_{vol_name}"
                                new_doc_id = base_new_doc_id
                                counter = 1
                                while new_doc_id in merged_records:
                                    new_doc_id = f"{base_new_doc_id}_{counter:03d}"
                                    counter += 1
                                doc_id_master_key = next((h for h in all_headers if h.lower() == self.doc_id_field.lower()), self.doc_id_field)
                                rec_dict[doc_id_master_key] = new_doc_id
                                merged_records[new_doc_id] = rec_dict
                        else:
                            merged_records[doc_id] = rec_dict

            # Write merged output file
            out_ext = os.path.splitext(self.output_path)[1].lower()
            if out_ext == '.dat':
                out_sep = chr(20)
                out_qt = chr(254)
            else:
                out_sep = ','
                out_qt = '"'

            self.progress.emit("Writing consolidated load file...", "merging", 95)
            
            with open(self.output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=out_sep, quotechar=out_qt, quoting=csv.QUOTE_MINIMAL)
                writer.writerow(all_headers)
                for rec_dict in merged_records.values():
                    row_data = [rec_dict[h] for h in all_headers]
                    writer.writerow(row_data)

            # Write audit log CSV
            self.write_audit_log(errors_list)

            self.finished.emit(
                len(self.files),
                len(merged_records),
                len(errors_list),
                self.audit_path,
                self.output_path
            )

        except Exception as e:
            self.error.emit(f"Merge process error: {str(e)}\n{traceback.format_exc()}")

    def write_audit_log(self, errors_list):
        import csv
        with open(self.audit_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Error Type", "Volume File Name", "Volume File Path", "Error Description"])
            for err in errors_list:
                writer.writerow(err)


class ImageVolumeMergeWorker(QThread):
    progress = Signal(str, str, int)  # status message, phase, progress_percent
    finished = Signal(int, int, int, str, str)  # total_volumes, unique_records, errors_caught, audit_log_path, output_file_path
    error = Signal(str)

    def __init__(self, files, file_type, dup_mode, output_path, audit_path, parent=None):
        super().__init__(parent)
        self.files = files  # list of dicts: {"path": ..., "volume_name": ...}
        self.file_type = file_type  # "OPT" or "LFP"
        self.dup_mode = dup_mode
        self.output_path = output_path
        self.audit_path = audit_path

    def run(self):
        import csv
        import os
        import path_utility

        errors_list = []  # items: (Error Type, Volume File Name, Volume File Path, Error Description)
        abort_merge = False
        file_row_counts = {}  # file_path -> row_count (for smooth Phase 2 progress)

        try:
            total_files = len(self.files)
            
            # 1. Phase 1: Dry-Run Pre-Flight Validation
            self.progress.emit("Phase 1: Pre-Flight Validation...", "validation", 5)
            
            seen_bates = set()
            duplicate_bates = set()
            
            for file_idx, file_info in enumerate(self.files):
                f_path = file_info["path"]
                vol_name = file_info["volume_name"]
                
                self.progress.emit(f"Scanning pages for duplicates in {vol_name}...", "validation", 5 + int(45 * file_idx / total_files))
                
                row_count = 0
                try:
                    with open(f_path, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            
                            # Parse parts
                            if self.file_type == "OPT":
                                parts = [p.strip().strip('"') for p in line.split(',')]
                                if len(parts) < 3:
                                    errors_list.append((
                                        "Format Error",
                                        os.path.basename(f_path),
                                        f_path,
                                        f"Invalid OPT format at line {line_num}."
                                    ))
                                    continue
                                bates = parts[0]
                            else:  # LFP
                                parts = [p.strip() for p in line.split(',')]
                                if not parts or parts[0].upper() not in ("IM", "OF") or len(parts) < 5:
                                    continue
                                bates = parts[1]
                                
                            row_count += 1
                            
                            if bates in seen_bates:
                                duplicate_bates.add(bates)
                                errors_list.append((
                                    "Duplicate Image Key",
                                    os.path.basename(f_path),
                                    f_path,
                                    f"Duplicate Bates key '{bates}' found at line {line_num}."
                                ))
                                if self.dup_mode == "Strict":
                                    abort_merge = True
                            else:
                                seen_bates.add(bates)
                                
                except Exception as e:
                    errors_list.append((
                        "File Read Error",
                        os.path.basename(f_path),
                        f_path,
                        f"Error reading records: {str(e)}"
                    ))
                    abort_merge = True
                
                file_row_counts[f_path] = row_count

            if abort_merge:
                self.write_audit_log(errors_list)
                if self.dup_mode == "Strict" and duplicate_bates:
                    self.error.emit(f"Merge aborted: Strict Mode enabled and duplicate Bates keys were detected. Checked the audit log at {self.audit_path} for details.")
                else:
                    self.error.emit(f"Merge aborted due to critical validation errors. Checked the audit log at {self.audit_path} for details.")
                return

            # 2. Phase 2: Consolidated Write / Merge
            self.progress.emit("Phase 2: Consolidating and Merging Image Load Files...", "merging", 50)
            
            final_pages = {}
            order = []
            total_rows_to_merge = sum(file_row_counts.values())
            rows_processed = 0

            for file_info in self.files:
                f_path = file_info["path"]
                vol_name = file_info["volume_name"]
                
                try:
                    with open(f_path, 'r', encoding='utf-8', errors='replace') as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue
                            
                            if self.file_type == "OPT":
                                parts = [p.strip().strip('"') for p in line.split(',')]
                                if len(parts) < 3:
                                    continue
                                bates = parts[0]
                                volume = parts[1] or vol_name
                                img_path = parts[2]
                                doc_break = parts[3].upper() if len(parts) > 3 else "N"
                            else:  # LFP
                                parts = [p.strip() for p in line.split(',')]
                                if not parts or parts[0].upper() not in ("IM", "OF") or len(parts) < 5:
                                    continue
                                bates = parts[1]
                                doc_break = parts[2].upper()
                                volume = parts[3] or vol_name
                                img_path = parts[4].strip('"')
                                
                            rows_processed += 1
                            if rows_processed % 1000 == 0 or rows_processed == total_rows_to_merge:
                                pct = 50 + int(40 * rows_processed / max(1, total_rows_to_merge))
                                self.progress.emit(f"Merging image records: {rows_processed}/{total_rows_to_merge}...", "merging", pct)

                            # Normalize path
                            normalized_img_path = path_utility.normalize_path(img_path, vol_name)

                            page_dict = {
                                "bates": bates,
                                "volume": volume,
                                "img_path": normalized_img_path,
                                "doc_break": doc_break
                            }

                            # Duplicate resolution
                            if bates in final_pages:
                                if self.dup_mode == "First-In Wins":
                                    continue
                                elif self.dup_mode == "Last-In Wins":
                                    final_pages[bates] = page_dict
                                elif self.dup_mode == "Suffix Append":
                                    base_new_bates = f"{bates}_{vol_name}"
                                    new_bates = base_new_bates
                                    counter = 1
                                    while new_bates in final_pages:
                                        new_bates = f"{base_new_bates}_{counter:03d}"
                                        counter += 1
                                    page_dict["bates"] = new_bates
                                    order.append(new_bates)
                                    final_pages[new_bates] = page_dict
                            else:
                                order.append(bates)
                                final_pages[bates] = page_dict
                except Exception as e:
                    errors_list.append((
                        "Merge Error",
                        os.path.basename(f_path),
                        f_path,
                        f"Error parsing line {line_num}: {str(e)}"
                    ))

            # Recalculate document page counts for OPT if necessary
            doc_counts_dict = {}
            if self.file_type == "OPT":
                current_doc_bates = None
                current_doc_count = 0
                for bates in order:
                    page = final_pages[bates]
                    if page["doc_break"] == "Y":
                        if current_doc_bates:
                            doc_counts_dict[current_doc_bates] = current_doc_count
                        current_doc_bates = bates
                        current_doc_count = 1
                    else:
                        if current_doc_bates is None:
                            current_doc_bates = bates
                        current_doc_count += 1
                if current_doc_bates:
                    doc_counts_dict[current_doc_bates] = current_doc_count

            # Write master merged file
            self.progress.emit("Writing consolidated image load file...", "merging", 95)
            with open(self.output_path, 'w', encoding='utf-8', newline='') as f:
                for bates in order:
                    page = final_pages[bates]
                    if self.file_type == "OPT":
                        is_break = (page["doc_break"] == "Y")
                        cnt_str = str(doc_counts_dict.get(bates, "")) if is_break else ""
                        line = f'"{bates}","{page["volume"]}","{page["img_path"]}","{page["doc_break"]}","","","{cnt_str}"\n'
                    else:  # LFP
                        line = f'IM,{bates},{page["doc_break"]},{page["volume"]},{page["img_path"]}\n'
                    f.write(line)

            # Write audit log CSV
            self.write_audit_log(errors_list)

            self.finished.emit(
                len(self.files),
                len(final_pages),
                len(errors_list),
                self.audit_path,
                self.output_path
            )

        except Exception as e:
            self.error.emit(f"Merge process error: {str(e)}\n{traceback.format_exc()}")

    def write_audit_log(self, errors_list):
        import csv
        with open(self.audit_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Error Type", "Volume File Name", "Volume File Path", "Error Description"])
            for err in errors_list:
                writer.writerow(err)


class DataSplitWorker(QThread):
    progress = Signal(str, int)  # status message, progress_percent
    finished = Signal(int, list, str)  # total_splits, split_files_info, summary_report
    error = Signal(str)

    def __init__(self, file_path, encoding, sep, quote, root_vol_name, dest_dir, split_type, split_val, out_format, field_name=None, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.encoding = encoding
        self.sep = sep
        self.quote = quote
        self.root_vol_name = root_vol_name
        self.dest_dir = dest_dir
        self.split_type = split_type  # "Line Count", "File Size", "Field Value"
        self.split_val = split_val  # int/float value depending on split_type
        self.out_format = out_format  # "DAT" or "CSV"
        self.field_name = field_name  # field name if split_type is "Field Value"

    def run(self):
        import csv
        import os
        import traceback
        
        try:
            # First read the headers and count lines
            self.progress.emit("Counting records for split...", 5)
            
            # Read header
            with open(self.file_path, 'r', encoding=self.encoding, errors='ignore') as f:
                reader = csv.reader(f, delimiter=self.sep, quotechar=self.quote)
                headers = next(reader)
                headers = [h.lstrip('\ufeff').strip(self.quote + ' \t\r\n') for h in headers]
                
                # Count total rows
                total_rows = 0
                for row in reader:
                    if row:
                        total_rows += 1
            
            if total_rows == 0:
                self.error.emit("Data file contains no records to split.")
                return

            self.progress.emit("Splitting records...", 10)
            
            # Re-open file and read line-by-line
            with open(self.file_path, 'r', encoding=self.encoding, errors='ignore') as f:
                reader = csv.reader(f, delimiter=self.sep, quotechar=self.quote)
                next(reader)  # skip header
                
                ext = ".dat" if self.out_format == "DAT" else ".csv"
                out_sep = chr(20) if self.out_format == "DAT" else ","
                out_qt = chr(254) if self.out_format == "DAT" else '"'
                
                split_idx = 1
                current_records_count = 0
                current_file_size = 0
                current_field_value = None
                
                out_file = None
                csv_writer = None
                split_files_info = []  # list of tuples (filename, record_count, size_bytes)
                
                field_idx = -1
                if self.split_type == "Field Value" and self.field_name:
                    field_idx = next((i for i, h in enumerate(headers) if h.lower() == self.field_name.lower()), -1)
                
                def open_next_split():
                    nonlocal out_file, csv_writer, split_idx
                    filename = f"{self.root_vol_name}-{split_idx:04d}{ext}"
                    filepath = os.path.join(self.dest_dir, filename)
                    out_file = open(filepath, 'w', newline='', encoding='utf-8')
                    csv_writer = csv.writer(out_file, delimiter=out_sep, quotechar=out_qt, quoting=csv.QUOTE_MINIMAL)
                    csv_writer.writerow(headers)
                    split_idx += 1
                    return filepath, filename
                
                filepath, filename = open_next_split()
                
                rows_processed = 0
                for row in reader:
                    if not row:
                        continue
                        
                    # Check if split is needed
                    need_new_file = False
                    
                    if self.split_type == "Line Count":
                        if current_records_count >= self.split_val:
                            need_new_file = True
                    elif self.split_type == "File Size":
                        row_str = out_sep.join(row) + "\n"
                        row_bytes_len = len(row_str.encode('utf-8'))
                        if current_file_size + row_bytes_len > self.split_val * 1024 * 1024 and current_records_count > 0:
                            need_new_file = True
                    elif self.split_type == "Field Value" and field_idx != -1:
                        val = row[field_idx] if field_idx < len(row) else ""
                        if current_field_value is not None and val != current_field_value:
                            need_new_file = True
                        current_field_value = val
                        
                    if need_new_file:
                        out_file.close()
                        sz = os.path.getsize(filepath)
                        split_files_info.append((filename, current_records_count, sz))
                        
                        current_records_count = 0
                        current_file_size = 0
                        
                        filepath, filename = open_next_split()
                        
                    csv_writer.writerow(row)
                    current_records_count += 1
                    
                    row_str = out_sep.join(row) + "\n"
                    row_bytes_len = len(row_str.encode('utf-8'))
                    current_file_size += row_bytes_len
                    
                    rows_processed += 1
                    if rows_processed % 1000 == 0 or rows_processed == total_rows:
                        pct = 10 + int(85 * rows_processed / total_rows)
                        self.progress.emit(f"Processed {rows_processed}/{total_rows} records. Split {split_idx-1} in progress...", pct)
                
                if out_file:
                    out_file.close()
                    sz = os.path.getsize(filepath)
                    split_files_info.append((filename, current_records_count, sz))
            
            # Build Summary Report
            summary = "DATA FILE SPLIT SUMMARY REPORT\n"
            summary += "=================================\n"
            summary += f"Source File: {self.file_path}\n"
            summary += f"Split Type: {self.split_type}\n"
            summary += f"Split Target: {self.split_val}\n"
            summary += f"Total Splits Created: {len(split_files_info)}\n\n"
            summary += "Generated Volume Files:\n"
            for fn, rc, sz_bytes in split_files_info:
                sz_mb = sz_bytes / (1024 * 1024)
                summary += f" - {fn}: {rc:,} records, {sz_mb:.2f} MB\n"
                
            summary_path = os.path.join(self.dest_dir, f"{self.root_vol_name}_Split_Summary_Report.txt")
            with open(summary_path, 'w', encoding='utf-8') as sf:
                sf.write(summary)
                
            self.finished.emit(len(split_files_info), split_files_info, summary_path)
            
        except Exception as e:
            self.error.emit(f"Data file split error: {str(e)}\n{traceback.format_exc()}")


class ImageSplitWorker(QThread):
    progress = Signal(str, int)  # status message, progress_percent
    finished = Signal(int, list, str)  # total_splits, split_files_info, summary_report
    error = Signal(str)

    def __init__(self, file_path, file_type, root_vol_name, dest_dir, split_type, split_val, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_type = file_type  # "OPT" or "LFP"
        self.root_vol_name = root_vol_name
        self.dest_dir = dest_dir
        self.split_type = split_type  # "Line Count", "File Size", "Document Boundaries"
        self.split_val = split_val

    def run(self):
        import os
        import traceback
        
        try:
            self.progress.emit("Counting records for split...", 5)
            
            total_lines = 0
            with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    if line.strip():
                        total_lines += 1
                        
            if total_lines == 0:
                self.error.emit("Image load file is empty.")
                return

            self.progress.emit("Splitting image records...", 10)
            
            ext = ".opt" if self.file_type == "OPT" else ".lfp"
            split_idx = 1
            
            current_records_count = 0
            current_file_size = 0
            
            out_file = None
            split_files_info = []  # list of tuples (filename, record_count, size_bytes)
            
            pages = []
            with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
                for line_num, line in enumerate(f, 1):
                    line_str = line.strip()
                    if not line_str:
                        continue
                    
                    if self.file_type == "OPT":
                        parts = [p.strip().strip('"') for p in line_str.split(',')]
                        if len(parts) < 3:
                            continue
                        bates = parts[0]
                        volume = parts[1]
                        img_path = parts[2]
                        doc_break = parts[3].upper() if len(parts) > 3 else "N"
                        is_break = (doc_break == "Y")
                    else:  # LFP
                        parts = [p.strip() for p in line_str.split(',')]
                        if not parts or parts[0].upper() not in ("IM", "OF") or len(parts) < 5:
                            continue
                        bates = parts[1]
                        doc_break = parts[2].upper()
                        volume = parts[3]
                        img_path = parts[4].strip('"')
                        is_break = (doc_break in ("D", "Y", "B", "1"))
                        
                    pages.append({
                        "bates": bates,
                        "volume": volume,
                        "img_path": img_path,
                        "doc_break": doc_break,
                        "is_break": is_break,
                        "raw_line": line
                    })

            def open_next_split():
                nonlocal out_file, split_idx
                filename = f"{self.root_vol_name}-{split_idx:04d}{ext}"
                filepath = os.path.join(self.dest_dir, filename)
                out_file = open(filepath, 'w', encoding='utf-8')
                split_idx += 1
                return filepath, filename
                
            filepath, filename = open_next_split()
            split_pages = []
            
            def close_current_split():
                nonlocal out_file, split_pages, filepath, filename, current_records_count
                if not out_file:
                    return
                
                if self.file_type == "OPT" and split_pages:
                    doc_counts = {}
                    current_doc_bates = None
                    current_doc_count = 0
                    for page in split_pages:
                        if page["is_break"]:
                            if current_doc_bates:
                                doc_counts[current_doc_bates] = current_doc_count
                            current_doc_bates = page["bates"]
                            current_doc_count = 1
                        else:
                            if current_doc_bates is None:
                                current_doc_bates = page["bates"]
                            current_doc_count += 1
                    if current_doc_bates:
                        doc_counts[current_doc_bates] = current_doc_count
                        
                    for page in split_pages:
                        cnt_str = str(doc_counts.get(page["bates"], "")) if page["is_break"] else ""
                        line_out = f'"{page["bates"]}","{page["volume"]}","{page["img_path"]}","{page["doc_break"]}","","","{cnt_str}"\n'
                        out_file.write(line_out)
                else:
                    for page in split_pages:
                        out_file.write(page["raw_line"])
                        
                out_file.close()
                sz = os.path.getsize(filepath)
                split_files_info.append((filename, current_records_count, sz))
                
                split_pages = []
                current_records_count = 0
                
            rows_processed = 0
            for page in pages:
                need_new_file = False
                
                if self.split_type == "Line Count":
                    if current_records_count >= self.split_val:
                        need_new_file = True
                elif self.split_type == "File Size":
                    if current_file_size + len(page["raw_line"].encode('utf-8')) > self.split_val * 1024 * 1024 and current_records_count > 0:
                        need_new_file = True
                elif self.split_type == "Document Boundaries":
                    doc_breaks_in_split = sum(1 for p in split_pages if p["is_break"])
                    if page["is_break"] and doc_breaks_in_split >= self.split_val:
                        need_new_file = True
                elif self.split_type == "Volume":
                    if split_pages and split_pages[-1]["volume"] != page["volume"]:
                        need_new_file = True
                        
                if need_new_file:
                    close_current_split()
                    current_file_size = 0
                    filepath, filename = open_next_split()
                    
                split_pages.append(page)
                current_records_count += 1
                current_file_size += len(page["raw_line"].encode('utf-8'))
                
                rows_processed += 1
                if rows_processed % 1000 == 0 or rows_processed == len(pages):
                    pct = 10 + int(85 * rows_processed / len(pages))
                    self.progress.emit(f"Processed {rows_processed}/{len(pages)} pages. Split {split_idx-1} in progress...", pct)
                    
            close_current_split()
            
            # Build Summary Report
            summary = "IMAGE LOAD FILE SPLIT SUMMARY REPORT\n"
            summary += "=================================\n"
            summary += f"Source File: {self.file_path}\n"
            summary += f"File Type: {self.file_type}\n"
            summary += f"Split Type: {self.split_type}\n"
            summary += f"Split Target: {self.split_val}\n"
            summary += f"Total Splits Created: {len(split_files_info)}\n\n"
            summary += "Generated Volume Files:\n"
            for fn, rc, sz_bytes in split_files_info:
                sz_mb = sz_bytes / (1024 * 1024)
                summary += f" - {fn}: {rc:,} records, {sz_mb:.2f} MB\n"
                
            summary_path = os.path.join(self.dest_dir, f"{self.root_vol_name}_Split_Summary_Report.txt")
            with open(summary_path, 'w', encoding='utf-8') as sf:
                sf.write(summary)
                
            self.finished.emit(len(split_files_info), split_files_info, summary_path)
            
        except Exception as e:
            self.error.emit(f"Image load file split error: {str(e)}\n{traceback.format_exc()}")


class TiffRemediationWorker(QThread):
    progress = Signal(str, int)  # status message, progress_percent
    finished = Signal(int, int, str)  # remediated_files, errors_count, audit_log_path
    error = Signal(str)

    def __init__(self, load_file_path, file_type, volume_dirs, parent=None):
        super().__init__(parent)
        self.load_file_path = load_file_path
        self.file_type = file_type  # "OPT" or "LFP"
        self.volume_dirs = volume_dirs

    def run(self):
        import os
        import csv
        import shutil
        import traceback
        from datetime import datetime
        from PIL import Image, ImageSequence

        try:
            self.progress.emit("Reading image load file...", 5)
            rows = []
            
            # Read all lines
            with open(self.load_file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                for r in reader:
                    if r:
                        rows.append(r)

            # Analyze files referenced
            is_opt = (self.file_type.upper() == "OPT")
            
            # Find unique image files
            unique_images = {}  # relative_path -> list of (row_index, page_number)
            
            for idx, r in enumerate(rows):
                if is_opt:
                    if len(r) < 3:
                        continue
                    path = r[2].strip()
                else:
                    if len(r) < 5 or r[0].upper() not in ("IM", "OF"):
                        continue
                    path = r[4].strip().strip('"')
                
                if path.lower().endswith(('.tif', '.tiff')):
                    if path not in unique_images:
                        unique_images[path] = []
                    unique_images[path].append(idx)

            if not unique_images:
                self.finished.emit(0, 0, "")
                return

            remediated_count = 0
            errors_count = 0
            audit_records = []
            remediated_paths_map = {}
            
            # Directory of the load file to resolve relative paths
            load_file_dir = os.path.dirname(self.load_file_path)
            
            total_images = len(unique_images)
            for img_idx, (rel_path, row_indices) in enumerate(unique_images.items()):
                self.progress.emit(f"Scanning/Remediating {os.path.basename(rel_path)}...", int(5 + 90 * img_idx / total_images))
                
                # Resolve physical path
                phys_path = None
                # Try relative to load file
                test_path = os.path.normpath(os.path.join(load_file_dir, rel_path))
                if os.path.exists(test_path):
                    phys_path = test_path
                else:
                    # Search under volume_dirs
                    for v_dir in self.volume_dirs:
                        parts = rel_path.split(os.sep)
                        for start_idx in range(len(parts)):
                            sub_rel = os.path.join(*parts[start_idx:])
                            test_path2 = os.path.normpath(os.path.join(v_dir, sub_rel))
                            if os.path.exists(test_path2):
                                phys_path = test_path2
                                break
                        if phys_path:
                            break
                
                if not phys_path or not os.path.exists(phys_path):
                    errors_count += 1
                    audit_records.append({
                        "file": rel_path,
                        "status": "Error",
                        "action": "Skipped - File Not Found",
                        "original_compression": "N/A",
                        "pages": 0,
                        "backup_path": "N/A",
                        "error_details": "Physical file could not be found in any specified volume directories."
                    })
                    continue

                # Open TIFF to check compression, color, pages
                try:
                    with Image.open(phys_path) as img:
                        orig_comp = img.tag_v2.get(259, 1)
                        comp_str = {
                            1: "Uncompressed",
                            2: "CCITT 1D",
                            3: "Group 3 Fax",
                            4: "Group 4 Fax (CCITT G4)",
                            5: "LZW",
                            6: "OJPEG",
                            7: "JPEG",
                            32773: "PackBits"
                        }.get(orig_comp, f"Unknown ({orig_comp})")

                        # Check color
                        is_color = img.mode in ("RGB", "RGBA", "CMYK", "YCbCr")
                        
                        # Check multi-page
                        pages_count = 0
                        for _ in ImageSequence.Iterator(img):
                            pages_count += 1

                        is_multipage = (pages_count > 1)
                        
                        # Decide if remediation is needed
                        needs_remediation = False
                        if is_color:
                            needs_remediation = True
                        elif is_multipage:
                            needs_remediation = True
                        elif orig_comp != 4:
                            needs_remediation = True

                        if not needs_remediation:
                            audit_records.append({
                                "file": rel_path,
                                "status": "Clean",
                                "action": "None - Valid TIFF Format",
                                "original_compression": comp_str,
                                "pages": pages_count,
                                "backup_path": "N/A",
                                "error_details": ""
                            })
                            continue

                        # Perform Remediation
                        remediated_count += 1
                        
                        # Create backup
                        file_dir = os.path.dirname(phys_path)
                        backup_dir = os.path.join(file_dir, "_backup")
                        os.makedirs(backup_dir, exist_ok=True)
                        backup_file_path = os.path.join(backup_dir, os.path.basename(phys_path))
                        shutil.copy2(phys_path, backup_file_path)
                        
                        # Determine new target extensions and paths
                        base_no_ext, _ = os.path.splitext(phys_path)
                        rel_base_no_ext, _ = os.path.splitext(rel_path)
                        
                        new_files_mapping = []
                        
                        if is_multipage:
                            # Extract all pages
                            for p_idx, page in enumerate(ImageSequence.Iterator(img)):
                                zero_padded = f"{p_idx + 1:04d}"
                                ext = ".jpg" if is_color else ".tif"
                                
                                page_phys_path = f"{base_no_ext}_{zero_padded}{ext}"
                                page_rel_path = f"{rel_base_no_ext}_{zero_padded}{ext}"
                                
                                if is_color:
                                    if page.mode != "RGB":
                                        page = page.convert("RGB")
                                    page.save(page_phys_path, "JPEG", quality=90)
                                else:
                                    page.save(page_phys_path, "TIFF", compression="group4")
                                
                                new_files_mapping.append(page_rel_path)
                        else:
                            ext = ".jpg" if is_color else ".tif"
                            page_phys_path = f"{base_no_ext}{ext}"
                            page_rel_path = f"{rel_base_no_ext}{ext}"
                            
                            if is_color:
                                rgb_img = img.convert("RGB") if img.mode != "RGB" else img
                                rgb_img.save(page_phys_path, "JPEG", quality=90)
                            else:
                                img.save(page_phys_path, "TIFF", compression="group4")
                            
                            new_files_mapping.append(page_rel_path)
                            
                            if page_phys_path != phys_path and os.path.exists(phys_path):
                                os.remove(phys_path)

                        # Store mappings
                        remediated_paths_map[rel_path] = new_files_mapping

                        action_taken = f"Converted to JPG (Color)" if is_color else f"Compressed CCITT Group 4 (Bitonal)"
                        if is_multipage:
                            action_taken = f"Extracted {pages_count} pages to {ext.upper()} single-page files"

                        audit_records.append({
                            "file": rel_path,
                            "status": "Remediated",
                            "action": action_taken,
                            "original_compression": comp_str,
                            "pages": pages_count,
                            "backup_path": os.path.relpath(backup_file_path, load_file_dir),
                            "error_details": ""
                        })

                except Exception as img_ex:
                    errors_count += 1
                    audit_records.append({
                        "file": rel_path,
                        "status": "Error",
                        "action": "Failed Remediation",
                        "original_compression": "Unknown",
                        "pages": 0,
                        "backup_path": "N/A",
                        "error_details": f"TIFF processing exception: {str(img_ex)}"
                    })

            # Reconstruct load file rows supporting page expansion
            new_rows = []
            
            def increment_bates(bates_str, offset=1):
                import re
                match = list(re.finditer(r'\d+', bates_str))
                if not match:
                    return bates_str + f"_{offset}"
                last_match = match[-1]
                start, end = last_match.span()
                num_str = bates_str[start:end]
                val = int(num_str) + offset
                padded = f"{val:0{len(num_str)}d}"
                return bates_str[:start] + padded + bates_str[end:]

            path_occurrence_count = {}
            for r in rows:
                if is_opt:
                    if len(r) < 3:
                        new_rows.append(r)
                        continue
                    path = r[2].strip()
                    original_bates = r[0]
                    original_volume = r[1]
                else:
                    if len(r) < 5 or r[0].upper() not in ("IM", "OF"):
                        new_rows.append(r)
                        continue
                    path = r[4].strip().strip('"')
                    original_bates = r[1]
                    original_volume = r[3]

                if path in remediated_paths_map:
                    new_mappings = remediated_paths_map[path]
                    occ_idx = path_occurrence_count.get(path, 0)
                    path_occurrence_count[path] = occ_idx + 1

                    if occ_idx == 0:
                        # Update first page path
                        if is_opt:
                            r[2] = new_mappings[0]
                        else:
                            r[4] = new_mappings[0]
                        new_rows.append(r)

                        # Insert implicit subsequent pages
                        total_ref_rows = len(unique_images[path])
                        actual_pages_extracted = len(new_mappings)
                        if total_ref_rows < actual_pages_extracted:
                            for i in range(1, actual_pages_extracted):
                                new_bates = increment_bates(original_bates, i)
                                page_path = new_mappings[i]
                                if is_opt:
                                    # Bates, Volume, Path, IsDocBreak, FolderDocID, Reserved, PageCount
                                    new_r = [new_bates, original_volume, page_path, "", "", "", ""]
                                else:
                                    # IM, Bates, IsDocBreak, Volume, Path, PageOffset, PageCount
                                    new_r = ["IM", new_bates, "", original_volume, page_path, "", ""]
                                new_rows.append(new_r)
                    else:
                        # Explicit page mapping
                        if occ_idx < len(new_mappings):
                            target_path = new_mappings[occ_idx]
                        else:
                            target_path = new_mappings[-1]

                        if is_opt:
                            r[2] = target_path
                        else:
                            r[4] = target_path
                        new_rows.append(r)
                else:
                    new_rows.append(r)

            rows = new_rows

            # Save modified load file back
            self.progress.emit("Saving updated image load file...", 95)
            try:
                with open(self.load_file_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
            except PermissionError as p_err:
                raise PermissionError(
                    f"Could not save changes to the load file '{self.load_file_path}'. "
                    "Please ensure the file is closed in Excel or other programs and try again."
                ) from p_err

            # Generate Audit Log CSV (with fallback if locked)
            base_audit_name = f"{os.path.splitext(os.path.basename(self.load_file_path))[0]}_Tiff_Remediation_Audit_Log"
            audit_log_path = os.path.join(load_file_dir, f"{base_audit_name}.csv")
            suffix = 1
            while True:
                try:
                    with open(audit_log_path, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=["file", "status", "action", "original_compression", "pages", "backup_path", "error_details"])
                        writer.writeheader()
                        writer.writerows(audit_records)
                    break
                except PermissionError:
                    audit_log_path = os.path.join(load_file_dir, f"{base_audit_name}_{suffix}.csv")
                    suffix += 1
                except Exception as ex:
                    raise ex

            self.finished.emit(remediated_count, errors_count, audit_log_path)

        except Exception as e:
            self.error.emit(f"TIFF Remediation error: {str(e)}\n{traceback.format_exc()}")
