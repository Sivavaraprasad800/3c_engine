@echo off
cd /D "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main"

echo Initializing git...
git init

git config user.email "sivavaraprasad800@gmail.com"
git config user.name "Siva Varaprasad"

echo Setting remote...
git remote remove origin 2>nul
git remote add origin https://github.com/Sivavaraprasad800/frs_ai_model.git

echo Staging files...
git add .

echo Status:
git status

echo Committing...
git commit -m "feat: FRS AI model - face engine, server, camera processor, DB layer, dashboard UI"

echo Pushing to feature/embedding-research branch...
git branch -M feature/embedding-research
git push -u origin feature/embedding-research

echo.
echo DONE. Check: https://github.com/Sivavaraprasad800/frs_ai_model
pause
