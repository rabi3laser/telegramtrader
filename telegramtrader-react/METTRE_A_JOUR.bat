@echo off
:: ═══════════════════════════════════════════════════════════════
:: TELEGRAMTRADER - MISE À JOUR (Double-clic)
:: ═══════════════════════════════════════════════════════════════
title TelegramTrader - Mise à jour
cd /d "%~dp0"

echo.
echo  ═══════════════════════════════════════════════════════════════
echo   TELEGRAMTRADER  —  Mise à jour de l'application
echo  ═══════════════════════════════════════════════════════════════
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\update-auto.ps1"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERREUR] La mise a jour a echoue.
    pause
)
