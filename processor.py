import polars as pl
import chardet
import os
import html
import re

_audit_store = {}

def set_audit(file_path, line_num, error=None, modification=None):
    path_key = os.path.abspath(file_path).lower()
    if path_key not in _audit_store:
        _audit_store[path_key] = {}
    if line_num not in _audit_store[path_key]:
        _audit_store[path_key][line_num] = {"Error": "", "Modification": ""}
    if error is not None:
        _audit_store[path_key][line_num]["Error"] = error
    if modification is not None:
        _audit_store[path_key][line_num]["Modification"] = modification

def get_audit(file_path, line_num):
    path_key = os.path.abspath(file_path).lower()
    return _audit_store.get(path_key, {}).get(line_num, {"Error": "", "Modification": ""})

def clear_audit(file_path):
    path_key = os.path.abspath(file_path).lower()
    if path_key in _audit_store:
        _audit_store[path_key] = {}



def _normalize_mapping_column_name(column_name):
    return "".join(ch.lower() for ch in str(column_name) if ch.isalnum())


def normalize_field_name(field_name):
    normalized_name = html.unescape(str(field_name or "").strip())
    normalized_name = re.sub(r"\s*\(\d+\)\s*$", "", normalized_name)
    return normalized_name.strip()


def load_mapping_csv(cross_ref_path):
    """Load a mapping CSV as {original/source field -> target field}."""
    map_df = pl.read_csv(cross_ref_path)
    normalized_columns = {
        _normalize_mapping_column_name(column_name): column_name
        for column_name in map_df.columns
        if str(column_name).strip()
    }

    source_column = None
    for candidate in ("originalname", "source", "sourcefield", "originalfield", "currentname"):
        if candidate in normalized_columns:
            source_column = normalized_columns[candidate]
            break

    target_column = None
    for candidate in ("targetname", "target", "newfield", "destination", "mappedname"):
        if candidate in normalized_columns:
            target_column = normalized_columns[candidate]
            break

    if source_column is None or target_column is None:
        usable_columns = [column for column in map_df.columns if str(column).strip()]
        if len(usable_columns) < 2:
            raise ValueError("Mapping CSV must contain source/original and target columns.")

        first_column, second_column = usable_columns[:2]
        first_name = _normalize_mapping_column_name(first_column)
        second_name = _normalize_mapping_column_name(second_column)

        target_like_names = {"targetname", "target", "newfield", "destination", "mappedname"}
        source_like_names = {"originalname", "source", "sourcefield", "originalfield", "currentname"}

        if first_name in target_like_names and second_name not in target_like_names:
            source_column = second_column
            target_column = first_column
        elif first_name in source_like_names and second_name not in source_like_names:
            source_column = first_column
            target_column = second_column
        else:
            source_column = second_column
            target_column = first_column

    rename_map = {}
    for source_value, target_value in zip(map_df[source_column].to_list(), map_df[target_column].to_list()):
        source_name = normalize_field_name(source_value)
        target_name = html.unescape(str(target_value or "").strip())
        if source_name and target_name:
            rename_map[source_name] = target_name

    return rename_map

#def get_encoding(file_path):
#    """Detects file encoding by reading the first 10k bytes."""
#    with open(file_path, 'rb') as f:
#        raw_data = f.read(10000)
#        result = chardet.detect(raw_data)
#        return result['encoding']

def get_encoding(file_path):
    """Detects encoding, prioritizing UTF-8 with BOM and falling back to cp1252 if not valid UTF-8."""
    with open(file_path, 'rb') as f:
        raw = f.read(4)
        if raw.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        if raw.startswith(b'\xff\xfe\x00\x00') or raw.startswith(b'\x00\x00\xfe\xff'):
            return 'utf-32'
        if raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
            return 'utf-16'
        
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)
        
        try:
            raw_data.decode('utf-8')
            is_utf8 = True
        except UnicodeDecodeError:
            is_utf8 = False
            
        if not is_utf8:
            if b'\x14' in raw_data or b'\xfe' in raw_data:
                return 'cp1252'
                
        result = chardet.detect(raw_data)
        enc = result.get('encoding') if result else None
        
        if enc:
            if not is_utf8 and enc.lower() in ('ascii', 'utf-8'):
                return 'cp1252'
            return enc
            
        return 'utf-8' if is_utf8 else 'cp1252'

