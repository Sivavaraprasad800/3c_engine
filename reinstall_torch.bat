@echo off
echo Reinstalling torch 2.0.1 + torchvision 0.15.2 on Python 3.10...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" -m pip install torch==2.0.1 torchvision==0.15.2 --force-reinstall --no-cache-dir
echo Done. Exit=%ERRORLEVEL%
