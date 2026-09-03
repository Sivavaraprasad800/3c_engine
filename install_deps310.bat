@echo off
echo Installing CodeFormer dependencies on Python 3.10...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" -m pip install basicsr facexlib gfpgan torch torchvision opencv-python numpy pymysql insightface onnxruntime
echo.
echo DONE
pause
