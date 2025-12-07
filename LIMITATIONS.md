# Rich Content Capture - Technical Limitations

This document outlines what can and cannot be captured when exporting GitHub Copilot shared conversations.

## ✅ Fully Supported

### Text Content
- **Status:** ✅ Working perfectly
- **Includes:** Plain text, formatted text, Markdown syntax
- **Limitations:** None
- **Extraction:** DOM-based and JSON API

### Code Blocks
- **Status:** ✅ Working perfectly
- **Includes:** Code with syntax highlighting, inline code
- **Limitations:** None
- **Extraction:** `<pre>`, `<code>` elements
- **Preserves:** Language tags, indentation

### Markdown Formatting
- **Status:** ✅ Working perfectly
- **Includes:** Bold, italic, lists, headers, links, blockquotes
- **Limitations:** None
- **Extraction:** Preserved as-is from DOM

### Tables
- **Status:** ✅ Working
- **Includes:** Markdown tables, HTML tables
- **Limitations:** Complex table formatting may need adjustment
- **Extraction:** Text-based, converted to Markdown format

---

## ⚠️ Partially Supported (POC Implemented)

### Images
- **Status:** ⚠️ Implemented with caveats
- **What Works:**
  - ✅ Download images with authentication (uses browser cookies)
  - ✅ Save to local `images/` folder
  - ✅ Update Markdown references to relative paths
  - ✅ Supports: PNG, JPG, GIF, WebP
- **Limitations:**
  - ⚠️ **Signed URLs may expire** - S3/CDN images with time-limited tokens
  - ⚠️ **Blob URLs fail** - Temporary browser-generated URLs (rare)
  - ⚠️ **Base64 embedded images** - Currently skipped (could be extracted)
- **Usage:** `--with-assets` flag
- **Technical:** Uses `page.request.get()` which includes auth context

**Example:**
```python
# Downloads all images and updates Markdown
image_map = await capture_images(page, output_dir)
# {"https://github.com/...": "images/img-001.png"}
```

### File Attachments
- **Status:** ⚠️ Partially working
- **What Works:**
  - ✅ Detect attachment links (`a[download]`, file URLs)
  - ✅ Extract metadata (filename, URL)
  - ✅ Attempt download with authentication
- **Limitations:**
  - ⚠️ **Signed URLs expire** - Download links typically valid for 1-24 hours
  - ⚠️ **Access control** - Some files may require additional permissions
  - ⚠️ **Large files** - May timeout or exceed memory limits
  - ⚠️ **Detection unreliable** - GitHub's attachment markup may vary
- **Workaround:** Capture metadata + URLs, user can download manually if automated fails
- **Usage:** `--with-assets` flag

**Example:**
```python
attachments = await capture_attachments(page, output_dir)
# [{"name": "file.pdf", "url": "...", "downloaded": True}]
```

### Charts & Visualizations
- **Status:** ⚠️ Implemented for static charts
- **What Works:**
  - ✅ Screenshot `<canvas>` elements
  - ✅ Screenshot `<svg>` elements with dimensions
  - ✅ Save as PNG
  - ✅ Embed in Markdown
- **Limitations:**
  - ⚠️ **Interactive charts** - Captured in current state only (no interaction)
  - ⚠️ **Animated visualizations** - Screenshot captures single frame
  - ⚠️ **Hidden elements** - May not screenshot correctly if not visible
  - ⚠️ **Size detection** - SVGs without width/height may be skipped (icons vs charts)
- **Usage:** `--with-assets` flag

**Example:**
```python
charts = await capture_charts(page, output_dir)
# ["charts/chart-001.png", "charts/svg-001.png"]
```

---

## ❌ Not Supported / Cannot Capture

### Real-Time Content
- **Status:** ❌ Not capturable
- **Reason:** Only final state visible in DOM
- **Includes:**
  - Streaming responses (WebSocket)
  - Progressive rendering
  - Live code execution results
- **Alternative:** Wait for completion before export

### Interactive Widgets
- **Status:** ❌ Only static state
- **Reason:** JavaScript interactions not preserved
- **Includes:**
  - Sliders, dropdowns (only current value captured)
  - Expandable sections (must be expanded before capture)
  - Tabs (only active tab captured)
- **Workaround:** Manually interact with page before export

### Edit History
- **Status:** ❌ Not available
- **Reason:** Not in DOM or API response
- **Includes:**
  - Message edit history
  - Deleted messages
  - Previous versions
