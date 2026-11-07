@echo off
chcp 65001 >nul
echo ============================================================================
echo   PORTFOLIO OPTIMIZATION BY KHIM — GITHUB & RENDER AUTO-DEPLOY
echo ============================================================================
cd /d "%~dp0"
set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin"

echo [1/3] Kiem tra trang thai ma nguon...
git remote get-url origin >nul 2>nul
if %ERRORLEVEL% neq 0 (
    git remote add origin https://github.com/khiemdotrantrong1107-ui/portfolio-optimization-by-Khim.git
)

git add .
git commit -m "feat: release Portfolio Optimization by Khim v2.4" >nul 2>nul

echo [2/3] Dang day code len GitHub: khiemdotrantrong1107-ui/portfolio-optimization-by-Khim...
echo (Neu co cua so trinh duyet hien ra, ban chi can bam 'Sign in with your browser' de xac thuc 1 lan)
echo.
git push -u origin main

echo.
if %ERRORLEVEL% equ 0 (
    echo ============================================================================
    echo [3/3] THANH CONG! Code da duoc day len GitHub.
    echo Render se tu dong phat hien va bat dau Build trong vong 1-2 phut.
    echo Ban co the theo doi trang thai tai:
    echo   - GitHub: https://github.com/khiemdotrantrong1107-ui/portfolio-optimization-by-Khim
    echo   - Render: https://dashboard.render.com (Tab 'Events' hoac 'Logs')
    echo   - Link Web: https://portfolio-optimization-by-khim.onrender.com
    echo ============================================================================
) else (
    echo ============================================================================
    echo [!] CO LOI KHI PUSH LEN GITHUB.
    echo Vui long kiem tra lai ket noi hoac thong tin dang nhap GitHub cua ban.
    echo ============================================================================
)

pause
