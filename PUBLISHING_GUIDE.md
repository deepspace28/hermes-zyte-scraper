# Publishing hermes-zyte-scraper to PyPI

## What we've done

1. ✓ Reorganized the repository into proper Python package structure
2. ✓ Created `pyproject.toml` with modern Python packaging metadata
3. ✓ Added entry point for Hermes auto-discovery
4. ✓ Built and tested the package (wheel + source distribution)
5. ✓ Updated README with new installation instructions

## Files created/modified

### New files:
- `pyproject.toml` - Modern Python packaging configuration
- `MANIFEST.in` - Package data manifest
- `reorganize.sh` - Script that moved files into `hermes_zyte_scraper/` package

### Modified files:
- `README.md` - Updated installation section with pip install method

### Structure changes:
```
Before:                          After:
.                                .
├── __init__.py                  ├── hermes_zyte_scraper/
├── operations.py                │   ├── __init__.py
├── schemas.py                   │   ├── operations.py
├── tools.py                     │   ├── schemas.py
├── zyte_helpers.py              │   ├── tools.py
├── plugin.yaml                  │   ├── zyte_helpers.py
├── skills/                      │   ├── plugin.yaml
├── templates/                   │   ├── skills/
├── scripts/                     │   ├── templates/
└── tests/                       │   ├── scripts/
                                 │   └── tests/
                                 ├── pyproject.toml
                                 ├── MANIFEST.in
                                 └── README.md
```

## Next steps

### 1. Push changes to GitHub

```bash
cd /tmp/hermes-zyte-scraper

# Stage all changes
git add -A

# Commit
git commit -m "feat: package as pip-installable plugin with entry point discovery

- Reorganized into hermes_zyte_scraper/ package structure
- Added pyproject.toml for modern Python packaging
- Configured entry point for automatic Hermes plugin discovery
- Updated README with pip install instructions
- Built and tested wheel + source distribution

Closes #48501 (hermes-agent PR) - now distributable as standalone plugin"

# Push to your fork
git push origin main
```

### 2. Publish to PyPI

#### A. Create PyPI account (if you don't have one)
- Go to https://pypi.org/account/register/
- Verify your email

#### B. Create API token
- Go to https://pypi.org/manage/account/token/
- Create token with scope "Entire account"
- Save the token (starts with `pypi-`)

#### C. Upload to PyPI

```bash
# Install twine (upload tool)
pip install twine

# Upload (it will prompt for username and password)
# Username: __token__
# Password: pypi-AgEIcHlwaS... (your API token)
python3 -m twine upload dist/*
```

**Or use token directly:**

```bash
python3 -m twine upload dist/* --username __token__ --password pypi-YOUR_TOKEN_HERE
```

### 3. Test the installation

After publishing to PyPI, anyone can install with:

```bash
pip install hermes-zyte-scraper
```

Hermes will auto-discover it via the entry point — no manual enabling needed.

### 4. Announce in Discord

Once published, share in the Nous Research Discord `#plugins-skills-and-skins` channel:

```
🎉 hermes-zyte-scraper v1.3.0 now on PyPI!

Production-grade Zyte + Scrapy Cloud integration for Hermes agents.

Install: pip install hermes-zyte-scraper
Repo: https://github.com/deepspace28/hermes-zyte-scraper

Features:
- zyte_extract: Multi-page extraction with auto schema inference
- zyte_build_spider: Natural language → Scrapy spiders
- Full Scrapy Cloud lifecycle (deploy, schedule, monitor, results)
- Battle-tested on real lead research workflows

As requested by the maintainers in PR #48501, this is now a standalone plugin using entry point discovery.
```

## Optional: GitHub Release

Create a release on GitHub matching the PyPI version:

1. Go to https://github.com/deepspace28/hermes-zyte-scraper/releases/new
2. Tag: `v1.3.0`
3. Title: `v1.3.0: PyPI-ready packaging`
4. Description: Copy the features list from above
5. Attach: `dist/hermes_zyte_scraper-1.3.0-py3-none-any.whl` and `.tar.gz`

## Verification checklist

Before publishing to PyPI:

- [ ] Package builds without errors: `python3 -m build`
- [ ] Wheel contains all necessary files: `unzip -l dist/*.whl | grep -E '(plugin.yaml|skills|templates)'`
- [ ] Entry point is registered: `grep hermes dist/*.whl` or check the wheel's `entry_points.txt`
- [ ] README renders correctly on GitHub
- [ ] All changes committed and pushed

## Troubleshooting

### If upload fails with "File already exists"
You can't overwrite published versions on PyPI. Bump the version in `pyproject.toml`:
```toml
version = "1.3.1"
```
Then rebuild and upload.

### If Hermes doesn't auto-discover the plugin
Check that the entry point is correct:
```bash
pip show -f hermes-zyte-scraper | grep entry_points
```

Should show:
```
[hermes.plugins]
hermes-zyte-scraper = hermes_zyte_scraper
```

## Future updates

When releasing new versions:

1. Update `version = "X.Y.Z"` in `pyproject.toml`
2. Rebuild: `python3 -m build`
3. Upload: `python3 -m twine upload dist/*`
4. Tag the release on GitHub
5. Announce in Discord

---

Good luck with the publication! 🚀
