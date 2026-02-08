import subprocess
import os

def run(cmd):
    print(f"> {cmd}")
    subprocess.check_call(cmd, shell=True)

run("git pull")
run("git submodule update --init --recursive")

os.chdir("suncan")
run("git checkout main")
run("git pull")

print("Done.")
