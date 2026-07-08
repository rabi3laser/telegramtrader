@echo off
:: ═══════════════════════════════════════════════════════════════
:: TELEGRAMTRADER - DÉMARRAGE RAPIDE (Double-clic)
:: ═══════════════════════════════════════════════════════════════
title TelegramTrader - Démarrage
cd /d "%~dp0"

echo.
echo  ████████╗███████╗██╗     ███████╗ ██████╗ ██████╗  █████╗ ███╗   ███╗
echo  ╚══██╔══╝██╔════╝██║     ██╔════╝██╔════╝ ██╔══██╗██╔══██╗████╗ ████║
echo     ██║   █████╗  ██║     █████╗  ██║  ███╗██████╔╝███████║██╔████╔██║
echo     ██║   ██╔══╝  ██║     ██╔══╝  ██║   ██║██╔══██╗██╔══██║██║╚██╔╝██║
echo     ██║   ███████╗███████╗███████╗╚██████╔╝██║  ██║██║  ██║██║ ╚═╝ ██║
echo     ╚═╝   ╚══════╝╚══════╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝
echo.
echo  TRADER
echo  ═══════════════════════════════════════════════════════════════
echo.

:: Lancer le script PowerShell principal
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-auto.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERREUR] Le script PowerShell a echoue.
    echo Verifiez que PowerShell est installe sur votre machine.
    pause
)
