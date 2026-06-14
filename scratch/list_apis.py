import json
from pathlib import Path

# Load catalog
catalog_path = Path('maintenance_core/module_catalog/module_api_catalog.json')
if not catalog_path.exists():
    print("Catalog not found")
    exit(1)

with open(catalog_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

targets = {
    'mugenforge/factory_plus.py',
    'mugenforge/factory_ultra.py',
    'mugenforge/forge_flow.py',
    'mugenforge/gap_closer.py',
    'mugenforge/creator_os.py',
    'mugenforge/forge_beyond.py',
    'mugenforge/creator_suite_visual.py',
    'mugenforge/authority_lab.py',
    'mugenforge/forge_polish.py',
    'mugenforge/engine_authority.py',
    'mugenforge/authority_core.py'
}

by_module = {}
for item in data['items']:
    mod = item['module'].replace('\\\\', '/').replace('\\', '/')
    if mod in targets:
        by_module.setdefault(mod, []).append((item['kind'], item['signature'], item['line']))

out_lines = []
for mod in sorted(targets):
    out_lines.append(f"=== {mod} ===")
    apis = by_module.get(mod, [])
    for kind, sig, line in sorted(apis, key=lambda x: (x[0], x[1])):
        if kind not in ('method', 'constant'):
            out_lines.append(f"  {kind}: {sig} (line {line})")

with open('scratch/apis_list.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out_lines) + '\n')
print("Wrote scratch/apis_list.txt")
