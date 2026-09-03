@echo off
echo =====================================================
echo  Pushing FRS AI Model to GitHub
echo =====================================================
echo.

cd /D "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main"

echo Step 1: Initialize git repo...
git init

echo.
echo Step 2: Set git config...
git config user.email "siva@frs"
git config user.name "Siva Varaprasad"

echo.
echo Step 3: Add remote origin...
git remote remove origin 2>nul
git remote add origin https://github.com/Sivavaraprasad800/frs_ai_model.git

echo.
echo Step 4: Stage all files (respecting .gitignore)...
git add .

echo.
echo Step 5: Check what will be committed...
git status

echo.
echo Step 6: Commit...
git commit -m "feat: FRS AI model with embedding averaging, image quality research scripts"

echo.
echo Step 7: Push to new branch feature/embedding-research...
git branch -M feature/embedding-research
git push -u origin feature/embedding-research

echo.
echo =====================================================
echo  Done! Check GitHub for the new branch.
echo =====================================================
pause
