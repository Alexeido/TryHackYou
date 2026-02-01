@echo off
cd /d "%~dp0"
pdflatex -shell-escape -interaction=nonstopmode main.tex
bibtex main
pdflatex -shell-escape -interaction=nonstopmode main.tex
pdflatex -shell-escape -interaction=nonstopmode main.tex
echo.
echo Compilacion terminada. Revisa main.pdf
pause
