@echo off
echo Step 1: Patching basicsr for numpy compatibility...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main\patch_basicsr.py"
echo.
echo Step 2: Running detected face enhancement A/B test...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main\compare_detected_enhancement.py" > "D:\kk]\siva\frs_ai_model-main\frs_ai_model-main\detected_result.txt" 2>&1
echo.
echo Done. Results in detected_result.txt
