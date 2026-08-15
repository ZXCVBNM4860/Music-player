@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title 网易云下载器 - 环境初始化

echo ============================================
echo  网易云下载器 - 一键环境初始化
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
::  1. 检测 Python 环境
:: ============================================================
echo [1/7] 检测 Python 环境...

where python >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] 未找到 Python，请先安装 Python 3.10 或更高版本
    echo      下载地址: https://www.python.org/downloads/
    goto error_end
)

for /f "tokens=*" %%v in ('python -V 2^>^&1') do echo [OK] %%v

:: 检查 pip
python -m pip -v >nul 2>&1
if !errorlevel! neq 0 (
    echo [XX] pip 不可用，尝试修复...
    python -m ensurepip --upgrade
    if !errorlevel! neq 0 goto error_end
)
echo [OK] pip 已就绪

:: ============================================================
::  2. 安装 Python 依赖
:: ============================================================
echo [2/7] 安装 Python 依赖...

if exist "%PROJECT_DIR%requirements.txt" (
    echo [..] 检测到 requirements.txt，正在安装...
    python -m pip install --upgrade pip -q
    python -m pip install -r "%PROJECT_DIR%requirements.txt" -q
    if !errorlevel! neq 0 (
        echo [XX] pip 依赖安装失败，尝试镜像源...
        python -m pip install -r "%PROJECT_DIR%requirements.txt" -i https://pypi.tuna.tsinghua.edu.cn/simple -q
        if !errorlevel! neq 0 (
            echo [XX] 依赖安装仍然失败
            goto error_end
        )
    )
    echo [OK] Python 依赖安装完成
) else (
    echo [..] 未找到 requirements.txt，跳过依赖安装
)

:: ============================================================
::  3. 检测 Node.js
:: ============================================================
echo [3/7] 检测 Node.js...

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
    
    :: 定位 npm（优先找 .cmd，再找 .js）
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
        echo [XX] 系统 npm 未找到
        goto error_end
    )
    goto verify_node
)

echo [XX] 未找到 Node.js，请先安装 Node.js 18 或更高版本
echo      下载地址: https://nodejs.org/
goto error_end

:: ============================================================
::  4. 验证 Node.js / npm
:: ============================================================
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

:: 判断 npm 是 .js 还是 .cmd，分别执行验证
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

:: ============================================================
::  5. 准备 api-enhanced
:: ============================================================
echo [4/7] 准备 api-enhanced...

:: 设置 npm 镜像
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

    :: 下载（带重试）
    set "RETRY=0"
    :download_retry
    powershell -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -Uri '%ZIP_URL%' -OutFile '%TEMP%\api-enhanced.zip' -TimeoutSec 180 -UseBasicParsing; exit 0 } catch { Write-Host '[XX] 下载异常:' $_.Exception.Message; exit 1 }"
    
    if not exist "%TEMP%\api-enhanced.zip" (
        set /a RETRY+=1
        if !RETRY! lss 3 (
            echo [..] 下载失败，重试 !RETRY!/3...
            timeout /t 3 /nobreak >nul
            goto download_retry
        )
        echo [XX] 下载失败
        goto error_end
    )

    echo [OK] 下载完成
    echo [..] 解压...
    powershell -Command "try { Expand-Archive -Path '%TEMP%\api-enhanced.zip' -DestinationPath '%API_DIR%\_tmp' -Force; exit 0 } catch { Write-Host '[XX] 解压异常:' $_.Exception.Message; exit 1 }"

    :: 寻找实际的解压目录（兼容不同 GitHub 压缩包结构）
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
        echo [XX] 解压后未找到 package.json
        goto error_end
    )
    echo [OK] api-enhanced 准备完成
) else (
    echo [OK] api-enhanced 已就绪
)

:: ============================================================
::  6. 安装 Node.js 依赖（pnpm）
:: ============================================================
echo [5/7] 安装 Node.js 依赖...

cd /d "%API_DIR%"

:: 检测 pnpm（路径中可能已有）
call pnpm -v >nul 2>&1
if !errorlevel! == 0 (
    echo [OK] pnpm 已就绪
    goto do_install
)

:: 检测全局 pnpm.cmd
set "PNPM_PATH=%APPDATA%\npm\pnpm.cmd"
if exist "!PNPM_PATH!" (
    set "PATH=%APPDATA%\npm;%PATH%"
    call pnpm -v >nul 2>&1
    if !errorlevel! == 0 (
        echo [OK] pnpm 已就绪
        goto do_install
    )
)

:: === 安装 pnpm（关键修复：正确处理 .js 和 .cmd） ===
echo [..] 未检测到 pnpm，正在安装...

:: 判断 npm 是 .js 还是 .cmd
echo "%NPM_CLI%" | findstr /I "\.js$" >nul
if !errorlevel! == 0 (
    :: npm 是 .js 文件 → 用 node 执行
    echo [..] npm 为 .js 文件，用 node 执行
    call "%NODE_EXE%" "%NPM_CLI%" install -g pnpm
) else (
    :: npm 是 .cmd 文件 → 直接调用
    echo [..] npm 为 .cmd 文件，直接执行
    call "%NPM_CLI%" install -g pnpm
)

if !errorlevel! neq 0 (
    echo [XX] pnpm 安装失败
    goto error_end
)

:: 将全局 npm 路径加入 PATH
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

:: ============================================================
::  7. 创建启动命令
:: ============================================================
echo [6/7] 创建启动命令...
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

:: ============================================================
::  8. 启动 API 服务
:: ============================================================
echo [..] 启动 API 服务...

:: 精确匹配端口 3000（避免匹配到 30001 等）
for /f "tokens=5" %%a in ('netstat -ano ^| findstr /R ":%API_PORT%[^0-9]"') do (
    echo [..] 发现端口 %API_PORT% 被 PID %%a 占用，正在释放...
    taskkill /F /PID %%a >nul 2>&1
    timeout /t 1 /nobreak >nul
)
echo [OK] 端口 %API_PORT% 已就绪

start /min "NeteaseCloudMusicApi" cmd /c "%GLOBAL_BAT%"

:: ============================================================
::  9. 等待 API 就绪
:: ============================================================
echo [7/7] 等待 API 就绪...
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

:: ============================================================
::  10. 启动下载器
:: ============================================================
:start_downloader
echo [..] 启动下载器...

if not exist "%PROJECT_DIR%%EXE_NAME%" (
    echo [XX] 未找到 %EXE_NAME%
    echo      请确保已运行 PyInstaller 打包，或修改脚本中的 EXE_NAME 变量
    goto error_end
)

start "" "%PROJECT_DIR%%EXE_NAME%"

echo.
echo ============================================
echo  启动完成！
echo  API: http://127.0.0.1:%API_PORT%
echo  项目: %PROJECT_DIR%
echo ============================================
timeout /t 3 /nobreak >nul
goto end

:: ============================================================
::  错误处理
:: ============================================================
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
