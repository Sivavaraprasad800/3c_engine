@echo off
echo Downgrading numpy to 1.x for basicsr compatibility...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" -m pip install "numpy<2" --force-reinstall --quiet
echo Done
