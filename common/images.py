"""Image upload helpers — compress photos before saving to disk."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import InMemoryUploadedFile, UploadedFile


def _is_real_upload(uploaded_file) -> bool:
    if not uploaded_file:
        return False
    name = (getattr(uploaded_file, "name", "") or "").strip()
    if not name:
        return False
    size = getattr(uploaded_file, "size", None)
    if size == 0:
        return False
    return True


def compress_image_upload(
    uploaded_file,
    *,
    max_side: int = 1600,
    quality: int = 72,
) -> UploadedFile:
    """
    Resize and JPEG-compress an uploaded image to reduce storage size.

    Falls back to the original upload if compression is not possible
    (e.g. HEIC without plugin, corrupt file, unusual formats).
    """
    if not _is_real_upload(uploaded_file):
        return uploaded_file

    try:
        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError:
        return uploaded_file

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image = ImageOps.exif_transpose(image)

        if image.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            alpha = image.split()[-1] if image.mode in ("RGBA", "LA") else None
            background.paste(image, mask=alpha)
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        width, height = image.size
        longest = max(width, height)
        if longest > max_side:
            scale = max_side / float(longest)
            image = image.resize(
                (max(1, int(width * scale)), max(1, int(height * scale))),
                Image.Resampling.LANCZOS,
            )

        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        buffer.seek(0)

        base_name = getattr(uploaded_file, "name", "receipt.jpg") or "receipt.jpg"
        base_name = Path(base_name).stem or "receipt"
        filename = f"{base_name}.jpg"

        return InMemoryUploadedFile(
            buffer,
            field_name=getattr(uploaded_file, "field_name", "receipt_image"),
            name=filename,
            content_type="image/jpeg",
            size=buffer.getbuffer().nbytes,
            charset=None,
        )
    except (UnidentifiedImageError, OSError, ValueError):
        try:
            uploaded_file.seek(0)
        except Exception:  # noqa: BLE001
            pass
        return uploaded_file
    except Exception:  # noqa: BLE001
        try:
            uploaded_file.seek(0)
        except Exception:  # noqa: BLE001
            pass
        return uploaded_file
