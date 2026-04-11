@echo off
REM ==========================================================================
REM ArkaOS - Claude Code Wrapper (cmd shim)
REM
REM Dispatches to bin\arka-claude.ps1, forwarding all arguments. Using a
REM .cmd shim means `arka-claude ...` works from cmd.exe, PowerShell, and
REM Windows Terminal alike, without the caller having to remember the
REM `powershell -File ...` invocation.
REM ==========================================================================
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0arka-claude.ps1" %*
exit /b %ERRORLEVEL%
