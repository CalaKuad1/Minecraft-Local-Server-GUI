@echo off
title Minecraft Server GUI
color 0A

echo.
echo ==========================================
echo   🎮 Minecraft Server GUI
echo ==========================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python no encontrado
    echo.
    echo Instala Python desde: https://python.org
    echo ✅ Marca "Add Python to PATH" durante la instalacion
    echo.
    pause
    exit /b 1
)

echo ✅ Python detectado
echo.

REM Verificar si existe el entorno virtual
if not exist "venv" (
    echo 📦 Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ Error creando entorno virtual
        pause
        exit /b 1
    )
)

REM Activar entorno virtual e instalar dependencias
echo 🔧 Configurando dependencias...
call venv\Scripts\activate.bat
pip install -r requirements.txt >nul 2>&1

REM Ejecutar la aplicación
echo 🚀 Iniciando aplicación...
echo.
python main.py

echo.
echo 👋 Aplicación cerrada
pause