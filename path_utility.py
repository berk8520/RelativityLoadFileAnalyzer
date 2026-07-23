import os
import re

def normalize_path(path_str, volume_name):
    """
    Normalizes path formatting, cleans drive roots, and standardizes paths to
    relative structure starting with the volume name (e.g. .\\ACMEPROD001\\...).
    """
    if not path_str:
        return ""
    # Normalize slashes (standardizing on backslash for Relativity style load files)
    normalized = path_str.replace('/', '\\')
    
    # Strip leading/trailing whitespaces, quotes, and backslashes
    normalized = normalized.strip().strip('"').strip("'")
    
    # Split the path into parts
    parts = [p for p in normalized.split('\\') if p]
    
    # Find the index of the volume name (case-insensitive)
    volume_idx = -1
    for i, part in enumerate(parts):
        if part.strip().lower() == volume_name.strip().lower():
            volume_idx = i
            break
            
    if volume_idx != -1:
        # Reconstruct starting with volume_name
        rel_parts = parts[volume_idx:]
        return ".\\" + "\\".join(rel_parts)
    else:
        # Strip drive letter if present
        cleaned = re.sub(r'^[a-zA-Z]:\\?', '', normalized)
        # Strip leading dots or backslashes
        cleaned = cleaned.lstrip('.\\')
        return f".\\{volume_name}\\{cleaned}"

def check_file_exists(load_file_path, original_path, normalized_path, volume_name):
    """
    Safely checks if a file exists relative to the load file or parent folders.
    """
    if not original_path:
        return False
        
    # If the original path is absolute and exists, return True
    if os.path.isabs(original_path) and os.path.exists(original_path):
        return True
        
    load_file_dir = os.path.dirname(load_file_path)
    
    # 1. Try directly joining original_path to load_file_dir
    p1 = os.path.abspath(os.path.join(load_file_dir, original_path))
    if os.path.exists(p1):
        return True
        
    # 2. Try joining normalized_path relative to the parent of load_file_dir
    parent_dir = os.path.dirname(load_file_dir)
    rel_path_stripped = normalized_path.lstrip('.\\')
    p2 = os.path.abspath(os.path.join(parent_dir, rel_path_stripped))
    if os.path.exists(p2):
        return True
        
    # 3. Try joining normalized_path relative to the load_file_dir itself
    p3 = os.path.abspath(os.path.join(load_file_dir, rel_path_stripped))
    if os.path.exists(p3):
        return True
        
    # 4. Try stripping the volume name folder segment if checking inside load_file_dir
    if rel_path_stripped.lower().startswith(volume_name.lower() + '\\'):
        sub_rel = rel_path_stripped[len(volume_name) + 1:]
        p4 = os.path.abspath(os.path.join(load_file_dir, sub_rel))
        if os.path.exists(p4):
            return True
            
    return False