def get_delimiters(file_path, encoding=None):
    """Detects delimiters by checking extension AND verifying existence in file."""
    encoding = encoding or get_encoding(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    
    # 1. Start with the "Relativity/Concordance" standard
    candidates = [(chr(20), chr(254)), (',', '"'), (';', '"'), ('\t', '"')]
    
    if ext == '.dat':
        # Prioritize the Concordance standard, but verify it
        candidates.insert(0, (chr(20), chr(254)))
        
    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        line = f.readline()
        for sep, quote in candidates:
            if sep in line:
                return sep, quote
                
    # Fallback if detection fails
    return ',', '"'

def infer_and_validate_format(file_path):
    """
    Detects encoding (stripping BOM if present), reads the first line, 
    infers separator and quote based on extension, and validates if
    the inferred separator exists in the first line.
    Returns: (encoding, inferred_sep, inferred_quote, first_line, validation_passed)
    """
    encoding = get_encoding(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.csv':
        inferred_sep = ','
        inferred_quote = '"'
    elif ext == '.dat':
        inferred_sep = chr(20)
        inferred_quote = chr(254)
    else:
        inferred_sep = ','
        inferred_quote = '"'
        
    first_line = ""
    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            first_line = f.readline()
    except Exception:
        pass
        
    validation_passed = bool(first_line and inferred_sep in first_line)
    return encoding, inferred_sep, inferred_quote, first_line, validation_passed


def analyze_load_file(file_path, encoding=None, sep=None, quote=None):
    """
    Analyzes the load file using Polars.
    Returns: (encoding, delimiter, row_count, schema_results)
    """
    print(f"PROCESSOR DEBUG: Analyzing {file_path}")
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote
    print(f"PROCESSOR DEBUG: Encoding={encoding}, Sep={repr(sep)}, Quote={repr(quote)}")
    
    # Verify raw access
    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            head = f.read(100)
            print(f"PROCESSOR DEBUG: Raw file head: {repr(head)}")
    except Exception as e:
        print(f"PROCESSOR DEBUG: Raw read failed: {str(e)}")

    # Manual parsing for analysis using memory-efficient line-by-line streaming
    try:
        print(f"PROCESSOR DEBUG: Performing memory-efficient streaming parse for {file_path}...")
        import re
        
        # Date detection pattern
        DATE_REGEX = re.compile(
            r'^(\d{1,4}[-/.]\d{1,2}[-/.]\d{2,4})'  # separator dates (e.g. 12/31/2020, 2020-12-31)
            r'|'
            r'^((19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01]))$' # YYYYMMDD
        )

        headers = None
        num_cols = 0
        row_count = 0
        
        # Accumulators per column index
        max_lengths = []
        longest_values = []
        int_counts = []
        float_counts = []
        date_counts = []
        non_empty_counts = []

        with open(file_path, 'r', encoding=encoding, errors='ignore', newline='') as f:
            import csv
            reader = csv.reader(f, delimiter=sep, quotechar=quote)
            try:
                headers = next(reader)
            except StopIteration:
                raise Exception("File appears to be empty.")
            
            headers = [h.strip() for h in headers]
            num_cols = len(headers)
            
            # Initialize accumulator lists
            max_lengths = [0] * num_cols
            longest_values = [""] * num_cols
            int_counts = [0] * num_cols
            float_counts = [0] * num_cols
            date_counts = [0] * num_cols
            non_empty_counts = [0] * num_cols

            for parts in reader:
                row_count += 1
                
                # Pad/truncate parts to match num_cols
                if len(parts) < num_cols:
                    parts.extend([""] * (num_cols - len(parts)))
                elif len(parts) > num_cols:
                    parts = parts[:num_cols]
                
                for i in range(num_cols):
                    val = parts[i]
                    val_strip = val.strip()
                    if not val_strip:
                        continue
                    non_empty_counts[i] += 1
                    
                    # Byte length calculation
                    v_len = len(val.encode(encoding))
                    if v_len > max_lengths[i]:
                        max_lengths[i] = v_len
                        longest_values[i] = val
                    
                    # Check Integer
                    is_int = False
                    try:
                        int(val_strip)
                        int_counts[i] += 1
                        is_int = True
                    except ValueError:
                        pass
                    
                    # Check Float (Decimal)
                    if not is_int:
                        try:
                            float(val_strip)
                            float_counts[i] += 1
                        except ValueError:
                            pass
                    
                    # Check Date
                    if DATE_REGEX.search(val_strip):
                        date_counts[i] += 1

        print(f"PROCESSOR DEBUG: Streaming complete. Processed {row_count} rows across {num_cols} columns.")
        
        schema_results = []
        for i in range(num_cols):
            col = headers[i]
            col_lower = col.lower()
            max_len = max_lengths[i]
            display_val = longest_values[i]
            if len(display_val) > 250:
                display_val = display_val[:250] + "..."
            
            # Type Inference Heuristic
            rel_type = "Fixed-length Text"
            
            if max_len == 0:
                rel_type = ""
            elif any(kw in col_lower for kw in ["begdoc", "enddoc", "begattach", "endattach", "control number", 
                                                "starting number", "ending number", "family identifier", "begno", "endno"]):
                rel_type = "Fixed-length Text"
            elif non_empty_counts[i] > 0:
                int_ratio = int_counts[i] / non_empty_counts[i]
                float_ratio = (int_counts[i] + float_counts[i]) / non_empty_counts[i]
                date_ratio = date_counts[i] / non_empty_counts[i]
                
                if int_ratio > 0.9:
                    rel_type = "Whole Number"
                elif float_ratio > 0.9:
                    rel_type = "Decimal"
                elif date_ratio > 0.5 or (("date" in col_lower or "time" in col_lower) and date_ratio > 0.2):
                    rel_type = "Date"
                elif max_len > 256:
                    rel_type = "Long Text"
                else:
                    rel_type = "Fixed-length Text"
            else:
                rel_type = ""

            schema_results.append({
                "column": col,
                "type": rel_type,
                "max_len": max_len,
                "sample": display_val
            })

        # Add system/audit fields if not present in schema results
        for sf in ["Error", "Modification"]:
            exists = any(r["column"].lower() == sf.lower() for r in schema_results)
            if not exists:
                schema_results.append({
                    "column": sf,
                    "type": "Fixed-length Text",
                    "max_len": 0,
                    "sample": "",
                    "system_field": True
                })
            else:
                for r in schema_results:
                    if r["column"].lower() == sf.lower():
                        r["system_field"] = True

        sep_display = "DC4 (chr20)" if sep == chr(20) else f"'{sep}'"
        qual_display = "Thorn (chr254)" if quote == chr(254) else f"'{quote}'"
        delimiters_info = f"Sep: {sep_display} | Qual: {qual_display}"

        return encoding, delimiters_info, f"{row_count:,}", schema_results

    except Exception as e:
        print(f"PROCESSOR DEBUG: Manual parse failed: {str(e)}")
        raise Exception(f"Analysis failed: {str(e)}")


def parse_control_number(val):
    """
    Parses a control number string into (prefix, numeric_value, digits_count).
    Example: 'ABC000123' -> ('ABC', 123, 6)
             '12345'     -> ('', 12345, 5)
    Returns (None, None, 0) if parsing fails.
    """
    if not val:
        return None, None, 0
    val_str = str(val).strip()
    match = re.search(r'^(.*?)(0*(\d+))$', val_str)
    if match:
        prefix = match.group(1)
        full_num_str = match.group(2)
        num_val = int(match.group(3))
        return prefix, num_val, len(full_num_str)
    return None, None, 0


def find_sequence_gaps(file_path, start_col, end_col):
    """
    Finds gaps in control number sequences in a load file.
    Reads file using streaming to be memory efficient.
    Calculates gaps within a row (Start -> End) and between consecutive rows.
    Returns: List of dicts representing gaps:
             [{'prefix': 'ABC', 'gap_start': 'ABC00010', 'gap_end': 'ABC00015', 'missing_count': 4}]
    """
    encoding = get_encoding(file_path)
    sep, quote = get_delimiters(file_path)
    
    gaps = []
    
    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
        header_line = f.readline()
        if not header_line:
            return gaps
        
        headers = [p.strip(quote) for p in header_line.strip().split(sep)]
        if start_col not in headers or end_col not in headers:
            raise ValueError(f"Selected control number columns must exist in file headers.")
            
        start_idx = headers.index(start_col)
        end_idx = headers.index(end_col)
        
        prev_end_prefix = None
        prev_end_num = None
        prev_end_digits = 0
        
        row_num = 1
        for line in f:
            row_num += 1
            parts = [p.strip(quote) for p in line.strip().split(sep)]
            if len(parts) <= max(start_idx, end_idx):
                continue # skip malformed row
                
            start_val = parts[start_idx]
            end_val = parts[end_idx]
            
            s_pref, s_num, s_dig = parse_control_number(start_val)
            e_pref, e_num, e_dig = parse_control_number(end_val)
            
            if s_num is None or e_num is None:
                continue # Skip if parsing failed
            
            # Check gap between previous row's end and this row's start
            if prev_end_num is not None and prev_end_prefix == s_pref:
                if s_num > prev_end_num + 1:
                    gap_size = s_num - prev_end_num - 1
                    # Format gap start and end matching padding of the control numbers
                    fmt = f"{{:0{s_dig}d}}"
                    gap_start_str = s_pref + fmt.format(prev_end_num + 1)
                    gap_end_str = s_pref + fmt.format(s_num - 1)
                    gaps.append({
                        "prefix": s_pref,
                        "gap_start": gap_start_str,
                        "gap_end": gap_end_str,
                        "missing_count": gap_size
                    })
            
            # Check internal gap within the row (Start -> End)
            if s_pref == e_pref:
                if e_num < s_num:
                    # Inverted range? Let's skip or handle: usually indicates single document or error
                    pass
                elif e_num > s_num + 1:
                    # NOTE: A document range like ABC001 to ABC005 normally means pages ABC001, ABC002, ABC003, ABC004, ABC005 are in the document.
                    # Usually, there is no GAP between document start and end, but this depends on whether we check document boundaries or page sequences.
                    # In Relativity DAT, each row is a Document. ABC001 to ABC005 is a single document.
                    # Gaps are checked between the end of Doc N and the start of Doc N+1.
                    # Gaps are NOT checked between Start and End of the same row because those pages are present in that document.
                    pass
            
            prev_end_prefix = e_pref
            prev_end_num = e_num
            prev_end_digits = e_dig
            
    return gaps

def remap_headers(file_path, cross_ref_path, output_path, keep_columns=None, encoding=None, sep=None, quote=None, target_line_numbers=None):
    """
    Renames headers in a load file by streaming. Can also filter columns (keep_columns)
    and target specific rows (target_line_numbers).
    """
    import csv
    import tempfile
    import shutil
    import os

    try:
        # 1. Load Cross-Reference Map if provided
        rename_map = {}
        if cross_ref_path:
            rename_map = load_mapping_csv(cross_ref_path)

        # 2. Detect original file properties
        encoding = encoding or get_encoding(file_path)
        if sep is None or quote is None:
            det_sep, det_quote = get_delimiters(file_path)
            sep = sep or det_sep
            quote = quote or det_quote

        # Determine output properties
        is_xlsx = output_path.lower().endswith(".xlsx")
        is_csv = output_path.lower().endswith(".csv")
        
        if is_xlsx or is_csv:
            out_sep = ","
            out_quote = '"'
        else:
            out_sep = sep
            out_quote = quote

        # If xlsx, write to a temp CSV file first
        if is_xlsx:
            temp_fd, temp_csv_path = tempfile.mkstemp(suffix=".csv")
            os.close(temp_fd)
            write_path = temp_csv_path
        else:
            write_path = output_path

        target_set = set(target_line_numbers) if target_line_numbers is not None else None
        
        count = 0
        with open(file_path, 'r', encoding=encoding, newline='') as fin:
            reader = csv.reader(fin, delimiter=sep, quotechar=quote)
            
            with open(write_path, 'w', encoding=encoding, newline='') as fout:
                writer = csv.writer(fout, delimiter=out_sep, quotechar=out_quote, quoting=csv.QUOTE_ALL)
                
                try:
                    headers = next(reader)
                except StopIteration:
                    return 0

                # Map headers using rename_map
                mapped_headers = []
                for h in headers:
                    normalized = normalize_field_name(h)
                    if normalized in rename_map:
                        mapped_headers.append(rename_map[normalized])
                    else:
                        mapped_headers.append(h)

                # Determine which indices to keep
                keep_indices = None
                if keep_columns:
                    keep_indices = []
                    for col in keep_columns:
                        idx = -1
                        for i, h in enumerate(headers):
                            if h.lower() == col.lower():
                                idx = i
                                break
                        if idx != -1:
                            keep_indices.append(idx)
                    
                    out_headers = [mapped_headers[i] for i in keep_indices if i < len(mapped_headers)]
                    writer.writerow(out_headers)
                else:
                    writer.writerow(mapped_headers)

                line_num = 1
                for row in reader:
                    if target_set is not None and line_num not in target_set:
                        line_num += 1
                        continue

                    if keep_indices is not None:
                        out_row = [row[i] for i in keep_indices if i < len(row)]
                        if len(out_row) < len(keep_indices):
                            out_row.extend([""] * (len(keep_indices) - len(out_row)))
                        writer.writerow(out_row)
                    else:
                        writer.writerow(row)

                    count += 1
                    line_num += 1

        if is_xlsx:
            import polars as pl
            try:
                df = pl.read_csv(write_path)
                df.write_excel(output_path)
            except Exception as pl_err:
                try:
                    import pandas as pd
                    df = pd.read_csv(write_path, encoding=encoding)
                    df.to_excel(output_path, index=False)
                except Exception as pd_err:
                    raise Exception(f"Failed to convert output to Excel format: Polars err: {str(pl_err)}, Pandas err: {str(pd_err)}")
            finally:
                if os.path.exists(write_path):
                    os.remove(write_path)

        return count

    except Exception as e:
        raise Exception(f"Remapping failed: {str(e)}")

def append_field_data(file_path, new_field_name, val_type, static_val="", copy_field="", prefix="", padding=0, encoding=None, sep=None, quote=None, target_line_numbers=None):
    """
    Streams through the load file, appends a new column to the file, and populates it.
    val_type can be 'static', 'row_num', or 'copy'.
    """
    import csv
    import tempfile
    import shutil
    
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote
        
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), suffix=".tmp")
    os.close(temp_fd)
    
    count = 0
    error_count = 0
    target_set = set(target_line_numbers) if target_line_numbers is not None else None
    
    try:
        with open(file_path, 'r', encoding=encoding, newline='') as fin:
            reader = csv.reader(fin, delimiter=sep, quotechar=quote)
            
            with open(temp_path, 'w', encoding=encoding, newline='') as fout:
                writer = csv.writer(fout, delimiter=sep, quotechar=quote, quoting=csv.QUOTE_ALL)
                
                try:
                    headers = next(reader)
                except StopIteration:
                    return 0
                
                # Check if new_field_name already exists case-insensitively
                for h in headers:
                    if h.lower() == new_field_name.lower():
                        raise ValueError(f"Field '{new_field_name}' already exists in headers.")
                        
                # Find copy_field index if copying
                copy_idx = -1
                if val_type == "copy":
                    for i, h in enumerate(headers):
                        if h.lower() == copy_field.lower():
                            copy_idx = i
                            break
                    if copy_idx == -1:
                        raise ValueError(f"Source Field to copy '{copy_field}' not found in headers.")
                
                headers.append(new_field_name)
                writer.writerow(headers)
                
                line_num = 1
                for row in reader:
                    # Pad/truncate to original headers length (before new column)
                    original_len = len(headers) - 1
                    if len(row) < original_len:
                        row.extend([""] * (original_len - len(row)))
                    elif len(row) > original_len:
                        row = row[:original_len]
                        
                    if target_set is not None and line_num not in target_set:
                        row.append("") # new_field
                        writer.writerow(row)
                        line_num += 1
                        continue
                        
                    val_to_append = ""
                    error_msg = ""
                    try:
                        if val_type == "static":
                            val_to_append = static_val
                            count += 1
                        elif val_type == "row_num":
                            val_to_append = prefix + (str(line_num).zfill(padding) if padding > 0 else str(line_num))
                            count += 1
                        elif val_type == "copy":
                            if copy_idx < len(row):
                                val_to_append = row[copy_idx]
                                count += 1
                    except Exception as ex:
                        error_msg = f"Append error: {str(ex)}"
                        error_count += 1
                    
                    row.append(val_to_append)
                    if error_msg:
                        set_audit(file_path, line_num, error=error_msg, modification=f"Append: {new_field_name}")
                    elif val_to_append:
                        set_audit(file_path, line_num, error="", modification=f"Append: {new_field_name}")
                    
                    writer.writerow(row)
                    line_num += 1
                    
        shutil.copy2(temp_path, file_path)
        os.remove(temp_path)
        return count, error_count
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def merge_fields_data(file_path, first_field, second_field, delimiter, new_field_name, encoding=None, sep=None, quote=None, target_line_numbers=None):
    """
    Streams through the load file, merges two fields into a new appended field, and updates the file.
    """
    import csv
    import tempfile
    import shutil
    
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote
        
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), suffix=".tmp")
    os.close(temp_fd)
    
    count = 0
    target_set = set(target_line_numbers) if target_line_numbers is not None else None
    
    try:
        with open(file_path, 'r', encoding=encoding, newline='') as fin:
            reader = csv.reader(fin, delimiter=sep, quotechar=quote)
            
            with open(temp_path, 'w', encoding=encoding, newline='') as fout:
                writer = csv.writer(fout, delimiter=sep, quotechar=quote, quoting=csv.QUOTE_ALL)
                
                try:
                    headers = next(reader)
                except StopIteration:
                    return 0
                    
                # Check if new_field_name already exists case-insensitively
                for h in headers:
                    if h.lower() == new_field_name.lower():
                        raise ValueError(f"Field '{new_field_name}' already exists in headers.")
                        
                first_idx = -1
                second_idx = -1
                for i, h in enumerate(headers):
                    if h.lower() == first_field.lower():
                        first_idx = i
                    if h.lower() == second_field.lower():
                        second_idx = i
                        
                if first_idx == -1:
                    raise ValueError(f"First Field '{first_field}' not found in headers.")
                if second_idx == -1:
                    raise ValueError(f"Second Field '{second_field}' not found in headers.")
                    
                headers.append(new_field_name)
                writer.writerow(headers)
                
                line_num = 1
                error_count = 0
                for row in reader:
                    # Pad/truncate to original headers length (before new column)
                    original_len = len(headers) - 1
                    if len(row) < original_len:
                        row.extend([""] * (original_len - len(row)))
                    elif len(row) > original_len:
                        row = row[:original_len]
                        
                    if target_set is not None and line_num not in target_set:
                        row.append("") # new_field
                        writer.writerow(row)
                        line_num += 1
                        continue
                        
                    first_val = row[first_idx] if first_idx < len(row) else ""
                    second_val = row[second_idx] if second_idx < len(row) else ""
                    
                    merged_val = ""
                    error_msg = ""
                    try:
                        merged_val = f"{first_val}{delimiter}{second_val}"
                        count += 1
                    except Exception as ex:
                        error_msg = f"Merge error: {str(ex)}"
                        error_count += 1
                        
                    row.append(merged_val)
                    if error_msg:
                        set_audit(file_path, line_num, error=error_msg, modification=f"Merge: {new_field_name}")
                    elif merged_val:
                        set_audit(file_path, line_num, error="", modification=f"Merge: {new_field_name}")
                        
                    writer.writerow(row)
                    line_num += 1
                    
        shutil.copy2(temp_path, file_path)
        os.remove(temp_path)
        return count, error_count
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def read_records(file_path, start_line, limit, encoding=None, sep=None, quote=None):
    """
    Reads a subset of records from the load file starting at start_line (1-indexed row number) up to limit.
    Returns: (headers, records)
    """
    import csv
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote

    records = []
    headers = []
    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            reader = csv.reader(f, delimiter=sep, quotechar=quote)
            try:
                headers = next(reader)
            except StopIteration:
                return [], []
            
            # Save the count of the actual fields in the load file
            load_file_fields_count = len(headers)
            
            # Dynamically ensure system columns are in headers
            h_lower = [h.lower() for h in headers]
            if "error" not in h_lower:
                headers.append("Error")
            if "modification" not in h_lower:
                headers.append("Modification")
            
            skip_count = max(0, start_line - 1)
            for _ in range(skip_count):
                try:
                    next(reader)
                except StopIteration:
                    break
            
            current_line = start_line
            for _ in range(limit):
                try:
                    row = next(reader)
                    # Pad/truncate the row to the original headers length
                    if len(row) < load_file_fields_count:
                        row.extend([""] * (load_file_fields_count - len(row)))
                    elif len(row) > load_file_fields_count:
                        row = row[:load_file_fields_count]
                    
                    audit = get_audit(file_path, current_line)
                    row.append(audit["Error"])
                    row.append(audit["Modification"])
                    records.append(row)
                    current_line += 1
                except StopIteration:
                    break
    except Exception as e:
        print(f"PROCESSOR DEBUG: read_records failed: {str(e)}")
        raise e
    return headers, records