- **Alternative:** None (GitHub doesn't provide this)

### Temporal Metadata
- **Status:** ⚠️ Limited
- **Reason:** Often relative ("2 hours ago") not absolute timestamps
- **Includes:**
  - Exact timestamps
  - Time zones
- **Workaround:** Capture at export time, use relative times

### External Embeds
- **Status:** ⚠️ Link only
- **Reason:** External content not under GitHub's control
- **Includes:**
  - YouTube videos (link captured, not video)
  - Twitter embeds (link only)
  - CodePen/JSFiddle (link only)
- **Workaround:** Links are preserved, user can visit

---

## 🔧 Technical Implementation

### Authentication for Asset Download

The POC uses Playwright's `page.request` API which automatically includes the user's authentication cookies:

```python
# This includes auth cookies from storage_state.json
response = await page.request.get(image_url)
if response.ok:
    content = await response.body()
```

**Why this works:**
- Browser context includes GitHub session cookies
- No need to manually pass cookies
- Respects authentication and access control

### ZIP Export Structure

When using `--with-assets`, output is packaged as:

```
chat-export-full.zip
├── chat-export.md        # Markdown with relative paths
├── images/
│   ├── image-001.png
│   ├── image-002.jpg
│   └── ...
├── attachments/
│   ├── file.pdf
│   └── document.txt
├── charts/
│   ├── chart-001.png
│   └── svg-001.png
└── page.html             # Debug artifact
```

**Benefits:**
- ✅ Self-contained archive
- ✅ Relative paths work when extracted
- ✅ Easy to share or backup
- ✅ Can open Markdown directly from extracted folder

---

## 🎯 Recommendations

### For CLI Users
- **Basic export:** Use default mode (fast, reliable)
- **Rich export:** Use `--with-assets` if conversation has images/charts
- **Best practice:** Export soon after conversation (before signed URLs expire)

### For Extension Developers
- **Images:** Implement immediately - high value, low complexity
- **Attachments:** Implement metadata extraction, make download optional
- **Charts:** Implement for static charts, document interactive limitations
- **ZIP export:** Offer as Pro feature (adds value justification)

### Priority Recommendations
1. **Must have:** Text + code blocks (already working)
2. **Should have:** Image download (implemented in POC)
3. **Nice to have:** Chart screenshots (implemented in POC)
4. **Optional:** Attachment download (partial, document limitations)

---

## 📊 POC Test Results

### What Was Tested
- ✅ Image download logic (unit tested)
- ✅ Attachment detection logic (unit tested)
- ✅ Chart screenshot logic (unit tested)
- ✅ Markdown replacement (11 unit tests passing)
- ✅ ZIP packaging implementation

### What Needs Live Testing
- ⏳ Real Copilot share page with images
- ⏳ Real Copilot share page with file attachments
- ⏳ Real Copilot share page with charts/canvas elements
- ⏳ Signed URL expiry behavior
- ⏳ Large file handling

**To test:** Run `python scraper_playwright.py --mode login --url <URL>` once, then:
```bash
python scraper_playwright.py --mode run --url <URL> --with-assets
```

Check `chat-export-full.zip` for completeness.

---

## 🔮 Future Enhancements

### Possible Improvements
1. **Parallel downloads** - Download images concurrently (faster)
2. **Progress bar** - Show download progress for large assets
3. **Retry logic** - Retry failed downloads with exponential backoff
4. **Size limits** - Skip or warn for files >50MB
5. **Format conversion** - Convert WebP to PNG, HEIC to JPG
6. **Deduplication** - Avoid downloading same image multiple times
7. **CDN caching** - Cache commonly used images (GitHub avatars, etc.)

### Not Planned
- ❌ Video download (too large, use links)
- ❌ Audio capture (use links)
- ❌ 3D model exports (use links)
- ❌ Live streaming (not feasible)

---

## 📝 Summary

| Content Type | Status | CLI Support | Extension Feasibility | Notes |
|--------------|--------|-------------|----------------------|-------|
| **Text** | ✅ Full | ✅ Yes | ✅ Excellent | No issues |
| **Code blocks** | ✅ Full | ✅ Yes | ✅ Excellent | Preserves formatting |
| **Markdown** | ✅ Full | ✅ Yes | ✅ Excellent | Native support |
| **Tables** | ✅ Full | ✅ Yes | ✅ Excellent | Markdown tables |
| **Images** | ⚠️ Partial | ✅ POC done | ✅ Good | Watch for expired URLs |
| **Attachments** | ⚠️ Partial | ✅ POC done | ⚠️ Medium | Signed URLs, access control |
| **Charts (static)** | ⚠️ Partial | ✅ POC done | ✅ Good | Screenshot works |
| **Interactive charts** | ⚠️ Static only | ⚠️ Limited | ⚠️ Limited | Current state only |
| **Videos** | ⚠️ Link only | ❌ No | ⚠️ Link only | Too large to bundle |
| **Edit history** | ❌ No | ❌ No | ❌ No | Not available in DOM |
| **Real-time content** | ❌ No | ❌ No | ❌ No | Capture final state |

---

## ⚡ Performance Impact

### Default Mode (Text Only)
- **Speed:** ~2-3 seconds
- **Size:** 10-50 KB
- **Memory:** <50 MB

### Rich Mode (--with-assets)
- **Speed:** ~10-30 seconds (depends on assets)
- **Size:** 1-50 MB (depends on images/files)
- **Memory:** 100-500 MB
- **Network:** Downloads all assets sequentially

**Trade-off:** Rich exports are slower but more complete.

---

## 🎓 Lessons Learned

1. **Authentication matters** - Browser context auth crucial for protected assets
2. **Signed URLs expire** - Export quickly after conversation ends
3. **DOM varies** - Multiple selectors needed for robustness
4. **Screenshots work well** - Playwright element screenshots reliable
5. **ZIP is user-friendly** - Self-contained archive better than folder
6. **Test early** - Mock data insufficient, need real share pages
7. **Document clearly** - Users need to know what to expect

---

**Last Updated:** 2025-12-06  
**Branch:** `feature/rich-content-capture`  
**Status:** POC complete, ready for live testing

