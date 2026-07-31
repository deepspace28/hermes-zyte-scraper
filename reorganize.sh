#!/bin/bash
# Reorganize hermes-zyte-scraper into proper Python package structure

set -e

echo "Reorganizing hermes-zyte-scraper for pip distribution..."

# Create package directory
mkdir -p hermes_zyte_scraper

# Move Python modules into package
for file in __init__.py operations.py schemas.py tools.py zyte_helpers.py; do
    if [ -f "$file" ]; then
        echo "Moving $file -> hermes_zyte_scraper/"
        mv "$file" hermes_zyte_scraper/
    fi
done

# Move supporting directories
for dir in skills templates scripts tests; do
    if [ -d "$dir" ]; then
        echo "Moving $dir -> hermes_zyte_scraper/"
        mv "$dir" hermes_zyte_scraper/
    fi
done

# Move plugin.yaml into package
if [ -f "plugin.yaml" ]; then
    echo "Moving plugin.yaml -> hermes_zyte_scraper/"
    mv plugin.yaml hermes_zyte_scraper/
fi

echo "✓ Package structure reorganized"
echo ""
echo "New structure:"
ls -la hermes_zyte_scraper/