def read_specific_records(file_path, target_lines, encoding=None, sep=None, quote=None):
    """
    Reads specific 1-indexed record numbers (line numbers of data, i.e., 1 is first data row) from the load file.
    Returns: (headers, records)
    """
    import csv
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote

    target_set = set(target_lines)
    records = []
    headers = []
    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            reader = csv.reader(f, delimiter=sep, quotechar=quote)
            try:
                headers = next(reader)
            except StopIteration:
                return [], []
            
            # Save the count of the actual fields in the load file
            load_file_fields_count = len(headers)
            
            # Dynamically ensure system columns are in headers
            h_lower = [h.lower() for h in headers]
            if "error" not in h_lower:
                headers.append("Error")
            if "modification" not in h_lower:
                headers.append("Modification")
            
            line_num = 1
            max_target = max(target_set) if target_set else 0
            for row in reader:
                if line_num in target_set:
                    # Pad/truncate the row to the original headers length
                    if len(row) < load_file_fields_count:
                        row.extend([""] * (load_file_fields_count - len(row)))
                    elif len(row) > load_file_fields_count:
                        row = row[:load_file_fields_count]
                    
                    audit = get_audit(file_path, line_num)
                    row.append(audit["Error"])
                    row.append(audit["Modification"])
                    records.append(row)
                if line_num >= max_target:
                    break
                line_num += 1
    except Exception as e:
        print(f"PROCESSOR DEBUG: read_specific_records failed: {str(e)}")
        raise e
    return headers, records

