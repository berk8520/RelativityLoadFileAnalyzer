import os
import sys

def verify_build(build_dir):
    print(f"Verifying PyInstaller build in: {build_dir}")
    
    if not os.path.exists(build_dir):
        print(f"Error: Build directory '{build_dir}' does not exist.")
        return False

    # Check for PyQt5 folder
    pyside_dir = os.path.join(build_dir, "_internal", "PyQt5", "Qt5", "bin")
    if not os.path.exists(pyside_dir):
        pyside_dir = os.path.join(build_dir, "PyQt5", "Qt5", "bin")
        
    if not os.path.exists(pyside_dir):
        # Fallback to direct folder
        pyside_dir = os.path.join(build_dir, "_internal", "PyQt5")
        if not os.path.exists(pyside_dir):
            pyside_dir = os.path.join(build_dir, "PyQt5")
            
    if not os.path.exists(pyside_dir):
        print(f"Error: PyQt5 directory not found in '{build_dir}'.")
        return False
        
    print(f"Found PyQt5 directory at: {pyside_dir}")

    required_dlls = [
        "Qt5Core.dll",
        "Qt5Widgets.dll",
        "Qt5Gui.dll"
    ]

    all_found = True
    for dll in required_dlls:
        dll_path = os.path.join(pyside_dir, dll)
        if os.path.exists(dll_path):
            print(f"Found {dll}")
        else:
            print(f"Missing {dll}")
            all_found = False

    if all_found:
        print("\nVerification SUCCESS: All required Qt5 DLLs are bundled correctly.")
        return True
    else:
        print("\nVerification FAILED: Some required Qt5 DLLs are missing.")
        return False

if __name__ == "__main__":
    # The default output dir for PyInstaller --onedir on pyside_main.py
    default_build_dir = os.path.join(os.path.dirname(__file__), "dist", "pyside_main")
    success = verify_build(default_build_dir)
    sys.exit(0 if success else 1)
