# Project Structure

## Overview
Vibe Route Planner - An intelligent travel planning application (currently in Phase 1: Data Collection)

```
vibe-route-planner/
├── README.md                      # Complete documentation
├── QUICKSTART.md                  # Quick start guide
├── xiaohongshu_api.py            # Core API (main code)
├── start.sh                       # Start MCP server
├── login.sh                       # Login check and QR code generation
├── stop.sh                        # Stop server
├── cookies.json                   # Login credentials (auto-generated)
├── docker/
│   ├── docker-compose.yml        # Docker configuration
│   └── start-server.sh           # Docker startup script
├── tokyo_coffee_clean.txt        # Sample output (Tokyo Coffee)
└── tokyo_travel_notes.txt        # Test output
```

## Core File Descriptions

### xiaohongshu_api.py
The main Python API containing:
- `XiaohongshuAPI` class
- `check_login()` - Check login status
- `search()` - Search for note list
- `get_note_content()` - Get single note content
- `search_and_extract()` - Search and extract full content

### start.sh
One-click Docker container startup to run MCP server

### login.sh
Check login status, generates QR code if not logged in

### stop.sh
Stop Docker container

## Output Files

Each search generates a file with the format:
- `{keyword}_notes.txt`

Examples:
- `tokyo_coffee_notes.txt`
- `tokyo_travel_notes.txt`

## Unnecessary Files

The following files can be deleted (already in .gitignore):
- `*_notes.txt` - Output files
- `qrcode.png` - Temporary QR code
- `tokyo_coffee_results.json` - Raw search results
