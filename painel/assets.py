"""Utilitários de assets visuais (logos/banners) com redimensionamento."""
from __future__ import annotations

from pathlib import Path
from weakref import WeakKeyDictionary

try:
    from PIL import Image, ImageTk
except Exception:  # pragma: no cover - fallback sem Pillow
    Image = ImageTk = None


ASSETS_DIR = Path(__file__).resolve().parent.parent / 'assets'
LOGO_PATH = ASSETS_DIR / 'phinia_logo.png'
BANNER_PATH = ASSETS_DIR / 'pgi_banner.jpg'


class AssetManager:
    def __init__(self):
        self._cache = WeakKeyDictionary()  # imagens não devem atravessar instâncias de Tk()

    def _load(self, path):
        if Image is None or not Path(path).exists():
            return None
        return Image.open(path)

    def photo(self, key, path, max_width=None, max_height=None, master=None):
        """Retorna PhotoImage redimensionada e cacheada por tamanho."""
        # Cada instância de Tk possui seu próprio interpretador Tcl e suas imagens.
        # Reusar PhotoImage de outro Tk provoca 'image pyimageN does not exist'.
        root = master.winfo_toplevel() if master is not None else None
        cache = self._cache.setdefault(root, {}) if root is not None else {}
        cache_key = (key, str(path), max_width, max_height)
        if cache_key in cache:
            return cache[cache_key]
        image = self._load(path)
        if image is None:
            return None
        img = image.copy()
        if max_width or max_height:
            w, h = img.size
            sx = (max_width / w) if max_width else 9999
            sy = (max_height / h) if max_height else 9999
            scale = min(sx, sy)
            if scale <= 0:
                scale = 1
            nw = max(1, int(w * scale))
            nh = max(1, int(h * scale))
            if (nw, nh) != (w, h):
                img = img.resize((nw, nh), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img, master=root) if root is not None else ImageTk.PhotoImage(img)
        cache[cache_key] = photo
        return photo


assets = AssetManager()
