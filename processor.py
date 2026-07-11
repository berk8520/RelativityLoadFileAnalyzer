import polars as pl
import chardet
import os
import html
import re


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

def get_encoding(file_path):
    """Detects file encoding by reading the first 10k bytes."""
    with open(file_path, 'rb') as f:
        raw_data = f.read(10000)
        result = chardet.detect(raw_data)
        return result['encoding']

def get_delimiters(file_path):
    """Detects delimiters based on file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.dat':
        # Concordance standards: Thorn (chr20) and Quote (chr254)
        return chr(20), chr(254)
    else:
        # Default to CSV
        return ',', '"'

def analyze_load_file(file_path):
    """
    Analyzes the load file using Polars.
    Returns: (encoding, delimiter, row_count, schema_results)
    """
    print(f"PROCESSOR DEBUG: Analyzing {file_path}")
    encoding = get_encoding(file_path)
    sep, quote = get_delimiters(file_path)
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

        with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
            header_line = f.readline()
            if not header_line:
                raise Exception("File appears to be empty.")
            
            headers = [p.strip(quote) for p in header_line.strip().split(sep)]
            num_cols = len(headers)
            
            # Initialize accumulator lists
            max_lengths = [0] * num_cols
            longest_values = [""] * num_cols
            int_counts = [0] * num_cols
            float_counts = [0] * num_cols
            date_counts = [0] * num_cols
            non_empty_counts = [0] * num_cols

            for line in f:
                # Split and clean thorn/quotes
                parts = [p.strip(quote) for p in line.strip().split(sep)]
                if len(parts) != num_cols:
                    # Skip malformed lines (column count mismatch)
                    continue
                row_count += 1
                
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

def remap_headers(file_path, cross_ref_path, output_path):
    """
    Renames headers in a load file by streaming. Only the first line is modified.
    All data rows are passed through exactly as-is to ensure 100% integrity.
    """
    try:
        # 1. Load Cross-Reference Map
        rename_map = load_mapping_csv(cross_ref_path)

        # 2. Detect original file properties
        encoding = get_encoding(file_path)
        sep, quote = get_delimiters(file_path)

        rename_count = 0
        with open(file_path, 'r', encoding=encoding, errors='ignore') as fin:
            with open(output_path, 'w', encoding=encoding, newline='') as fout:
                # Process Header
                header_line = fin.readline()
                if not header_line:
                    return 0

                newline = "\r\n" if header_line.endswith("\r\n") else "\n"
                header_text = header_line.rstrip("\r\n")
                
                # Split, rename, and rejoin
                parts = [p.strip(quote) for p in header_text.split(sep)]
                new_parts = []
                for p in parts:
                    normalized_part = normalize_field_name(p)
                    if normalized_part in rename_map:
                        new_parts.append(f"{quote}{rename_map[normalized_part]}{quote}")
                        rename_count += 1
                    else:
                        new_parts.append(f"{quote}{p}{quote}")
                
                fout.write(sep.join(new_parts) + newline)

                # Stream Data Rows (100% Passthrough)
                for line in fin:
                    fout.write(line)
        
        return rename_count

    except Exception as e:
        raise Exception(f"Remapping failed: {str(e)}")
