@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Player - Environment Initialization

echo Initializing environment...

set "NODE_DIR=%~dp0nodejs"
set "NODE_EXE=%NODE_DIR%\node.exe"
set "NPM_CLI=%NODE_DIR%\node_modules\npm\bin\npm-cli.js"
set "API_PORT=3000"
set "API_DIR=%~dp0api-enhanced"
set "GLOBAL_BAT=%APPDATA%\npm\NeteaseCloudMusicApi.bat"
set "ZIP_URL=https://codeload.github.com/xgxdmx/NeteaseMusic-API/zip/refs/heads/main"

:: ========== Node.js Detection ==========
if exist "%NODE_EXE%" (
    echo [OK] Built-in Node.js found
    set "PATH=%NODE_DIR%;%PATH%"
    goto verify_node
)

where node >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] System Node.js detected
    for /f "tokens=*" %%a in ('node -v') do echo     Version: %%a
    for /f "tokens=*" %%p in ('where node') do set "NODE_EXE=%%p"
    
    where npm >nul 2>&1
    if !errorlevel! == 0 (
        set "NPM_CLI="
        for /f "tokens=*" %%n in ('where npm ^| findstr /I "\.cmd$"') do (
            if not defined NPM_CLI set "NPM_CLI=%%n"
        )
        if not defined NPM_CLI (
            for /f "tokens=*" %%n in ('where npm') do (
                if not defined NPM_CLI set "NPM_CLI=%%n"
            )
        )
    ) else (
        echo [XX] System npm not found
        goto error_end
    )
    goto verify_node
)

echo [XX] Node.js not found, please install it first
goto error_end

:: ========== Verify Node.js ==========
:verify_node
echo [..] Verifying Node.js...
"%NODE_EXE%" -v >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] Node.js verification failed
    goto error_end
)
for /f "tokens=*" %%v in ('"%NODE_EXE%" -v') do echo [OK] Node.js %%v

echo [..] Verifying npm...
if not exist "%NPM_CLI%" (
    echo [XX] npm not found: "%NPM_CLI%"
    goto error_end
)

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    call "%NODE_EXE%" "%NPM_CLI%" -v >nul 2>&1
) else (
    call "%NPM_CLI%" -v >nul 2>&1
)

if !errorlevel! neq 0 (
    echo [XX] npm verification failed
    goto error_end
)

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    for /f "tokens=*" %%v in ('call "%NODE_EXE%" "%NPM_CLI%" -v') do echo [OK] npm %%v
) else (
    for /f "tokens=*" %%v in ('call "%NPM_CLI%" -v') do echo [OK] npm %%v
)

:: ========== Prepare api-enhanced ==========
echo [..] Preparing api-enhanced...

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    call "%NODE_EXE%" "%NPM_CLI%" config set registry https://registry.npmmirror.com >nul 2>&1
) else (
    call "%NPM_CLI%" config set registry https://registry.npmmirror.com >nul 2>&1
)

if not exist "%API_DIR%\package.json" (
    echo [..] Downloading api-enhanced...
    if exist "%API_DIR%" rmdir /s /q "%API_DIR%" 2>nul
    del "%TEMP%\api-enhanced.zip" 2>nul

    powershell -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP%\api-enhanced.zip' -TimeoutSec 120 -UseBasicParsing; exit 0 } catch { Write-Host '[XX] Download Exception: ' $_.Exception.Message; exit 1 }"

    if not exist "%TEMP%\api-enhanced.zip" (
        echo [XX] Download failed
        goto error_end
    )

    echo [OK] Download completed
    echo [..] Extracting...
    powershell -Command "try { Expand-Archive -Path '%TEMP%\api-enhanced.zip' -DestinationPath '%API_DIR%\_tmp' -Force; exit 0 } catch { Write-Host '[XX] 解压异常:' $_.Exception.Message; exit 1 }"

    if exist "%API_DIR%\_tmp\NeteaseMusic-API-main" (
        robocopy "%API_DIR%\_tmp\NeteaseMusic-API-main" "%API_DIR%" /E /MOVE >nul 2>&1
        if exist "%API_DIR%\_tmp" rmdir /s /q "%API_DIR%\_tmp" 2>nul
        del "%TEMP%\api-enhanced.zip" 2>nul
        echo [OK] Extraction completed
    ) else (
        echo [XX] Extraction error: expected directory not found
        goto error_end
    )

    if not exist "%API_DIR%\package.json" (
        echo [XX] package.json not found
        goto error_end
    )
    echo [OK] api-enhanced preparation completed
) else (
    echo [OK] api-enhanced ready
)

