"""Run isolated fixtures from the repository root; never installs into live Minecraft."""
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
(root/"work").mkdir(exist_ok=True);(root/"build").mkdir(exist_ok=True)
for test in sorted((root/"tools").glob("Check-*.py")):
    print(test.name,flush=True)
    subprocess.run([sys.executable,str(test)],cwd=root,check=True)
print("All checks passed.")
