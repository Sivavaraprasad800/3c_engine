@echo off
echo Step 1: Patching basicsr...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main\patch_basicsr.py"
echo.
echo Step 2: Running GFPGAN compare...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main\gfpgan_compare.py" > "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main\gfpgan_result.txt" 2>&1
echo Done. Exit=%ERRORLEVEL%
