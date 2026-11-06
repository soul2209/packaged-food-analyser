import io
import os
import shutil

import pytesseract
from PIL import Image, ImageChops, ImageFilter, ImageOps

try:
    import zxingcpp as _zxing
except Exception:
    _zxing = None

try:
    from pyzbar.pyzbar import decode as _zbar_decode
except Exception:
    _zbar_decode = None

WINDOWS_PATHS = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
)


class OcrUnavailable(Exception):
    """Tesseract is not installed or cannot be found."""


def _locate_tesseract():
    env = os.environ.get("TESSERACT_CMD")
    if env and os.path.exists(env):
        return env
    found = shutil.which("tesseract")
    if found:
        return found
    for path in WINDOWS_PATHS:
        if os.path.exists(path):
            return path
    return None


_cmd = _locate_tesseract()
if _cmd:
    pytesseract.pytesseract.tesseract_cmd = _cmd


def _open(image_bytes):
    image = Image.open(io.BytesIO(image_bytes))
    return ImageOps.exif_transpose(image)


def _prepare(image):
    image = image.convert("L")
    width, height = image.size
    longest = max(width, height)
    if longest < 1600:
        scale = 1600 / longest
        image = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
    elif longest > 2600:
        scale = 2600 / longest
        image = image.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
    image = ImageOps.autocontrast(image, cutoff=1)
    image = image.filter(ImageFilter.SHARPEN)
    return image


def _binarise(image):
    # Subtract blurred background to cope with glossy packs and uneven lighting, then threshold.
    background = image.filter(ImageFilter.GaussianBlur(30))
    flat = ImageChops.subtract(ImageChops.add(image, Image.new("L", image.size, 255)), background)
    return ImageOps.autocontrast(flat).point(lambda p: 255 if p > 170 else 0)


def _run(image, config):
    try:
        return pytesseract.image_to_string(image, config=config)
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailable(str(exc))


def extract_candidates(image_bytes):
    """Yield several OCR readings of the same photo (different layouts and cleanups).
    The caller keeps whichever parses best."""
    if not _cmd:
        raise OcrUnavailable("Tesseract was not found.")
    prepared = _prepare(_open(image_bytes))
    yield _run(prepared, "--oem 3 --psm 6")
    yield _run(prepared, "--oem 3 --psm 4")
    yield _run(prepared, "--oem 3 --psm 3")
    try:
        yield _run(_binarise(prepared), "--oem 3 --psm 6")
    except OcrUnavailable:
        raise
    except Exception:
        pass


def extract_rotated(image_bytes):
    """Last resort for photos taken sideways."""
    prepared = _prepare(_open(image_bytes))
    for angle in (90, 270, 180):
        yield _run(prepared.rotate(angle, expand=True, fillcolor=255), "--oem 3 --psm 6")


def extract_text(image_bytes):
    if not _cmd:
        raise OcrUnavailable("Tesseract was not found.")
    return _run(_prepare(_open(image_bytes)), "--oem 3 --psm 6")


def _variants(image):
    gray = image.convert("L")
    yield image.convert("RGB")
    yield gray
    yield ImageOps.autocontrast(gray)
    width, height = gray.size
    if max(width, height) > 1600:
        scale = 1600 / max(width, height)
        yield gray.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
    elif max(width, height) < 800:
        yield gray.resize((width * 2, height * 2), Image.LANCZOS)
    yield gray.point(lambda p: 255 if p > 128 else 0)


def decode_barcode(image_bytes):
    """Return the first numeric barcode found in the photo, or None."""
    try:
        base = _open(image_bytes)
    except Exception:
        return None
    for variant in _variants(base):
        if _zxing is not None:
            try:
                for result in _zxing.read_barcodes(variant):
                    text = (result.text or "").strip()
                    if text.isdigit():
                        return text
            except Exception:
                pass
        if _zbar_decode is not None:
            try:
                for result in _zbar_decode(variant):
                    value = result.data.decode("ascii", errors="ignore")
                    if value.isdigit():
                        return value
            except Exception:
                pass
    return None