def matches_wildcard(val, pattern):
    """
    Returns True if val matches pattern case-insensitively.
    If pattern contains no wildcards ('*' or '?'), performs case-insensitive substring match.
    Wildcard searches do not match values with a length of 0.
    """
    val_lower = str(val).lower()
    pat_lower = str(pattern).lower()
    
    has_wildcard = "*" in pat_lower or "?" in pat_lower
    if has_wildcard and len(val_lower.strip()) == 0:
        return False
        
    if not has_wildcard:
        return pat_lower in val_lower
    import fnmatch
    try:
        regex_str = fnmatch.translate(pat_lower)
        return bool(re.match(regex_str, val_lower))
    except Exception:
        return False

def search_records(file_path, config, encoding=None, sep=None, quote=None):
    """
    Searches the load file using streaming.
    Returns: List of 1-indexed row numbers that match the search configuration.
    """
    import csv
    import re
    
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote
        
    mode = config.get("mode", "full")
    query = config.get("query", "").strip()
    use_regex = config.get("regex", False)
    
    hits = []
    
    try:
        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            reader = csv.reader(f, delimiter=sep, quotechar=quote)
            try:
                headers = next(reader)
            except StopIteration:
                return []
                
            field_idx = -1
            is_audit_search = False
            audit_field = ""
            if mode == "field":
                field_name = config.get("field", "")
                if field_name.lower() in ("error", "modification"):
                    is_audit_search = True
                    audit_field = "Error" if field_name.lower() == "error" else "Modification"
                else:
                    for i, h in enumerate(headers):
                        if h.lower() == field_name.lower():
                            field_idx = i
                            break
                    if field_idx == -1:
                        raise ValueError(f"Field '{field_name}' not found in headers.")
            
            if use_regex:
                regex_pat = re.compile(query, re.IGNORECASE)
                
            ast = None
            if mode == "query":
                tokens = lex(query)
                parser = Parser(tokens)
                ast = parser.parse()
                
            line_num = 1
            for row in reader:
                matched = False
                if mode == "query":
                    row_dict = {}
                    for idx, h in enumerate(headers):
                        row_dict[h.lower()] = row[idx] if idx < len(row) else ""
                    audit = get_audit(file_path, line_num)
                    row_dict["error"] = audit["Error"]
                    row_dict["modification"] = audit["Modification"]
                    if ast.evaluate(row_dict):
                        matched = True
                elif mode == "field":
                    if is_audit_search:
                        audit = get_audit(file_path, line_num)
                        val = audit.get(audit_field, "")
                        if use_regex:
                            if regex_pat.search(val):
                                matched = True
                        else:
                            if matches_wildcard(val, query):
                                matched = True
                    else:
                        if field_idx < len(row):
                            val = row[field_idx]
                            if use_regex:
                                if regex_pat.search(val):
                                    matched = True
                            else:
                                if matches_wildcard(val, query):
                                    matched = True
                else: # mode == "full"
                    for cell in row:
                        if use_regex:
                            if regex_pat.search(cell):
                                matched = True
                                break
                        else:
                            if matches_wildcard(cell, query):
                                matched = True
                                break
                    if not matched:
                        # Also check in-memory audit store for full text searches
                        audit = get_audit(file_path, line_num)
                        if use_regex:
                            if regex_pat.search(audit["Error"]) or regex_pat.search(audit["Modification"]):
                                matched = True
                        else:
                            if matches_wildcard(audit["Error"], query) or matches_wildcard(audit["Modification"], query):
                                matched = True
                            
                if matched:
                    hits.append(line_num)
                line_num += 1
    except Exception as e:
        print(f"PROCESSOR DEBUG: search_records failed: {str(e)}")
        raise e
        
    return hits

