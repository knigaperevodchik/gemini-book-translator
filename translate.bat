@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Проверка и установка зависимостей
echo ========================================
echo.

:: Проверяем установлен ли pip
pip --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] pip не установлен!
    echo Установите Python и pip перед запуском.
    pause
    exit /b 1
)

:: Устанавливаем зависимости
echo Устанавливаю библиотеки...
pip install google-generativeai ebooklib beautifulsoup4 lxml

echo.
echo ========================================
echo   Запуск переводчика...
echo ========================================
echo.

:: Проверяем существует ли файл скрипта
if not exist "translate_gemini_new.py" (
    echo [ОШИБКА] Файл translate_gemini_new.py не найден!
    echo Убедитесь, что скрипт находится в той же папке.
    pause
    exit /b 1
)

python translate_gemini_new.py

echo.
echo ========================================
echo   Работа завершена
echo ========================================
pause
