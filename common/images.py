"""Image upload helpers — compress photos before saving to disk."""

from __future__ import annotations

from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile


def compress_image_upload(
    uploaded_file,
    *,
    max_side: int = 1600,
    quality: int = 72,
) -> InMemoryUploadedFile:
    """
    Resize and JPEG-compress an uploaded image to reduce storage size.

    - Converts to RGB (handles PNG/HEIC-like modes with transparency)
    - Scales so the longest side is at most ``max_side``
    - Saves as optimized JPEG
    """
    from PIL import Image, ImageOps

    if not uploaded_file:
        return uploaded_file

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
    if "." in base_name:
        base_name = base_name.rsplit(".", 1)[0]
    filename = f"{base_name}.jpg"

    return InMemoryUploadedFile(
        buffer,
        field_name=getattr(uploaded_file, "field_name", None),
        name=filename,
        content_type="image/jpeg",
        size=buffer.getbuffer().nbytes,
        charset=None,
    )
