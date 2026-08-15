@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title Netease Music Downloader - Environment Initialization

echo ============================================
echo  Netease Music Downloader - One-Click Setup
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"
set "NODE_DIR=%PROJECT_DIR%nodejs"
set "NODE_EXE=%NODE_DIR%\node.exe"
set "NPM_CLI=%NODE_DIR%\node_modules\npm\bin\npm-cli.js"
set "API_PORT=3000"
set "API_DIR=%PROJECT_DIR%api-enhanced"
set "GLOBAL_BAT=%APPDATA%\npm\NeteaseCloudMusicApi.bat"
set "ZIP_URL=https://codeload.github.com/xgxdmx/NeteaseMusic-API/zip/refs/heads/main"
set "EXE_NAME=MusicPlayer.exe"

:: ============================================================
::  1. Check Python environment
:: ============================================================
echo [1/7] Checking Python environment...

where python >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] Python not found. Please install Python 3.10 or later.
    echo      Download: https://www.python.org/downloads/
    goto error_end
)

for /f "tokens=*" %%v in ('python -V 2^>^&1') do echo [OK] %%v

:: Check pip
python -m pip -v >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] pip unavailable. Attempting to fix...
    python -m ensurepip --upgrade
    if !errorlevel! neq 0 goto error_end
)
echo [OK] pip ready

:: ============================================================
::  2. Install Python dependencies
:: ============================================================
echo [2/7] Installing Python dependencies...

if exist "%PROJECT_DIR%requirements.txt" (
    echo [..] Found requirements.txt, installing...
    python -m pip install --upgrade pip -q
    python -m pip install -r "%PROJECT_DIR%requirements.txt" -q
    if !errorlevel! neq 0 (
        echo [XX] pip install failed. Trying mirror...
        python -m pip install -r "%PROJECT_DIR%requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple -q
        if !errorlevel! neq 0 (
            echo [XX] Dependency installation still failed
            goto error_end
        )
    )
    echo [OK] Python dependencies installed
) else (
    echo [..] requirements.txt not found, skipping Python dependencies
)

:: ============================================================
::  3. Check Node.js
:: ============================================================
echo [3/7] Checking Node.js...

if exist "%NODE_EXE%" (
    echo [OK] Bundled Node.js found
    set "PATH=%NODE_DIR%;%PATH%"
    goto verify_node
)

where node >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] System Node.js found
    for /f "tokens=*" %%a in ('node -v') do echo     Version: %%a
    for /f "tokens=*" %%p in ('where node') do set "NODE_EXE=%%p"
    
    :: Locate npm (prefer .cmd, fallback to .js)
    where npm >nul 2>&1
    if !errorlevel! == 0 (
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

echo [XX] Node.js not found. Please install Node.js 18 or later.
echo      Download: https://nodejs.org/
goto error_end

:: ============================================================
::  4. Verify Node.js / npm
:: ============================================================
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

:: Check if npm is .js or .cmd and run accordingly
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

:: ============================================================
::  5. Prepare api-enhanced
:: ============================================================
echo [4/7] Preparing api-enhanced...

:: Set npm mirror
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

    :: Download with retry
    set "RETRY=0"
    :download_retry
    powershell -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP%\api-enhanced.zip' -TimeoutSec 180 -UseBasicParsing; exit 0 } catch { Write-Host '[XX] Download error:' $_.Exception.Message; exit 1 }"
    
    if not exist "%TEMP%\api-enhanced.zip" (
        set /a RETRY+=1
        if !RETRY! lss 3 (
            echo [..] Download failed, retry !RETRY!/3...
            timeout /t 3 /nobreak >nul
            goto download_retry
        )
        echo [XX] Download failed
        goto error_end
    )

    echo [OK] Download complete
    echo [..] Extracting...
    powershell -Command "try { Expand-Archive -Path '%TEMP%\api-enhanced.zip' -DestinationPath '%API_DIR%\_tmp' -Force; exit 0 } catch { Write-Host '[XX] Extraction error:' $_.Exception.Message; exit 1 }"

    :: Locate extracted directory (handle different archive structures)
    if exist "%API_DIR%\_tmp\NeteaseMusic-API-main" (
        robocopy "%API_DIR%\_tmp\NeteaseMusic-API-main" "%API_DIR%" /E /MOVE >nul 2>&1
    ) else (
        for /d %%d in ("%API_DIR%\_tmp\*") do (
            robocopy "%%d" "%API_DIR%" /E /MOVE >nul 2>&1
            goto unpack_done
        )
        :unpack_done
    )

    if exist "%API_DIR%\_tmp" rmdir /s /q "%API_DIR%\_tmp" 2>nul
    del "%TEMP%\api-enhanced.zip" 2>nul

    if not exist "%API_DIR%\package.json" (
        echo [XX] package.json not found after extraction
        goto error_end
    )
    echo [OK] api-enhanced ready
) else (
    echo [OK] api-enhanced already exists
)