def ensure_system_columns(headers):
    """
    Ensures that "Error" and "Modification" are in headers.
    Returns (updated_headers, error_idx, mod_idx)
    """
    h_lower = [h.lower() for h in headers]
    
    if "error" in h_lower:
        error_idx = h_lower.index("error")
    else:
        error_idx = len(headers)
        headers.append("Error")
        h_lower.append("error")
        
    if "modification" in h_lower:
        mod_idx = h_lower.index("modification")
    else:
        mod_idx = len(headers)
        headers.append("Modification")
        h_lower.append("modification")
        
    return headers, error_idx, mod_idx

def replace_field_data(file_path, field_name, find_pattern, replace_string, encoding=None, sep=None, quote=None, use_regex=False, target_line_numbers=None):
    """
    Streams through the load file, performs a find-and-replace on the specified field, and saves changes.
    Returns: (count of cells updated, error_count)
    """
    import csv
    import tempfile
    import shutil
    import re
    import fnmatch
    
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote
        
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), suffix=".tmp")
    os.close(temp_fd)
    
    count = 0
    error_count = 0
    target_set = set(target_line_numbers) if target_line_numbers is not None else None
    
    try:
        with open(file_path, 'r', encoding=encoding, newline='') as fin:
            reader = csv.reader(fin, delimiter=sep, quotechar=quote)
            
            with open(temp_path, 'w', encoding=encoding, newline='') as fout:
                writer = csv.writer(fout, delimiter=sep, quotechar=quote, quoting=csv.QUOTE_ALL)
                
                try:
                    headers = next(reader)
                except StopIteration:
                    return 0, 0
                    
                field_idx = -1
                for i, h in enumerate(headers):
                    if h.lower() == field_name.lower():
                        field_idx = i
                        break
                if field_idx == -1:
                    raise ValueError(f"Field '{field_name}' not found in headers.")
                    
                writer.writerow(headers)
                
                if use_regex:
                    regex_pat = re.compile(find_pattern)
                    
                line_num = 1
                for row in reader:
                    # Pad/truncate to original headers length
                    if len(row) < len(headers):
                        row.extend([""] * (len(headers) - len(row)))
                    elif len(row) > len(headers):
                        row = row[:len(headers)]
                        
                    if target_set is not None and line_num not in target_set:
                        writer.writerow(row)
                        line_num += 1
                        continue
                        
                    if field_idx < len(row):
                        old_val = row[field_idx]
                        try:
                            if use_regex:
                                # Overwrite entire field if regex matches
                                if regex_pat.search(old_val):
                                    new_val = replace_string
                                else:
                                    new_val = old_val
                            else:
                                # Overwrite entire field if wildcard pattern matches
                                if "*" in find_pattern or "?" in find_pattern:
                                    if fnmatch.fnmatchcase(old_val, find_pattern):
                                        new_val = replace_string
                                    else:
                                        new_val = old_val
                                else:
                                    new_val = old_val.replace(find_pattern, replace_string)
                                    
                            if new_val != old_val:
                                row[field_idx] = new_val
                                set_audit(file_path, line_num, error="", modification=f"Replace: {field_name}")
                                count += 1
                        except Exception as ex:
                            error_msg = f"Replace error: {str(ex)}"
                            set_audit(file_path, line_num, error=error_msg, modification=f"Replace: {field_name}")
                            error_count += 1
                            
                    writer.writerow(row)
                    line_num += 1
                    
        shutil.copy2(temp_path, file_path)
        os.remove(temp_path)
        return count, error_count
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def get_strftime_format(format_str):
    mapping = {
        "MM/DD/YYYY HH:MM:SS": "%m/%d/%Y %H:%M:%S",
        "YYYY-MM-DD HH:MM:SS": "%Y-%m-%d %H:%M:%S",
        "MM/DD/YYYY": "%m/%d/%Y",
        "YYYY-MM-DD": "%Y-%m-%d",
        "mm/dd/yyyy hh:mm:ss": "%m/%d/%Y %H:%M:%S",
        "yyyy-mm-dd hh:mm:ss": "%Y-%m-%d %H:%M:%S",
        "mm/dd/yyyy": "%m/%d/%Y",
        "yyyy-mm-dd": "%Y-%m-%d"
    }
    return mapping.get(format_str, format_str)

