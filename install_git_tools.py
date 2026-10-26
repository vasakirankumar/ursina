import subprocess
import shutil

winget = r"C:\Users\STAFF\AppData\Local\Microsoft\WindowsApps\winget.exe"

for app in ["Git.Git", "GitHub.cli"]:
    print(f"Installing {app}...")
    result = subprocess.run(
        [winget, "install", "--id", app, "-e", "--source", "winget"],
        capture_output=True,
        text=True,
    )
    print(f"returncode={result.returncode}")
    if result.stdout:
        print(result.stdout[:4000])
    if result.stderr:
        print(result.stderr[:4000])
    print("---")

print("git=", shutil.which("git"))
print("gh=", shutil.which("gh"))
