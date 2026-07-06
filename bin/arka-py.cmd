@echo off
REM ==========================================================================
REM ArkaOS - Python entrypoint (cmd shim)
REM
REM Dispatches to bin\arka-py.ps1, forwarding all arguments, so `arka-py ...`
REM works from cmd.exe, PowerShell, and Windows Terminal alike.
REM ==========================================================================
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0arka-py.ps1" %*
exit /b %ERRORLEVEL%
