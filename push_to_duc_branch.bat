@echo off
chcp 65001 >nul
echo ============================================================================
echo   PUSH PORTFOLIO OPTIMIZATION TO GITHUB — BRANCH: ĐỨC
echo ============================================================================
cd /d "%~dp0"
set "PATH=%PATH%;C:\Program Files\Git\cmd;C:\Program Files\Git\bin"

echo [1/3] Kiem tra cau hinh Git User...
git config user.name >nul 2>nul
if errorlevel 1 (
    echo [!] Chua co thong tin Git User. Dang dat mac dinh la Duc...
    git config user.name "Duc"
    git config user.email "duc@example.com"
)

echo [2/3] Dang commit cac thay doi moi nhat...
git add .
git commit -m "feat: SQLite Quant Database V2.1, Graphify architecture, comprehensive docs, and audit"

echo [3/3] Dang push len GitHub repos under branch 'đức'...
echo (Neu co hop thoai dang nhap GitHub hien len, vui long dang nhap tren trinh duyet)
git push -u origin đức

if errorlevel 1 goto :on_error

:on_success
echo ============================================================================
echo [SUCCESS] Push len branch 'đức' thanh cong!
echo Repos URL: https://github.com/khiemdotrantrong1107-ui/portfolio-optimization-by-Khim/tree/%%C4%91%%E1%%BB%%A9c
echo ============================================================================
goto :done

:on_error
echo ============================================================================
echo [!] CO LOI HOAC BI CANCEL TRONG KHI PUSH.
echo Vui long kiem tra quyen truy cap repository hoac token GitHub cua ban.
echo ============================================================================

:done
pause