:: ============================================================
::  6. Install Node.js dependencies (pnpm)
:: ============================================================
echo [5/7] Installing Node.js dependencies...

cd /d "%API_DIR%"

:: Check if pnpm is available
call pnpm -v >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] pnpm ready
    goto do_install
)

:: Check global pnpm.cmd
set "PNPM_PATH=%APPDATA%\npm\pnpm.cmd"
if exist "!PNPM_PATH!" (
    set "PATH=%APPDATA%\npm;%PATH%"
    call pnpm -v >nul 2>&1
    if !errorlevel! == 0 (
        echo [OK] pnpm ready
        goto do_install
    )
)

:: === Install pnpm (critical fix: handle .js and .cmd correctly) ===
echo [..] pnpm not found. Installing...

:: Check if npm is .js or .cmd
echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    :: npm is .js → run with node
    echo [..] npm is .js, running with node
    call "%NODE_EXE%" "%NPM_CLI%" install -g pnpm
) else (
    :: npm is .cmd → run directly
    echo [..] npm is .cmd, running directly
    call "%NPM_CLI%" install -g pnpm
)

if !errorlevel! neq 0 (
    echo [XX] pnpm installation failed
    goto error_end
)

:: Add global npm bin to PATH
set "PATH=%APPDATA%\npm;%PATH%"
call pnpm -v >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] pnpm still unavailable after installation
    goto error_end
)
echo [OK] pnpm installed

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

:: ============================================================
::  7. Create startup command
:: ============================================================
echo [6/7] Creating startup command...
if not exist "%APPDATA%\npm" mkdir "%APPDATA%\npm"
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo title NeteaseCloudMusicApi
    echo cd /d "%API_DIR%"
    echo call pnpm start
    echo if errorlevel 1 pause
) > "%GLOBAL_BAT%"
echo [OK] Startup command created

:: ============================================================
::  8. Start API service
:: ============================================================
echo [..] Starting API service...

:: Match port 3000 exactly (avoid matching 30001 etc.)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":%API_PORT%[^0-9]"') do (
    echo [..] Port %API_PORT% occupied by PID %%a, releasing...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
)
echo [OK] Port %API_PORT% ready

start /min "NeteaseCloudMusicApi" cmd /c "%GLOBAL_BAT%"

:: ============================================================
::  9. Wait for API to be ready
:: ============================================================
echo [7/7] Waiting for API to be ready...
set "RETRY=0"
:check_api
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%API_PORT%/search?keywords=test' -TimeoutSec 5 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] API ready
    timeout /t 2 /nobreak >nul
    goto start_downloader
)
set /a RETRY+=1
if !RETRY! lss 20 (
    echo     Retry !RETRY!/20...
    timeout /t 2 /nobreak >nul
    goto check_api
)
echo [XX] API startup timeout (waited ~40 seconds)
goto error_end

:: ============================================================
::  10. Start downloader
:: ============================================================
:start_downloader
echo [..] Starting downloader...

if not exist "%PROJECT_DIR%%EXE_NAME%" (
    echo [XX] %EXE_NAME% not found
    echo      Please run PyInstaller first, or update EXE_NAME in this script
    goto error_end
)

start "" "%PROJECT_DIR%%EXE_NAME%"

echo.
echo ============================================
echo  Startup complete!
echo  API: http://127.0.0.1:%API_PORT%
echo  Project: %PROJECT_DIR%
echo ============================================
timeout /t 3 /nobreak >nul
goto end

:: ============================================================
::  Error handler
:: ============================================================
:error_end
echo.
echo [XX] An error occurred during setup. Please check the logs above.
echo Press any key to exit...
pause >nul
exit /b 1

:end
echo Press any key to exit...
pause >nul
exit /b 0
