@echo off
echo ========================================
echo    ERRORES DE COMPILACION LATEX
echo ========================================
echo.

if not exist main.log (
    echo No se encuentra main.log
    pause
    exit /b
)

echo Buscando errores en main.log...
echo.
echo === ERRORES CRITICOS ===
findstr /C:"! " main.log
echo.
echo === WARNINGS ===
findstr /C:"Warning:" main.log | findstr /V "headheight Underfull Overfull"
echo.
echo === ERRORES UNICODE ===
findstr /C:"Unicode character" main.log
echo.
echo === CAPACITY EXCEEDED ===
findstr /C:"capacity exceeded" main.log
echo.
echo ========================================
pause
