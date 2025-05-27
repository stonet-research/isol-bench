# Benchmark

Scale up containers running BE-app 4k randread, QD=1, io_uring, direct, registerfiles, fixedbufs. Use Optane.
Scale up one container with QD running BE-app 4k randread, io_uring, direct, registerfiles, fixedbufs. Use Optane.

# CPU overhead
Use fio ((usr_cpu + sys_cpu) * #process) / 100, and ctx

./cpu_overhead.sh
python3 analyze.py

# Lock overhead
Perf record -> fio start -> perf report -> grep for common locks