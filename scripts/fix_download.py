import os

files = [
    r'C:\PathForge\frontend\app\r\[shareId]\page.tsx',
    r'C:\PathForge\frontend\app\routes\[routeId]\page.tsx',
    r'C:\PathForge\frontend\components\Studio.tsx'
]

for p in files:
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()
    content = content.replace('download>', 'download="route.gpx">')
    with open(p, 'w', encoding='utf-8') as f:
        f.write(content)
print('Fixed download tags')