:: ========== Install Dependencies ==========
echo [..] Installing dependencies...
cd /d "%API_DIR%"

:: Check for pnpm
call pnpm -v >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] pnpm is ready
    goto do_install
)

:: Check npm global path
set "PNPM_PATH=%APPDATA%\npm\pnpm.cmd"
if exist "!PNPM_PATH!" (
    set "PATH=%APPDATA%\npm;%PATH%"
    call pnpm -v >nul 2>&1
    if !errorlevel! == 0 (
        echo [OK] pnpm is ready
        goto do_install
    )
)

:: Install pnpm
echo [..] pnpm not detected, installing...

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    call "%NODE_EXE%" "%NPM_CLI%" install -g pnpm
) else (
    call "%NPM_CLI%" install -g pnpm
)

if !errorlevel! neq 0 (
    echo [XX] pnpm installation failed
    goto error_end
)

set "PATH=%APPDATA%\npm;%PATH%"
call pnpm -v >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] pnpm still unavailable after installation
    goto error_end
)
echo [OK] pnpm installation completed

:do_install
set "HUSKY=0"
echo [..] Running pnpm install...
call pnpm install --dangerously-allow-all-builds

if exist "node_modules\express" (
    echo [OK] Dependencies installed
) else (
    echo [XX] Dependency installation failed
    goto error_end
)

:: ========== Create Launch Command ==========
echo [..] Creating launch command...
if not exist "%APPDATA%\npm" mkdir "%APPDATA%\npm"
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo title NeteaseCloudMusicApi
    echo cd /d "%API_DIR%"
    echo call pnpm start
    echo if errorlevel 1 pause
) > "%GLOBAL_BAT%"
echo [OK] Launch command created

:: ========== Start API Service ==========
echo [..] Starting API service...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":%API_PORT%[^0-9]"') do (
    echo [..] Port occupied, releasing...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
)
echo [OK] Port is ready

start /min "NeteaseCloudMusicApi" cmd /c "%GLOBAL_BAT%"

:: ========== Wait for API Ready ==========
echo [..] Waiting for API to be ready...
set "RETRY=0"
:check_api
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%API_PORT%/search?keywords=test' -TimeoutSec 5 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] API is ready
    timeout /t 2 /nobreak >nul
    goto start_downloader
)
set /a RETRY+=1
if !RETRY! lss 20 (
    echo     Retry !RETRY!...
    timeout /t 2 /nobreak >nul
    goto check_api
)
echo [XX] API startup timed out (waited ~40s)
goto error_end

:: ========== Start Downloader ==========
:start_downloader
echo [..] Starting downloader...
if not exist "%~dp0Music_player.exe" (
    echo [XX] Music_player.exe not found
    goto error_end
)
start "" "%~dp0Music_player.exe"

echo.
echo ========== Startup Complete ==========
echo API: http://127.0.0.1:%API_PORT%
echo =============================
timeout /t 3 /nobreak >nul
goto end

:: ========== Error Handling ==========
:error_end
echo.
echo [XX] An error occurred during setup, please check the logs above
echo Press any key to exit...
pause >nul
exit /b 1

:end
echo Press any key to exit...
pause >nul
exit /b 0