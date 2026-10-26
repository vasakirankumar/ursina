import shutil, os, glob
print('git=', shutil.which('git'))
print('gh=', shutil.which('gh'))
print('winget=', shutil.which('winget'))
roots = [r'C:\Program Files', r'C:\Program Files (x86)', os.environ.get('LOCALAPPDATA',''), os.environ.get('PROGRAMFILES',''), os.environ.get('PROGRAMFILES(X86)',''), r'C:\\']
matches=[]
for root in roots:
    if not root or not os.path.exists(root):
        continue
    for pattern in ('**/git.exe','**/gh.exe','**/git.cmd','**/gh.cmd'):
        for path in glob.glob(os.path.join(root, pattern), recursive=True):
            if path.lower().endswith(('.exe','.cmd')):
                matches.append(path)
print('matches=', matches[:20])
