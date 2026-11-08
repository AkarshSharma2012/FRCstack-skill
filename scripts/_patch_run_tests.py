import os
c = open('scripts/_run_tests.py', encoding='utf-8').read()
# Fix REPO_ROOT: scripts/_run_tests.py is one level below repo root
c = c.replace(
    'REPO_ROOT = os.path.dirname(os.path.abspath(__file__))',
    'REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))'
)
open('scripts/_run_tests.py', 'w', encoding='utf-8').write(c)
print('patched OK')
