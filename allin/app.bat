@echo off
chcp 65001 >nul
start "" /D "%~dp0" "E:\python\pythonw.exe" "%~dp0app.py"
