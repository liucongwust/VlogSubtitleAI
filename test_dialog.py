import subprocess
script = 'tell application "System Events"\nactivate\nreturn POSIX path of (choose folder with prompt "选择")\nend tell'
result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
print("Code:", result.returncode)
print("Stdout:", repr(result.stdout))
print("Stderr:", repr(result.stderr))
