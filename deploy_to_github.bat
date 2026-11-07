@echo off
chcp 65001 >nul
echo ============================================================================
echo   PORTFOLIO OPTIMIZATION BY KHIM — GITHUB & RENDER AUTO-DEPLOY
echo ============================================================================
cd /d "%~dp0"
set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin"

echo [1/3] Kiem tra trang thai ma nguon...
git remote get-url origin >nul 2>nul
if errorlevel 1 (
    git remote add origin https://github.com/khiemdotrantrong1107-ui/portfolio-optimization-by-Khim.git
)

git add .
git commit -m "feat: release Portfolio Optimization by Khim v2.4" >nul 2>nul

echo [2/3] Dang day code len GitHub...
git push -u origin main
if errorlevel 1 goto :on_error

:on_success
echo ============================================================================
echo [3/3] THANH CONG! Code da duoc day len GitHub thanh cong.
echo Render dang tu dong build va cap nhat ung dung.
echo   - Repo GitHub: https://github.com/khiemdotrantrong1107-ui/portfolio-optimization-by-Khim
echo   - Link Web:    https://portfolio-optimization-by-khim.onrender.com
echo ============================================================================
goto :done

:on_error
echo ============================================================================
echo [!] CO LOI KHI PUSH LEN GITHUB.
echo Vui long kiem tra lai ket noi hoac thong tin dang nhap GitHub cua ban.
echo ============================================================================

:done
pause
