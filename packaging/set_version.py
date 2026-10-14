"""
Sets the release version everywhere it is recorded: package, plugin manifest and launcher.
"""

import json
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
version = sys.argv[1]

if not re.fullmatch(r'\d+\.\d+\.\d+', version):
    sys.exit(f'Version must look like 1.2.3, got {version!r}')

init = root / 'src' / 'redmine_mcp' / '__init__.py'
init.write_text(re.sub(r"__version__ = '[^']*'", f"__version__ = '{version}'", init.read_text()))

manifest = root / '.claude-plugin' / 'plugin.json'
data = json.loads(manifest.read_text(encoding='utf-8'))
data['version'] = version
manifest.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

(root / 'bin' / 'version.txt').write_text(version + '\n')
