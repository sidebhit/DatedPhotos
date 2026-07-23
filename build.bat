@echo off
setlocal

echo Installing build dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo Building PhotoConverter.exe...
pyinstaller --noconfirm PhotoConverter.spec

if exist dist\PhotoConverter.exe (
    echo.
    echo Build complete: dist\PhotoConverter.exe
) else (
    echo.
    echo Build failed.
    exit /b 1
)
