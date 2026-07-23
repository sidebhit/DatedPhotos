# Photo Converter (Windows 11)

A simple Windows 11 desktop app that converts photos into **1800×1200** JPEG files with a white padding strip and the photo capture date.

## What it does

1. You pick a folder of photos.
2. Click **Convert**.
3. The app creates a `converted` subfolder and writes one output JPEG per input image.

Each output image:

- Uses a fixed **1800×1200** canvas (6×4 landscape page).
- Scales the source photo **down to fit** without cropping (aspect ratio preserved).
- Adds **white padding** on the **right** for landscape photos, or on the **bottom** for portrait photos.
- Writes the **date the photo was taken** (from EXIF, or file date as fallback) in the padding area.
- Draws the date **vertically**, parallel to the short edge of the page, centered in the padding.

You can adjust **text size** and **text color** in the UI before converting.

## Requirements

- Windows 11 (also runs on Windows 10)
- [Python 3.10+](https://www.python.org/downloads/) — check **“Add python.exe to PATH”** during install

## Setup

```powershell
cd path\to\DatedPhotos
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```powershell
python main.py
```

## Supported input formats

JPEG, PNG, TIFF, BMP, WEBP

Output is always JPEG (`.jpg`) at quality 95.

## Build a standalone `.exe` (optional)

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name PhotoConverter main.py
```

The executable will be in `dist\PhotoConverter.exe`.

## Notes

- Only files in the **selected folder** are processed (not subfolders).
- The original files are never modified.
- For portrait images, the photo is centered horizontally above the bottom padding strip.
