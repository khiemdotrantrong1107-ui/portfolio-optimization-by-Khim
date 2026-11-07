@echo off
chcp 65001 >nul
echo ============================================================================
echo   PORTFOLIO OPTIMIZATION BY KHIM — GITHUB & RENDER AUTO-DEPLOY HELPER
echo ============================================================================
cd /d "%~dp0"

where git >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [1/3] Dang cai dat Git chinh thuc qua Windows Winget...
    winget install --id Git.Git -e --source winget --accept-source-agreements --accept-package-agreements
    set "PATH=%PATH%;C:\Program Files\Git\cmd"
)

if not exist ".git" (
    echo [2/3] Khoi tao Git Repository cuc bo...
    git init
    git branch -M main
)

git add .
set /p COMMIT_MSG="Nhap noi dung cap nhat (Nhan Enter de dung mac dinh): "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=update: sync latest changes to Render cloud
git commit -m "%COMMIT_MSG%"

git remote get-url origin >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo.
    echo Hay tao 1 Public Repo ten la: portfolio-optimization-by-khim tren https://github.com/new
    set /p REPO_URL="Dan link GitHub Repo cua ban (VD: https://github.com/ten-ban/portfolio-optimization-by-khim.git): "
    git remote add origin %REPO_URL%
)

echo [3/3] Dang day code len GitHub (Render se tu dong cap nhat sau 1-2 phut)...
git push -u origin main
echo.
echo HOAN TAT! Hay kiem tra trang thai Live tren https://dashboard.render.com
pause
