@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title 网易云下载器 - 环境初始化

echo 环境安装中...

set "NODE_DIR=%~dp0nodejs"
set "NODE_EXE=%NODE_DIR%\node.exe"
set "NPM_CLI=%NODE_DIR%\node_modules\npm\bin\npm-cli.js"
set "API_PORT=3000"
set "API_DIR=%~dp0api-enhanced"
set "GLOBAL_BAT=%APPDATA%\npm\NeteaseCloudMusicApi.bat"
set "ZIP_URL=https://codeload.github.com/xgxdmx/NeteaseMusic-API/zip/refs/heads/main"

:: ========== Node.js 检测 ==========
if exist "%NODE_EXE%" (
    echo [OK] 内置 Node.js 已存在
    set "PATH=%NODE_DIR%;%PATH%"
    goto verify_node
)

where node >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] 系统 Node.js 已安装
    for /f "tokens=*" %%a in ('node -v') do echo     版本: %%a
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
        echo [XX] 系统 npm 未找到
        goto error_end
    )
    goto verify_node
)

echo [XX] 未找到 Node.js，请先安装
goto error_end

:: ========== 验证 Node.js ==========
:verify_node
echo [..] 验证 Node.js...
"%NODE_EXE%" -v >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] Node.js 验证失败
    goto error_end
)
for /f "tokens=*" %%v in ('"%NODE_EXE%" -v') do echo [OK] Node.js %%v

echo [..] 验证 npm...
if not exist "%NPM_CLI%" (
    echo [XX] npm 未找到: "%NPM_CLI%"
    goto error_end
)

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    call "%NODE_EXE%" "%NPM_CLI%" -v >nul 2>&1
) else (
    call "%NPM_CLI%" -v >nul 2>&1
)

if !errorlevel! neq 0 (
    echo [XX] npm 验证失败
    goto error_end
)

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    for /f "tokens=*" %%v in ('call "%NODE_EXE%" "%NPM_CLI%" -v') do echo [OK] npm %%v
) else (
    for /f "tokens=*" %%v in ('call "%NPM_CLI%" -v') do echo [OK] npm %%v
)

:: ========== 准备 api-enhanced ==========
echo [..] 准备 api-enhanced...

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    call "%NODE_EXE%" "%NPM_CLI%" config set registry https://registry.npmmirror.com >nul 2>&1
) else (
    call "%NPM_CLI%" config set registry https://registry.npmmirror.com >nul 2>&1
)

if not exist "%API_DIR%\package.json" (
    echo [..] 下载 api-enhanced...
    if exist "%API_DIR%" rmdir /s /q "%API_DIR%" 2>nul
    del "%TEMP%\api-enhanced.zip" 2>nul

    powershell -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP%\api-enhanced.zip' -TimeoutSec 120 -UseBasicParsing; exit 0 } catch { Write-Host '[XX] 下载异常:' $_.Exception.Message; exit 1 }"

    if not exist "%TEMP%\api-enhanced.zip" (
        echo [XX] 下载失败
        goto error_end
    )

    echo [OK] 下载完成
    echo [..] 解压...
    powershell -Command "try { Expand-Archive -Path '%TEMP%\api-enhanced.zip' -DestinationPath '%API_DIR%\_tmp' -Force; exit 0 } catch { Write-Host '[XX] 解压异常:' $_.Exception.Message; exit 1 }"

    if exist "%API_DIR%\_tmp\NeteaseMusic-API-main" (
        robocopy "%API_DIR%\_tmp\NeteaseMusic-API-main" "%API_DIR%" /E /MOVE >nul 2>&1
        if exist "%API_DIR%\_tmp" rmdir /s /q "%API_DIR%\_tmp" 2>nul
        del "%TEMP%\api-enhanced.zip" 2>nul
        echo [OK] 解压完成
    ) else (
        echo [XX] 解压异常：未找到预期目录
        goto error_end
    )

    if not exist "%API_DIR%\package.json" (
        echo [XX] 未找到 package.json
        goto error_end
    )
    echo [OK] api-enhanced 准备完成
) else (
    echo [OK] api-enhanced 已就绪
)

:: ========== 安装依赖 ==========
echo [..] 安装依赖...
cd /d "%API_DIR%"

:: 检测 pnpm
call pnpm -v >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] pnpm 已就绪
    goto do_install
)

:: 检测 npm 全局路径
set "PNPM_PATH=%APPDATA%\npm\pnpm.cmd"
if exist "!PNPM_PATH!" (
    set "PATH=%APPDATA%\npm;%PATH%"
    call pnpm -v >nul 2>&1
    if !errorlevel! == 0 (
        echo [OK] pnpm 已就绪
        goto do_install
    )
)

:: 安装 pnpm
echo [..] 未检测到 pnpm，正在安装...

echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    call "%NODE_EXE%" "%NPM_CLI%" install -g pnpm
) else (
    call "%NPM_CLI%" install -g pnpm
)

if !errorlevel! neq 0 (
    echo [XX] pnpm 安装失败
    goto error_end
)

set "PATH=%APPDATA%\npm;%PATH%"
call pnpm -v >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] pnpm 安装后仍不可用
    goto error_end
)
echo [OK] pnpm 安装完成

:do_install
set "HUSKY=0"
echo [..] 执行 pnpm install...
call pnpm install --dangerously-allow-all-builds

if exist "node_modules\express" (
    echo [OK] 依赖安装完成
) else (
    echo [XX] 依赖安装失败
    goto error_end
)

:: ========== 创建启动命令 ==========
echo [..] 创建启动命令...
if not exist "%APPDATA%\npm" mkdir "%APPDATA%\npm"
(
    echo @echo off
    echo chcp 65001 ^>nul
    echo title NeteaseCloudMusicApi
    echo cd /d "%API_DIR%"
    echo call pnpm start
    echo if errorlevel 1 pause
) > "%GLOBAL_BAT%"
echo [OK] 启动命令已创建

:: ========== 启动 API 服务 ==========
echo [..] 启动 API 服务...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":%API_PORT%[^0-9]"') do (
    echo [..] 发现端口 %API_PORT% 被 PID %%a 占用，正在释放...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
)
echo [OK] 端口 %API_PORT% 已就绪

start /min "NeteaseCloudMusicApi" cmd /c "%GLOBAL_BAT%"

:: ========== 等待 API 就绪 ==========
echo [..] 等待 API 就绪...
set "RETRY=0"
:check_api
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:%API_PORT%/search?keywords=test' -TimeoutSec 5 -UseBasicParsing; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] API 已就绪
    timeout /t 2 /nobreak >nul
    goto start_downloader
)
set /a RETRY+=1
if !RETRY! lss 20 (
    echo     第 !RETRY! 次重试...
    timeout /t 2 /nobreak >nul
    goto check_api
)
echo [XX] API 启动超时（已等待约 40 秒）
goto error_end

:: ========== 启动下载器 ==========
:start_downloader
echo [..] 启动下载器...
if not exist "%~dp0Music_player.exe" (
    echo [XX] 未找到 Music_player.exe
    goto error_end
)
start "" "%~dp0Music_player.exe"

echo.
echo ========== 启动完成 ==========
echo API: http://127.0.0.1:%API_PORT%
echo =============================
timeout /t 3 /nobreak >nul
goto end

:: ========== 错误处理 ==========
:error_end
echo.
echo [XX] 安装过程中出现错误，请检查上方日志
echo 按任意键退出...
pause >nul
exit /b 1

:end
echo 按任意键退出...
pause >nul
exit /b 0