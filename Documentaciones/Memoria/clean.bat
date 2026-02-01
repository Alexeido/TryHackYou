@echo off
echo Limpiando archivos temporales de LaTeX y minted...
rd /s /q _minted 2>nul
del /q *.aux 2>nul
del /q *.log 2>nul
del /q *.out 2>nul
del /q *.toc 2>nul
del /q *.bbl 2>nul
del /q *.blg 2>nul
del /q *.fdb_latexmk 2>nul
del /q *.fls 2>nul
del /q *.synctex.gz 2>nul
del /q *.maf 2>nul
del /q *.mtc 2>nul
del /q *.mtc0 2>nul
echo Limpieza completada. Ahora compila de nuevo.
pause
