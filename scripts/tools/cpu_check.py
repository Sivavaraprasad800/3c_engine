import psutil, time

frs = [p for p in psutil.process_iter(['pid','name','cmdline','memory_info'])
       if 'python' in (p.info['name'] or '').lower()]

# Warm up
for p in frs:
    try: p.cpu_percent()
    except: pass

time.sleep(3)

print("=== FRS 3C Engine — CPU & RAM Report ===")
print(f"Measurement over 3 seconds | {psutil.cpu_count()} CPU cores")
print()

total_cpu = 0
total_ram = 0

for p in frs:
    try:
        cpu = p.cpu_percent()
        ram = p.memory_info().rss / 1024 / 1024
        cmd = (p.info['cmdline'] or ['?'])[-1][-40:]
        print(f"  PID {p.pid:6d}  CPU={cpu:5.1f}%  RAM={ram:5.0f} MB  ...{cmd}")
        total_cpu += cpu
        total_ram += ram
    except:
        pass

print()
print(f"  TOTAL FRS:    CPU={total_cpu:.1f}%  RAM={total_ram:.0f} MB")
print()

vm = psutil.virtual_memory()
print(f"  System CPU:   {psutil.cpu_percent(interval=1):.1f}% (all processes)")
print(f"  System RAM:   {vm.percent:.1f}% used  ({vm.used//1024//1024} MB / {vm.total//1024//1024} MB)")