def validate_and_format_datetime(date_str, time_str, format_str):
    d_val = str(date_str or "").strip()
    t_val = str(time_str or "").strip()
    
    # Normalize common string representations of null/empty to empty string
    if d_val.lower() in ("none", "null", "nan", "empty", "undefined", ""):
        d_val = ""
    if t_val.lower() in ("none", "null", "nan", "empty", "undefined", ""):
        t_val = ""
        
    if not d_val and not t_val:
        return "", ""
        
    py_fmt = get_strftime_format(format_str)
    
    dt_date = parse_datetime_flexible(d_val)
    dt_time = parse_datetime_flexible(t_val)
    
    if dt_date and dt_time:
        dt = parse_datetime_flexible(d_val, t_val)
        if dt:
            try:
                return dt.strftime(py_fmt), ""
            except Exception as e:
                return "", f"Formatting error: {str(e)}"
        else:
            return "", f"Combined datetime parsing failed for '{d_val}' and '{t_val}'"
    else:
        return "", f"Invalid date/time value: '{d_val}' / '{t_val}'"

def parse_datetime_flexible(date_str, time_str=None):
    """
    Parses a date string and optional time string dynamically.
    Supports formats like YYYYMMDD, MM/DD/YYYY, YYYY-MM-DD, etc.
    """
    import datetime
    import re
    
    date_str = str(date_str).strip()
    if not date_str:
        return None
        
    combined = date_str
    if time_str:
        t_str = str(time_str).strip()
        if t_str:
            combined = f"{date_str} {t_str}"
            
    # Try using dateutil parser if available (which handles almost anything)
    try:
        from dateutil import parser
        return parser.parse(combined)
    except Exception:
        pass
        
    # Fallback: manual parsing for typical eDiscovery formats
    # Clean up separators
    cleaned = re.sub(r'[\s\-/.]+', ' ', combined).strip()
    
    # 1. Try YYYYMMDD
    if len(cleaned) == 8 and cleaned.isdigit():
        try:
            return datetime.datetime.strptime(cleaned, "%Y%m%d")
        except ValueError:
            pass
            
    # 2. Try various standard patterns
    formats = [
        "%m %d %Y", "%m %d %y",
        "%d %m %Y", "%d %m %y",
        "%Y %m %d",
        "%m %d %Y %H %M %S", "%m %d %Y %I %M %S %p",
        "%Y %m %d %H %M %S", "%Y %m %d %I %M %S %p",
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(cleaned, fmt)
        except ValueError:
            pass
            
    # 3. Try parsing without seconds or other parts
    try:
        import pandas as pd
        dt = pd.to_datetime(combined)
        if pd.notna(dt):
            return dt.to_pydatetime()
    except Exception:
        pass
        
    return None

def format_date_field(file_path, field_name, strftime_format, encoding=None, sep=None, quote=None, target_line_numbers=None):
    """
    Streams through the load file, formats date values in date_field using strftime_format.
    Returns: (count of dates formatted, error_count)
    """
    import csv
    import tempfile
    import shutil
    
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote
        
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), suffix=".tmp")
    os.close(temp_fd)
    
    count = 0
    error_count = 0
    target_set = set(target_line_numbers) if target_line_numbers is not None else None
    
    try:
        with open(file_path, 'r', encoding=encoding, newline='') as fin:
            reader = csv.reader(fin, delimiter=sep, quotechar=quote)
            
            with open(temp_path, 'w', encoding=encoding, newline='') as fout:
                writer = csv.writer(fout, delimiter=sep, quotechar=quote, quoting=csv.QUOTE_ALL)
                
                try:
                    headers = next(reader)
                except StopIteration:
                    return 0, 0
                    
                field_idx = -1
                for i, h in enumerate(headers):
                    if h.lower() == field_name.lower():
                        field_idx = i
                        break
                if field_idx == -1:
                    raise ValueError(f"Field '{field_name}' not found in headers.")
                    
                writer.writerow(headers)
                
                line_num = 1
                for row in reader:
                    # Pad/truncate to original headers length
                    if len(row) < len(headers):
                        row.extend([""] * (len(headers) - len(row)))
                    elif len(row) > len(headers):
                        row = row[:len(headers)]
                        
                    if target_set is not None and line_num not in target_set:
                        writer.writerow(row)
                        line_num += 1
                        continue
                        
                    if field_idx < len(row):
                        old_val = row[field_idx]
                        if old_val.strip():
                            dt = parse_datetime_flexible(old_val)
                            if dt:
                                try:
                                    py_fmt = get_strftime_format(strftime_format)
                                    new_val = dt.strftime(py_fmt)
                                    if new_val != old_val:
                                        row[field_idx] = new_val
                                        set_audit(file_path, line_num, error="", modification=f"Format Date: {field_name}")
                                        count += 1
                                except Exception as ex:
                                    error_msg = f"Format error: {str(ex)}"
                                    set_audit(file_path, line_num, error=error_msg, modification=f"Format Date: {field_name}")
                                    error_count += 1
                            else:
                                error_msg = f"Invalid date: '{old_val}'"
                                set_audit(file_path, line_num, error=error_msg, modification=f"Format Date: {field_name}")
                                error_count += 1
                                
                    writer.writerow(row)
                    line_num += 1
                    
        shutil.copy2(temp_path, file_path)
        os.remove(temp_path)
        return count, error_count
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def merge_date_time_fields(file_path, date_field, time_field, new_field_name, strftime_format, encoding=None, sep=None, quote=None, target_line_numbers=None):
    """
    Streams through the load file, merges date_field and time_field, and appends a new_field_name formatted with strftime_format.
    Returns: (count, error_count)
    """
    import csv
    import tempfile
    import shutil
    
    encoding = encoding or get_encoding(file_path)
    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path)
        sep = sep or det_sep
        quote = quote or det_quote
        
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), suffix=".tmp")
    os.close(temp_fd)
    
    count = 0
    error_count = 0
    target_set = set(target_line_numbers) if target_line_numbers is not None else None
    
    try:
        with open(file_path, 'r', encoding=encoding, newline='') as fin:
            reader = csv.reader(fin, delimiter=sep, quotechar=quote)
            
            with open(temp_path, 'w', encoding=encoding, newline='') as fout:
                writer = csv.writer(fout, delimiter=sep, quotechar=quote, quoting=csv.QUOTE_ALL)
                
                try:
                    headers = next(reader)
                except StopIteration:
                    return 0, 0
                    
                # Check if new_field_name already exists case-insensitively
                for h in headers:
                    if h.lower() == new_field_name.lower():
                        raise ValueError(f"Field '{new_field_name}' already exists in headers.")
                        
                date_idx = -1
                time_idx = -1
                for i, h in enumerate(headers):
                    if h.lower() == date_field.lower():
                        date_idx = i
                    if h.lower() == time_field.lower():
                        time_idx = i
                        
                if date_idx == -1:
                    raise ValueError(f"Date Field '{date_field}' not found in headers.")
                if time_idx == -1:
                    raise ValueError(f"Time Field '{time_field}' not found in headers.")
                    
                headers.append(new_field_name)
                writer.writerow(headers)
                
                line_num = 1
                for row in reader:
                    # Pad/truncate to original headers length (before new column)
                    original_len = len(headers) - 1
                    if len(row) < original_len:
                        row.extend([""] * (original_len - len(row)))
                    elif len(row) > original_len:
                        row = row[:original_len]
                        
                    if target_set is not None and line_num not in target_set:
                        row.append("") # new_field
                        writer.writerow(row)
                        line_num += 1
                        continue
                        
                    date_val = row[date_idx] if date_idx < len(row) else ""
                    time_val = row[time_idx] if time_idx < len(row) else ""
                    
                    merged_val, error_msg = validate_and_format_datetime(date_val, time_val, strftime_format)
                    
                    if error_msg:
                        error_count += 1
                        row.append(merged_val)
                        set_audit(file_path, line_num, error=error_msg, modification="Merge Date Time")
                    elif merged_val:
                        count += 1
                        row.append(merged_val)
                        set_audit(file_path, line_num, error="", modification="Merge Date Time")
                    else:
                        row.append("")
                        
                    writer.writerow(row)
                    line_num += 1
                    
        shutil.copy2(temp_path, file_path)
        os.remove(temp_path)
        return count, error_count
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e

