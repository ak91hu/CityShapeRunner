import sys

def fix_test(path):
    with open(path, 'r', encoding='utf-8') as f:
        c = f.read()
    c = c.replace('input[type="text"]', 'input')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(c)

fix_test(r'C:\PathForge\frontend\tests\interactions.spec.ts')
fix_test(r'C:\PathForge\frontend\tests\navigation.spec.ts')
print('Fixed!')
