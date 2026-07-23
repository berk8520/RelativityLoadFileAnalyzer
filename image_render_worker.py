"""
Optimized Image Render Worker for Relativity Load File Analyzer using PySide6.
Renders PDF pages and image files cleanly to temporary PNG files for browser viewport consumption.
"""

import os
import tempfile
from PySide6.QtCore import QThread, Signal
from PIL import Image

try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

from opt_engine import resolve_full_image_path


class ImageRenderWorker(QThread):
    """
    Worker thread that renders a requested document page asynchronously.
    Emits image_rendered signal with (temp_image_path: str, page_index: int, total_pages: int, error_message: str).
    """
    image_rendered = Signal(str, int, int, str)

    def __init__(self, file_path: str, page_index: int = 0, dpi: int = 300, base_dir: str = "", parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.page_index = page_index
        self.dpi = dpi
        self.base_dir = base_dir

    def run(self):
        full_path = resolve_full_image_path(self.file_path, self.base_dir)

        if not os.path.exists(full_path):
            self.image_rendered.emit("", self.page_index, 0, f"File not found: {full_path}")
            return

        ext = os.path.splitext(full_path)[1].lower()

        try:
            if ext == ".pdf":
                self._render_pdf(full_path)
            else:
                self._render_image(full_path)
        except Exception as e:
            self.image_rendered.emit("", self.page_index, 0, f"Rendering error: {str(e)}")

    def _render_pdf(self, pdf_path: str):
        if not HAS_PYMUPDF:
            self.image_rendered.emit("", self.page_index, 0, "PyMuPDF (fitz) is required for PDF rendering.")
            return

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        if total_pages == 0:
            doc.close()
            self.image_rendered.emit("", self.page_index, 0, "PDF has no pages.")
            return

        idx = max(0, min(self.page_index, total_pages - 1))
        page = doc.load_page(idx)

        # Calculate matrix for target DPI (72 DPI is standard 1.0 zoom factor)
        zoom = self.dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        # Output to temporary PNG
        temp_fd, temp_path = tempfile.mkstemp(suffix=".png")
        os.close(temp_fd)
        pix.save(temp_path)
        doc.close()

        self.image_rendered.emit(temp_path, idx, total_pages, "")

    def _render_image(self, img_path: str):
        with Image.open(img_path) as pil_img:
            # Handle multi-frame images (e.g. multi-page Group 4 TIFFs)
            total_pages = getattr(pil_img, "n_frames", 1)
            idx = max(0, min(self.page_index, total_pages - 1))

            if total_pages > 1:
                pil_img.seek(idx)

            # Convert to standard RGB to prevent browser compatibility issues
            if pil_img.mode != "RGB":
                pil_img = pil_img.convert("RGB")

            # Save to temporary PNG
            temp_fd, temp_path = tempfile.mkstemp(suffix=".png")
            os.close(temp_fd)
            pil_img.save(temp_path, "PNG")

            self.image_rendered.emit(temp_path, idx, total_pages, "")