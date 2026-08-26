@echo off
REM run_tests.cmd - pdca-skill 测试运行器(Windows)
REM 用法: tests\run_tests.cmd 或双击运行
REM 依赖: Python 3.8+ 和 pytest

setlocal

REM v1.0.4: 强制 UTF-8 模式，防 GBK 控制台下子进程 UTF-8 输出解码崩溃
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM 切到项目根(SKILL.md 所在目录)
cd /d "%~dp0\.."

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 未安装或不在 PATH
    exit /b 1
)

REM 检查 pytest
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo [INFO] pytest 未安装,正在安装...
    python -m pip install pytest
    if errorlevel 1 (
        echo [ERROR] pytest 安装失败
        exit /b 1
    )
)

REM 跑测试
echo ========================================
echo Running pdca-skill tests...
echo ========================================
python -m pytest tests/ -v
set EXITCODE=%ERRORLEVEL%

echo.
echo ========================================
if %EXITCODE% EQU 0 (
    echo [PASS] All tests passed.
) else (
    echo [FAIL] Some tests failed. Exit code: %EXITCODE%
)
echo ========================================

exit /b %EXITCODE%
