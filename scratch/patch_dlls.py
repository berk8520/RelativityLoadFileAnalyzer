import os

def patch_file(filepath):
    with open(filepath, 'rb') as f:
        data = f.read()
    
    target = b'SetThreadDescription'
    replacement = b'SetThreadPriority\x00\x00\x00'
    
    if target in data:
        new_data = data.replace(target, replacement)
        with open(filepath, 'wb') as f:
            f.write(new_data)
        print(f"Successfully patched SetThreadDescription -> SetThreadPriority in: {filepath}")

dist_dir = 'dist/pyside_main'
if os.path.exists(dist_dir):
    for root, dirs, files in os.walk(dist_dir):
        for file in files:
            if file.lower().endswith('.dll') or file.lower().endswith('.pyd'):
                path = os.path.join(root, file)
                try:
                    patch_file(path)
                except Exception as e:
                    print(f"Error patching {path}: {e}")
else:
    print("dist/pyside_main does not exist!")
