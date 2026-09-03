@echo off
echo Patching basicsr degradations.py for torchvision compatibility...
"C:\Users\siva\AppData\Local\Programs\Python\Python310\python.exe" -c "
import pathlib, re
f = pathlib.Path(r'C:\Users\siva\AppData\Local\Programs\Python\Python310\Lib\site-packages\basicsr\data\degradations.py')
txt = f.read_text()
old = 'from torchvision.transforms.functional_tensor import rgb_to_grayscale'
new = 'try:\n    from torchvision.transforms.functional_tensor import rgb_to_grayscale\nexcept ImportError:\n    from torchvision.transforms.functional import rgb_to_grayscale'
if old in txt:
    f.write_text(txt.replace(old, new))
    print('Patched OK')
else:
    print('Already patched or different version')
"
echo Done
