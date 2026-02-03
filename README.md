# Vibe Route Planner 🗺️

**An intelligent travel route planning application** that helps users discover personalized travel destinations and create optimized itineraries based on their preferences.

## 🚧 Project Status: Under Construction

Currently implemented:
- ✅ **Phase 1: Data Scraping** - Xiaohongshu (RedNote) content extraction for travel research

Coming soon:
- 🔄 User preference input system
- 🔄 Route optimization algorithm
- 🔄 Interactive map generation
- 🔄 Personalized itinerary output

---

## Current Feature: Xiaohongshu Content Scraper

A data collection module that searches Xiaohongshu for travel-related content and extracts note titles and body content for route planning research.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Usage](#usage)
- [API Usage](#api-usage)
- [File Description](#file-description)
- [Troubleshooting](#troubleshooting)

## 🚀 Quick Start

### First-Time Setup

1. **Start the MCP Server**
   ```bash
   ./start.sh
   ```

2. **Login to Xiaohongshu Account**
   ```bash
   ./login.sh
   ```
   - Generates a `qrcode.png` QR code
   - Scan with Xiaohongshu app to login
   - Cookies will be automatically saved after successful login

3. **Search and Extract Content**
   ```bash
   python3 xiaohongshu_api.py "Tokyo Coffee" 10
   ```
   - First parameter: search keyword
   - Second parameter: number of notes to extract (optional, default 10)

### Every Time You Reopen VSCode

```bash
# 1. Start the server (if not running)
./start.sh

# 2. Check login (if cookies expired)
./login.sh

# 3. Start using
python3 xiaohongshu_api.py "your search keyword" 10
```

## 📖 Usage

### Basic Usage

Search for a single keyword:
```bash
python3 xiaohongshu_api.py "Tokyo Coffee" 15
```

Search for keywords with spaces:
```bash
python3 xiaohongshu_api.py "Tokyo Travel Guide" 10
```

### Output Files

Search results are automatically saved to files, with filenames generated from the keywords:
- Search "Tokyo Coffee" → `tokyo_coffee_notes.txt`
- Search "Tokyo Travel" → `tokyo_travel_notes.txt`

### Output Format

Each note contains:
- **Title**
- **Body Content** (includes address, recommendations, detailed descriptions, etc.)

Example:
```
====================================================================================================
Note 1
====================================================================================================
Title: Tokyo Must-Visit Coffee Shops

☕️1. STREAMER COFFEE (Photos 1-4)
Shop opened by world latte art champion Hiroshi Sawada, specializing in latte art☕️
...
🏠: 〒106-0032 Tokyo, Minato City, Roppongi, 6 Chome−11−16
====================================================================================================
```

## 💻 API Usage

### Using in Python Code

```python
from xiaohongshu_api import XiaohongshuAPI

# Create API client
api = XiaohongshuAPI()

# Check login
if not api.check_login():
    print("Please login first")
    exit()

# Search for notes (get list only)
feeds = api.search("Tokyo Coffee", max_results=20)
print(f"Found {len(feeds)} notes")

# Get single note content
note = api.get_note_content(feeds[0]['id'], feeds[0]['xsecToken'])
print(f"Title: {note['title']}")
print(f"Content: {note['content']}")

# Search and extract full content (recommended)
results = api.search_and_extract("Tokyo Food", max_notes=10)
for note in results:
    print(note['title'])
    print(note['content'])
```

### API Methods

| Method | Description | Parameters | Return Value |
|--------|-------------|------------|--------------|
| `check_login()` | Check login status | None | bool |
| `search(keyword, max_results)` | Search note list | keyword: Search term<br>max_results: Max number | List[Dict] |
| `get_note_content(feed_id, xsec_token)` | Get note details | feed_id: Note ID<br>xsec_token: Security token | Dict or None |
| `search_and_extract(keyword, max_notes, delay)` | Search and extract content | keyword: Search term<br>max_notes: Number<br>delay: Request interval | List[Dict] |

## 📁 File Description

### Core Files
- `xiaohongshu_api.py` - Main API (**core code**)
- `start.sh` - Start MCP server
- `login.sh` - Login check and QR code generation
- `stop.sh` - Stop server

### Configuration Files
- `docker/docker-compose.yml` - Docker configuration
- `cookies.json` - Login credentials (auto-generated)

### Output Files
- `*_notes.txt` - Extracted note content
- `qrcode.png` - Login QR code (temporary)

## 🔧 Troubleshooting

### Issue 1: Server Won't Start

**Symptoms**: Running `./start.sh` fails

**Solutions**:
1. Confirm Docker is running
2. Check if port 18060 is occupied:
   ```bash
   lsof -i :18060
   ```
3. View logs:
   ```bash
   docker logs xiaohongshu-mcp-server
   ```

### Issue 2: Login Failed or Cookies Expired

**Symptoms**: Prompted "Not logged in"

**Solutions**:
```bash
# Re-login
./login.sh

# After scanning, check again
./login.sh
```

### Issue 3: Search Returns Empty Results

**Possible Causes**:
1. No related notes for the keyword
2. Network connection issues
3. Rate limited by Xiaohongshu

**Solutions**:
- Try a different keyword
- Increase request interval (modify `delay` parameter)
- Wait a while and try again

### Issue 4: Note Extraction Fails

**Symptoms**: Some notes show "❌ Retrieval Failed"

**Causes**:
- API rate limiting
- Network timeout
- Note has been deleted

**Solutions**:
- Normal occurrence, ignore failed notes
- Reduce `max_notes` quantity
- Increase `delay` time interval

## 📌 Usage Recommendations

1. **First-time use**: Recommend starting with 5-10 notes for testing
2. **Batch scraping**: Recommend no more than 20 notes per run to avoid rate limiting
3. **Request intervals**: Default 1.5 seconds, increase to 2-3 seconds if failures are frequent
4. **Cookie management**: Approximately need to re-login once per week

## 🎯 Use Cases

### Travel Planning
```bash
python3 xiaohongshu_api.py "Tokyo Food Recommendations" 15
python3 xiaohongshu_api.py "Kyoto Accommodation Guide" 10
python3 xiaohongshu_api.py "Osaka Shopping List" 10
```

### Coffee Shop Exploration
```bash
python3 xiaohongshu_api.py "Shanghai Coffee" 20
python3 xiaohongshu_api.py "Beijing Specialty Coffee" 15
```

### Product Research
```bash
python3 xiaohongshu_api.py "iPhone 16 Review" 10
python3 xiaohongshu_api.py "Skincare Recommendations" 15
```

## 🙏 Acknowledgments

This project's data scraping module is built upon the excellent work by **[@xpzouying](https://github.com/xpzouying)**:
- **Original Repository**: [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)
- **Author**: xpzouying
- **License**: As specified in the original repository

Special thanks for providing the foundation for the Xiaohongshu MCP server integration.

## 🔗 Related Resources

- Xiaohongshu MCP Server (original): https://github.com/xpzouying/xiaohongshu-mcp
- MCP protocol documentation: Model Context Protocol

## ⚠️ Important Notes

1. **For learning and research only**: Please comply with Xiaohongshu's terms of service
2. **Request frequency**: Don't make requests too frequently to avoid account suspension
3. **Data usage**: Scraped data is for personal use only, do not commercialize
4. **Privacy protection**: Do not scrape and distribute user privacy information

## 📝 Changelog

### v1.0.0 (2026-01-20)
- ✅ Initial version
- ✅ Support searching for any keyword
- ✅ Auto-extract title and body text
- ✅ Simplified startup process
- ✅ Complete error handling
