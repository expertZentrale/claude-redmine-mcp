@echo off
rem Starts the Redmine MCP server binary for Windows, downloading and verifying it on first use.
rem stdout belongs to the MCP protocol, every message goes to stderr.
setlocal

if defined REDMINE_MCP_BINARY (
    "%REDMINE_MCP_BINARY%" %*
    exit /b %ERRORLEVEL%
)

set /p VERSION=<"%~dp0version.txt"
set "DATA=%REDMINE_MCP_DATA%"
if not defined DATA set "DATA=%LOCALAPPDATA%\redmine-mcp"
if "%DATA:~0,2%"=="${" set "DATA=%LOCALAPPDATA%\redmine-mcp"
set "EXE=%DATA%\%VERSION%\windows-x64\redmine-mcp\redmine-mcp.exe"

if not exist "%EXE%" (
    powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0install.ps1" -Version "%VERSION%" -Data "%DATA%" 1>&2
    if errorlevel 1 exit /b 1
)

"%EXE%" %*
exit /b %ERRORLEVEL%
