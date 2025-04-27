@echo off
title Controle de Estudos - Setup Automático
color 0A

echo 🔧 Verificando Python...
where python >nul 2>&1
if errorlevel 1 (
    echo [✖] Python não encontrado. Instale o Python 3.8+ antes de continuar.
    pause
    exit /b
)

echo 🔧 Verificando pip...
where pip >nul 2>&1
if errorlevel 1 (
    echo [✖] Pip não encontrado. Instale o Pip antes de continuar.
    pause
    exit /b
)

echo 🔧 Criando pastas necessárias...
if not exist data\uploads (
    mkdir data\uploads
    echo [✔] Pasta data\uploads criada.
) else (
    echo [✔] Pasta data\uploads já existe.
)

if not exist templates (
    mkdir templates
    echo [✔] Pasta templates criada.
) else (
    echo [✔] Pasta templates já existe.
)

echo 🔧 Instalando Flask (se necessário)...
pip show flask >nul 2>&1
if errorlevel 1 (
    echo [..] Flask não encontrado. Instalando...
    pip install flask
    echo [✔] Flask instalado.
) else (
    echo [✔] Flask já instalado.
)

echo 🔧 Verificando app.py...
if not exist app.py (
    echo [✖] Arquivo app.py não encontrado na pasta atual.
    pause
    exit /b
)

echo 🚀 Iniciando o sistema...
start /B python app.py

timeout /t 3 >nul

echo 🌐 Abrindo navegador...
start http://127.0.0.1:5000/

exit
