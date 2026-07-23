@echo off
setlocal

echo Installing build dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo Building PhotoConverter...
pyinstaller --noconfirm PhotoConverter.spec

if exist dist\PhotoConverter\PhotoConverter.exe (
    echo.
    echo Build complete: dist\PhotoConverter\PhotoConverter.exe
    echo Run PhotoConverter.exe from the dist\PhotoConverter folder.
) else (
    echo.
    echo Build failed.
    exit /b 1
)
