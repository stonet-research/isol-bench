import subprocess

def exec_cmd(cmd, sudo=True):
    final_cmd = f'{"sudo" if sudo else ""} {cmd}'
    return subprocess.check_output(final_cmd, shell=True, stderr=subprocess.STDOUT)

def set_sysfs(path, value):
    subprocess.check_call(f"echo {value} | sudo tee {path} > /dev/null", shell=True)

