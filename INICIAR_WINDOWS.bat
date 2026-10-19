@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Abrindo o Painel de Gestao Integrada da Phinia...
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PGI_RUNTIME=python"
    goto runtime_pronto
)
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PGI_RUNTIME=py -3"
    goto runtime_pronto
)
echo Python nao encontrado. Instale o Python 3.10 ou superior com a opcao Add Python to PATH.
goto falha

:runtime_pronto
%PGI_RUNTIME% -c "import tkinter, matplotlib, openpyxl, PIL" >nul 2>&1
if errorlevel 1 (
    echo Preparando os componentes para a primeira abertura...
    %PGI_RUNTIME% -m pip install -r requirements.txt
    if errorlevel 1 goto falha
)
if /I "%~1"=="--verificar" (
    echo Componentes verificados. O painel esta pronto para abrir.
    exit /b 0
)
%PGI_RUNTIME% main.py %*
if errorlevel 1 goto falha
exit /b 0

:falha
echo Nao foi possivel abrir o painel. Confira a mensagem acima.
pause
exit /b 1
