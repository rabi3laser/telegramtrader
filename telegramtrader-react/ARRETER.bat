@echo off
:: ═══════════════════════════════════════════════════════════════
:: TELEGRAMTRADER - ARRÊT (Double-clic)
:: ═══════════════════════════════════════════════════════════════
title TelegramTrader - Arrêt
cd /d "%~dp0"

echo.
echo  ═══════════════════════════════════════════════════════════════
echo   TELEGRAMTRADER  —  Arrêt de l'application
echo  ═══════════════════════════════════════════════════════════════
echo.

PowerShell -NoProfile -ExecutionPolicy Bypass -Command "Set-Location '%~dp0'; docker-compose down; Write-Host ''; Write-Host '  ✅  TelegramTrader arrêté.' -ForegroundColor Green; Write-Host ''; Write-Host '  Appuyez sur une touche pour fermer...' -ForegroundColor Gray; $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')"