def mass_redact_records(file_path, csv_path, replacement_string, lf_match_field, csv_match_field, matched_fields, encoding=None, sep=None, quote=None):
    import csv
    import tempfile
    import shutil

    # 1. Determine safe encoding for main load file.
    safe_encoding = encoding or get_encoding(file_path)

    if sep is None or quote is None:
        det_sep, det_quote = get_delimiters(file_path, safe_encoding)
        sep = sep or det_sep
        quote = quote or det_quote

    # 2. Auto-detect properties for cross-reference file (csv_path) independently
    csv_encoding = get_encoding(csv_path)
    csv_sep, csv_quote = get_delimiters(csv_path, csv_encoding)

    # Use csv_encoding when opening the CSV/DAT match file
    csv_keys = set()
    try:
        with open(csv_path, 'r', encoding=csv_encoding, newline='', errors='ignore') as f:
            reader = csv.reader(f, delimiter=csv_sep, quotechar=csv_quote)
            csv_headers = next(reader)
            csv_cols_lower = [c.lower() for c in csv_headers]
            if csv_match_field.lower() not in csv_cols_lower:
                raise ValueError(f"Match field '{csv_match_field}' not found in cross-reference headers.")
            csv_match_idx = csv_cols_lower.index(csv_match_field.lower())
            
            for row in reader:
                if csv_match_idx < len(row):
                    val = row[csv_match_idx]
                    if val is not None and val != "":
                        csv_keys.add(str(val).strip().lower())
    except Exception as e:
        raise Exception(f"Failed to read cross-reference file: {str(e)}")

    # 3. Use safe_encoding for the main load file as well
    temp_fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(file_path), suffix=".tmp")
    os.close(temp_fd)
    
    count = 0
    error_count = 0
    try:
        with open(file_path, 'r', encoding=safe_encoding, newline='') as fin:
            reader = csv.reader(fin, delimiter=sep, quotechar=quote)
            
            with open(temp_path, 'w', encoding=safe_encoding, newline='') as fout:
                writer = csv.writer(fout, delimiter=sep, quotechar=quote, quoting=csv.QUOTE_ALL)
                
                try:
                    headers = next(reader)
                except StopIteration:
                    return 0, 0
                    
                lf_match_idx = -1
                for idx, h in enumerate(headers):
                    if h.lower() == lf_match_field.lower():
                        lf_match_idx = idx
                        break
                        
                if lf_match_idx == -1:
                    raise ValueError(f"Load file column '{lf_match_field}' not found in load file headers.")
                
                header_indices = {h.lower().strip(): idx for idx, h in enumerate(headers)}
                fields_to_replace_indices = []
                for field in matched_fields:
                    f_lower = field.lower().strip()
                    if f_lower in header_indices:
                        fields_to_replace_indices.append(header_indices[f_lower])
                
                writer.writerow(headers)
                
                line_num = 1
                for row in reader:
                    # Maintain row integrity
                    if len(row) < len(headers):
                        row.extend([""] * (len(headers) - len(row)))
                    elif len(row) > len(headers):
                        row = row[:len(headers)]
                        
                    if lf_match_idx < len(row):
                        lf_val = str(row[lf_match_idx]).strip().lower()
                        if lf_val in csv_keys:
                            row_modified = False
                            error_msg = ""
                            for f_idx in fields_to_replace_indices:
                                if f_idx < len(row):
                                    try:
                                        row[f_idx] = replacement_string
                                        row_modified = True
                                    except Exception as ex:
                                        error_msg = f"Redaction error: {str(ex)}"
                                        error_count += 1
                            if row_modified:
                                count += 1
                                
                            if error_msg:
                                set_audit(file_path, line_num, error=error_msg, modification="Mass Field Redaction")
                            elif row_modified:
                                set_audit(file_path, line_num, error="", modification=f"Redacted: {', '.join(matched_fields)}")
                                
                    writer.writerow(row)
                    line_num += 1
                    
        shutil.copy2(temp_path, file_path)
        os.remove(temp_path)
        return count, error_count
    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise e
# --- SQL-like Query Lexer, Parser, and AST ---

class Token:
    def __init__(self, type_, value, pos=0):
        self.type = type_
        self.value = value
        self.pos = pos
    def __repr__(self):
        return f"Token({self.type}, {self.value})"

