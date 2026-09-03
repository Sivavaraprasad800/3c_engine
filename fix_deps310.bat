@echo off
echo Fixing Python 3.10 dependencies for GFPGAN compare...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" -m pip install "faiss-cpu" --quiet
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" -m pip install "torchvision==0.15.2" "torch==2.0.1" --quiet
echo Done.
