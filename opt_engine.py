"""
OptDocument Engine for Relativity Load File Analyzer.
Supports high-performance read/write operations for OPT, LFP, DII, and SMI image load files,
and maintains an O(1) dictionary lookup structure for 500k+ record sets.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Iterator

@dataclass
class OptDocument:
    """
    Central document model representing an image document and its page collection.
    """
    doc_id: str
    volume_name: str = ""
    box: str = ""
    folder: str = ""
    page_count: int = 0
    image_paths: List[str] = field(default_factory=list)
    bates_list: List[str] = field(default_factory=list)


class OptDocumentStore:
    """
    Dictionary store providing O(1) lookups for OptDocument objects by DocID,
    along with helper cross-referencing and lookup methods.
    """
    def __init__(self):
        # Primary key: DocID -> OptDocument
        self.documents: Dict[str, OptDocument] = {}
        # Secondary index: Image Path / Page Bates -> DocID (for reverse lookup)
        self.bates_to_doc_id: Dict[str, str] = {}
        # List of DocIDs in insertion order for indexed navigation
        self.doc_id_list: List[str] = []

    def clear(self):
        self.documents.clear()
        self.bates_to_doc_id.clear()
        self.doc_id_list.clear()

    def add_document(self, doc: OptDocument):
        if doc.doc_id not in self.documents:
            self.doc_id_list.append(doc.doc_id)
        self.documents[doc.doc_id] = doc
        for bates in doc.bates_list:
            self.bates_to_doc_id[bates] = doc.doc_id

    def get_document(self, doc_id: str) -> Optional[OptDocument]:
        return self.documents.get(doc_id)

    def get_doc_id_by_bates(self, bates: str) -> Optional[str]:
        return self.bates_to_doc_id.get(bates)

    def get_all_pages(self) -> List[Tuple[str, str, int, int, str, str]]:
        """
        Returns a flat list of all pages in the store.
        Tuple format: (bates, doc_id, page_index, total_doc_pages, volume, relative_path)
        """
        pages = []
        for doc_id in self.doc_id_list:
            doc = self.documents[doc_id]
            for idx, img_path in enumerate(doc.image_paths):
                bates = doc.bates_list[idx] if idx < len(doc.bates_list) else f"{doc.doc_id}_{idx+1}"
                pages.append((bates, doc.doc_id, idx + 1, doc.page_count, doc.volume_name, img_path))
        return pages

    def get_first_image_path(self) -> Optional[str]:
        for doc_id in self.doc_id_list:
            doc = self.documents[doc_id]
            if doc.image_paths:
                return doc.image_paths[0]
        return None

    def __len__(self) -> int:
        return len(self.documents)


def resolve_full_image_path(image_path: str, base_dir: str = "") -> str:
    """
    Resolves full image file path on disk handling relative subpaths, duplicate folder segments,
    and parent folder searches.
    """
    if not image_path:
        return ""

    if os.path.isabs(image_path) and os.path.exists(image_path):
        return os.path.normpath(image_path)

    clean_img_path = os.path.normpath(image_path)
    clean_base = os.path.normpath(base_dir) if base_dir else ""

    # Direct join
    direct = os.path.normpath(os.path.join(clean_base, clean_img_path)) if clean_base else clean_img_path
    if os.path.exists(direct):
        return direct

    # Try matching tail segments if relative path overlaps with base_dir subfolders
    rel_parts = clean_img_path.split(os.sep)
    for idx in range(1, len(rel_parts)):
        sub_rel = os.path.join(*rel_parts[idx:])
        sub_join = os.path.normpath(os.path.join(clean_base, sub_rel))
        if os.path.exists(sub_join):
            return sub_join

    # Try searching parent directories of base_dir for the relative path
    curr_dir = clean_base
    for _ in range(3):
        if not curr_dir:
            break
        test_path = os.path.normpath(os.path.join(curr_dir, clean_img_path))
        if os.path.exists(test_path):
            return test_path
        parent = os.path.dirname(curr_dir)
        if parent == curr_dir:
            break
        curr_dir = parent

    return direct


def infer_base_dir(relative_path: str, actual_path: str) -> str:
    """
    Infers root base directory given a relative load file image path and the actual selected image file path on disk.
    Supports partial sub-path matching.
    """
    rel_norm = os.path.normpath(relative_path)
    act_norm = os.path.normpath(actual_path)

    if act_norm.lower().endswith(rel_norm.lower()):
        base = act_norm[:-len(rel_norm)].rstrip(os.sep)
        return base

    # Try suffix matching on subpaths
    rel_parts = rel_norm.split(os.sep)
    for idx in range(1, len(rel_parts)):
        sub_rel = os.path.join(*rel_parts[idx:])
        if act_norm.lower().endswith(sub_rel.lower()):
            return act_norm[:-len(sub_rel)].rstrip(os.sep)

    return os.path.dirname(act_norm)



# --- Load File Parsers ---

def parse_opt_file(file_path: str) -> OptDocumentStore:
    """
    Parses Opticon (.opt) file.
    Format: Bates, Volume, Path, DocBreak (Y/N), Box, Folder, PageCount
    """
    store = OptDocumentStore()
    current_doc: Optional[OptDocument] = None

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip('"') for p in line.split(',')]
            if len(parts) < 3:
                continue

            bates = parts[0]
            volume = parts[1]
            img_path = parts[2]
            doc_break = parts[3].upper() if len(parts) > 3 else "N"
            box = parts[4] if len(parts) > 4 else ""
            folder = parts[5] if len(parts) > 5 else ""
            page_cnt_str = parts[6] if len(parts) > 6 else ""

            try:
                page_cnt = int(page_cnt_str) if page_cnt_str else 0
            except ValueError:
                page_cnt = 0

            # Document boundary detection: Y indicates start of a new document
            if doc_break == "Y" or current_doc is None:
                if current_doc:
                    store.add_document(current_doc)
                current_doc = OptDocument(
                    doc_id=bates,
                    volume_name=volume,
                    box=box,
                    folder=folder,
                    page_count=page_cnt,
                    image_paths=[img_path],
                    bates_list=[bates]
                )
            else:
                current_doc.image_paths.append(img_path)
                current_doc.bates_list.append(bates)
                current_doc.page_count = len(current_doc.image_paths)

        if current_doc:
            store.add_document(current_doc)

    return store


def parse_lfp_file(file_path: str) -> OptDocumentStore:
    """
    Parses IPRO LFP (.lfp) file.
    Example lines:
    IM, Bates, DocBreak (Y/N), Offset/Volume, Path, ...
    """
    store = OptDocumentStore()
    current_doc: Optional[OptDocument] = None

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(',')]
            if not parts or parts[0].upper() not in ("IM", "OF"):
                continue

            if parts[0].upper() == "IM":
                if len(parts) < 5:
                    continue
                bates = parts[1]
                doc_break = parts[2].upper()  # C (continue) or D/Y (doc break) or B (boundary)
                volume = parts[3]
                img_path = parts[4].strip('"')

                is_new_doc = doc_break in ("D", "Y", "B", "1") or current_doc is None

                if is_new_doc:
                    if current_doc:
                        store.add_document(current_doc)
                    current_doc = OptDocument(
                        doc_id=bates,
                        volume_name=volume,
                        page_count=1,
                        image_paths=[img_path],
                        bates_list=[bates]
                    )
                else:
                    current_doc.image_paths.append(img_path)
                    current_doc.bates_list.append(bates)
                    current_doc.page_count = len(current_doc.image_paths)

        if current_doc:
            store.add_document(current_doc)

    return store


def parse_dii_file(file_path: str) -> OptDocumentStore:
    """
    Parses Summation DII (.dii) file.
    Summation DII uses token-based commands like @V, @D, @F, @I, etc.
    """
    store = OptDocumentStore()
    current_doc: Optional[OptDocument] = None
    current_vol = ""
    current_box = ""
    current_folder = ""

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith("@V"):
                current_vol = line[2:].strip()
            elif line.startswith("@B"):
                current_box = line[2:].strip()
            elif line.startswith("@F"):
                current_folder = line[2:].strip()
            elif line.startswith("@D"):
                if current_doc:
                    store.add_document(current_doc)
                doc_id = line[2:].strip()
                current_doc = OptDocument(
                    doc_id=doc_id,
                    volume_name=current_vol,
                    box=current_box,
                    folder=current_folder,
                    page_count=0,
                    image_paths=[],
                    bates_list=[]
                )
            elif line.startswith("@I"):
                # Image line: @I bates; path
                content = line[2:].strip()
                img_parts = content.split(';')
                bates = img_parts[0].strip()
                img_path = img_parts[1].strip() if len(img_parts) > 1 else ""

                if current_doc is None:
                    current_doc = OptDocument(
                        doc_id=bates,
                        volume_name=current_vol,
                        box=current_box,
                        folder=current_folder
                    )
                current_doc.image_paths.append(img_path)
                current_doc.bates_list.append(bates)
                current_doc.page_count = len(current_doc.image_paths)

        if current_doc:
            store.add_document(current_doc)

    return store


def parse_smi_file(file_path: str) -> OptDocumentStore:
    """
    Parses Summation SMI (.smi) file format.
    Format is delimiter-separated line entries.
    """
    store = OptDocumentStore()
    current_doc: Optional[OptDocument] = None

    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip('"') for p in line.split(',')]
            if len(parts) < 3:
                parts = [p.strip('"') for p in line.split('\t')]
            if len(parts) < 3:
                continue

            doc_id = parts[0]
            bates = parts[1]
            img_path = parts[2]
            doc_break = parts[3].upper() if len(parts) > 3 else "N"

            if doc_break == "Y" or current_doc is None or current_doc.doc_id != doc_id:
                if current_doc:
                    store.add_document(current_doc)
                current_doc = OptDocument(
                    doc_id=doc_id,
                    page_count=1,
                    image_paths=[img_path],
                    bates_list=[bates]
                )
            else:
                current_doc.image_paths.append(img_path)
                current_doc.bates_list.append(bates)
                current_doc.page_count = len(current_doc.image_paths)

        if current_doc:
            store.add_document(current_doc)

    return store


def parse_image_load_file(file_path: str) -> OptDocumentStore:
    """
    Auto-detects format from extension and parses into an OptDocumentStore.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".opt":
        return parse_opt_file(file_path)
    elif ext == ".lfp":
        return parse_lfp_file(file_path)
    elif ext == ".dii":
        return parse_dii_file(file_path)
    elif ext == ".smi":
        return parse_smi_file(file_path)
    else:
        # Fallback to OPT parser
        return parse_opt_file(file_path)


# --- Load File Writers ---

def write_opt_file(output_path: str, store: OptDocumentStore):
    """
    Writes OptDocumentStore contents to an Opticon (.opt) file.
    """
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        for doc_id in store.doc_id_list:
            doc = store.documents[doc_id]
            for idx, img_path in enumerate(doc.image_paths):
                bates = doc.bates_list[idx] if idx < len(doc.bates_list) else f"{doc.doc_id}_{idx+1}"
                doc_break = "Y" if idx == 0 else "N"
                page_cnt = str(doc.page_count) if idx == 0 else ""
                line = f'"{bates}","{doc.volume_name}","{img_path}","{doc_break}","{doc.box}","{doc.folder}","{page_cnt}"\n'
                f.write(line)