def lex(query):
    import re
    tokens = []
    i = 0
    n = len(query)
    while i < n:
        start_pos = i
        if query[i].isspace():
            i += 1
            continue
        if query[i] == '(':
            tokens.append(Token('LPAREN', '(', start_pos))
            i += 1
            continue
        if query[i] == ')':
            tokens.append(Token('RPAREN', ')', start_pos))
            i += 1
            continue
        if query[i] == '[':
            j = query.find(']', i)
            if j == -1:
                raise ValueError(f"Unclosed square bracket|{start_pos}|{n}")
            field_name = query[i+1:j].strip()
            tokens.append(Token('FIELD', field_name, start_pos))
            i = j + 1
            continue
        if query[i] == '"':
            j = query.find('"', i+1)
            if j == -1:
                raise ValueError(f"Unclosed double quote|{start_pos}|{n}")
            str_val = query[i+1:j]
            tokens.append(Token('STRING', str_val, start_pos))
            i = j + 1
            continue
        if query[i:i+2] == '!=':
            tokens.append(Token('OP', '!=', start_pos))
            i += 2
            continue
        if query[i] == '=':
            tokens.append(Token('OP', '=', start_pos))
            i += 1
            continue
        
        match = re.match(r'^[a-zA-Z]+', query[i:])
        if match:
            word = match.group(0)
            word_upper = word.upper()
            if word_upper in ('AND', 'OR', 'NOT'):
                tokens.append(Token(word_upper, word_upper, start_pos))
            elif word_upper in ('LIKE', 'CONTAINS'):
                tokens.append(Token('OP', word_upper, start_pos))
            elif word_upper == 'IS':
                remainder = query[i + len(word):]
                match_set = re.match(r'^\s*([a-zA-Z]+)', remainder)
                if match_set and match_set.group(1).upper() == "SET":
                    tokens.append(Token('OP', 'IS SET', start_pos))
                    i += len(word) + len(match_set.group(0))
                    continue
                else:
                    raise ValueError(f"Unexpected keyword '{word}'|{start_pos}|{start_pos + len(word)}")
            else:
                raise ValueError(f"Unexpected keyword '{word}'|{start_pos}|{start_pos + len(word)}")
            i += len(word)
            continue
            
        raise ValueError(f"Unexpected character '{query[i]}'|{start_pos}|{start_pos+1}")
    return tokens

class Node:
    pass

class BinOpNode(Node):
    def __init__(self, left, op, right, left_pos=0):
        self.left = left
        self.op = op
        self.right = right
        self.left_pos = left_pos
    def evaluate(self, row_dict):
        import re
        val = str(row_dict.get(self.left.lower(), "")).lower()
        target = self.right.lower()
        if self.op == '=':
            return val == target
        elif self.op == '!=':
            return val != target
        elif self.op == 'CONTAINS':
            return target in val
        elif self.op == 'LIKE':
            import fnmatch
            return fnmatch.fnmatchcase(val, target)
        elif self.op == 'IS SET':
            return len(val.strip()) > 0
        return False

class AndNode(Node):
    def __init__(self, left, right):
        self.left = left
        self.right = right
    def evaluate(self, row_dict):
        return self.left.evaluate(row_dict) and self.right.evaluate(row_dict)

class OrNode(Node):
    def __init__(self, left, right):
        self.left = left
        self.right = right
    def evaluate(self, row_dict):
        return self.left.evaluate(row_dict) or self.right.evaluate(row_dict)

class NotNode(Node):
    def __init__(self, expr):
        self.expr = expr
    def evaluate(self, row_dict):
        return not self.expr.evaluate(row_dict)

class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self):
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_type=None):
        tok = self.peek()
        if not tok:
            raise ValueError(f"Unexpected end of query|{len(self.tokens)}|{len(self.tokens)}")
        if expected_type and tok.type != expected_type:
            raise ValueError(f"Expected token of type {expected_type}, got {tok.type}|{tok.pos}|{tok.pos + len(tok.value)}")
        self.pos += 1
        return tok

    def parse(self):
        node = self.expr_or()
        if self.peek() is not None:
            tok = self.peek()
            raise ValueError(f"Unexpected token '{tok.value}' at end of query|{tok.pos}|{tok.pos + len(tok.value)}")
        return node

    def expr_or(self):
        node = self.expr_and()
        while True:
            tok = self.peek()
            if tok and tok.type == 'OR':
                self.consume()
                right = self.expr_and()
                node = OrNode(node, right)
            else:
                break
        return node

    def expr_and(self):
        node = self.expr_not()
        while True:
            tok = self.peek()
            if tok and tok.type == 'AND':
                self.consume()
                right = self.expr_not()
                node = AndNode(node, right)
            else:
                break
        return node

    def expr_not(self):
        tok = self.peek()
        if tok and tok.type == 'NOT':
            self.consume()
            expr = self.expr_not()
            return NotNode(expr)
        return self.primary()

    def primary(self):
        tok = self.peek()
        if not tok:
            raise ValueError(f"Unexpected end of query in primary expression|{len(self.tokens)}|{len(self.tokens)}")
            
        if tok.type == 'LPAREN':
            self.consume()
            node = self.expr_or()
            self.consume('RPAREN')
            return node
            
        if tok.type == 'FIELD':
            field_tok = self.consume()
            op_tok = self.consume('OP')
            if op_tok.value == "IS SET":
                return BinOpNode(field_tok.value, op_tok.value, "", field_tok.pos)
            val_tok = self.consume('STRING')
            return BinOpNode(field_tok.value, op_tok.value, val_tok.value, field_tok.pos)
            
        raise ValueError(f"Unexpected token '{tok.value}' in primary expression|{tok.pos}|{tok.pos + len(tok.value)}")

def get_query_fields_with_spans(node):
    fields = set()
    if isinstance(node, BinOpNode):
        fields.add((node.left.lower(), node.left_pos, node.left_pos + len(node.left) + 2))
    elif isinstance(node, NotNode):
        fields.update(get_query_fields_with_spans(node.expr))
    elif isinstance(node, (AndNode, OrNode)):
        fields.update(get_query_fields_with_spans(node.left))
        fields.update(get_query_fields_with_spans(node.right))
    return fields

def validate_query(query, headers=None):
    """
    Validates a SQL-like query string.
    Returns: (is_valid, error_message, start_pos, end_pos)
    """
    try:
        tokens = lex(query)
        parser = Parser(tokens)
        ast = parser.parse()
        if headers is not None:
            fields = get_query_fields_with_spans(ast)
            headers_lower = {h.lower() for h in headers}
            headers_lower.add("error")
            headers_lower.add("modification")
            for f, start_pos, end_pos in fields:
                if f not in headers_lower:
                    return False, f"Field '[{f}]' does not exist in schema.", start_pos, end_pos
        return True, "", -1, -1
    except Exception as e:
        err_msg = str(e)
        if "|" in err_msg:
            parts = err_msg.split("|")
            return False, parts[0], int(parts[1]), int(parts[2])
        return False, err_msg, 0, len(query)
