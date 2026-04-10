@echo off
echo ========================================
echo Compiling DIDMerger.exe
echo ========================================
echo.

call venv\Scripts\activate.bat
pyinstaller --onefile --name DIDMerger --console --noconfirm --clean --strip DIDMerger.py

echo.
echo ========================================
echo COMPILATION COMPLETE!
echo ========================================
echo Executable: dist\DIDMerger.exe
echo.
pause