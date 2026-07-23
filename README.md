# Photo Converter (Windows 11)

A standalone Windows desktop app that converts photos into dated JPEGs with white padding.

## What it does

1. You pick a folder of photos.
2. Click **Convert**.
3. The app creates a `converted` subfolder and writes one output JPEG per input image.

Each output image:

- **Landscape** sources → **1800×1200** canvas, white padding on the **right**, date written vertically in the strip.
- **Portrait** sources → **1200×1800** canvas, white padding on the **bottom**, date written horizontally in the strip.
- Scales the source photo **down to fit** without cropping (aspect ratio preserved).
- Uses the **EXIF capture date** (or file date as fallback).
- Date text is always parallel to the **short edge** of the page.

You can adjust **text size** and **text color** before converting.

## Download (no dependencies)

Download `PhotoConverter-win10.zip` from the latest [GitHub Actions build artifact](https://github.com/sidebhit/DatedPhotos/actions). Unzip the folder and run `PhotoConverter.exe` inside it. No Python install required.

The app is packaged as a folder (not a single-file exe) so it starts quickly on Windows 10/11.

The executable includes publisher metadata (`sidebhit`) in its Windows version info. To fully avoid SmartScreen warnings for unknown publishers, the `.exe` would still need to be code-signed with a trusted certificate.

## Build the `.exe` yourself

On Windows:

```powershell
build.bat
```

Output: `dist\PhotoConverter\PhotoConverter.exe`

Or manually:

```powershell
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm PhotoConverter.spec
```

## Run from source (development)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Supported input formats

JPEG, PNG, TIFF, BMP, WEBP

Output is always JPEG (`.jpg`) at quality 95.

## Notes

- Only files in the **selected folder** are processed (not subfolders).
- The original files are never modified.
