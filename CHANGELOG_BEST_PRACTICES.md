# AccelByte How-To Tool Implementation - Change Log

## Overview

Added a new `get_accelbyte_how_to` tool to the MCP server that provides implementation guidance and how-to instructions for common AccelByte tasks.

## Changes Made

### 1. Created Best Practices Knowledge Base
**File:** `data/best-practices.json`

- Created structured JSON database of best practices guides
- Includes 5 comprehensive guides covering common AccelByte implementation scenarios
- Each guide includes:
  - Multiple implementation methods/approaches
  - Code templates with proper Unreal C++ syntax
  - Step-by-step instructions
  - Best practices and common pitfalls
  - Links to related snippets and components

**Guides included:**
1. **get-apiclient**: How to Get AccelByte API Client Instance
   - Via AccelByte OSS (Recommended)
   - Via AccelByte OSS with Custom ID
   - Create Manual AccelByte Instance
   - For Game Server

2. **add-api-call**: How to Add New API Calls to Unreal SDK
   - File structure and naming conventions
   - Creating models, API headers, and implementations
   - Blueprint wrapping (optional)

3. **authentication**: How to Authenticate Users with AccelByte
   - Device ID Login (Guest Account)
   - Email and Password Login

4. **matchmaking**: How to Implement Matchmaking with AccelByte
   - Party session creation
   - Match pool configuration
   - Session joining

5. **achievements**: How to Query and Display Player Achievements
   - Querying definitions and progress
   - Image downloading

### 2. Added Tool Definition
**File:** `server.py`

- Added `get_accelbyte_how_to` to the tools list in `list_tools` handler
- Input schema with three parameters:
  - `topic` (required): Search query for finding relevant guides
  - `include_code_examples` (optional, default true): Include related snippets
  - `include_components` (optional, default true): Include related example components

### 3. Implemented Tool Handler
**File:** `server.py`

- Added `get_accelbyte_how_to` case to `call_tool` handler
- Implements fuzzy matching algorithm to find relevant guides:
  - Keyword matching (+10 points each)
  - Title matching (+20 points)
  - ID matching (+15 points)
- Dynamically enhances guides with:
  - Related code snippets from snippet index (by area, tags, or query)
  - Related example components (by component name)
- Returns structured JSON with guide content and related materials

### 4. Created Documentation
**File:** `BEST_PRACTICES.md` (new)

- Comprehensive documentation for the new tool
- Usage examples for each guide topic
- Parameter descriptions
- Response structure documentation
- Instructions for adding new topics

### 5. Updated README
**File:** `README.md`

- Added `get_accelbyte_how_to` tool to the Tools section
- Added usage example (Example 6)
- Updated project structure to include `best-practices.json`, `BEST_PRACTICES.md`, and `sdk_installer.py`
- Updated tool description to include the new tool in SDK requirement note

## Technical Details

### Fuzzy Matching Algorithm
The tool uses a scoring system to find the most relevant guide:
- Searches through keywords, title, and ID fields
- Calculates relevance scores based on matches
- Returns the highest-scoring guide
- If no match found, returns list of available topics

### Dynamic Content Enhancement
When `include_code_examples` is true:
- Searches snippet index by area (if `related_snippets.areas` defined)
- Searches by tags (if `related_snippets.tags` defined)
- Searches by query string (if `related_snippets.query` defined)
- Limits to 10 snippets maximum

When `include_components` is true:
- Searches component index by component name
- Matches against controller class, UI widget class, or component ID
- Returns component metadata and file URIs

### Data Structure
Best practices JSON schema:
```json
{
  "guides": [
    {
      "id": "unique-id",
      "title": "Guide title",
      "keywords": ["keyword1", "keyword2"],
      "source_url": "https://docs.accelbyte.io/...",
      "overview": "Description",
      "methods": [
        {
          "name": "Method name",
          "when_to_use": "When to use",
          "prerequisites": ["prereq1"],
          "code_template": "Code example",
          "steps": ["step1", "step2"]
        }
      ],
      "steps": ["overall steps"],
      "best_practices": ["practice1"],
      "common_pitfalls": ["pitfall1"],
      "related_snippets": {
        "areas": ["area1"],
        "tags": ["tag1"],
        "query": "search string"
      },
      "related_components": ["ComponentName"]
    }
  ]
}
```

## Testing

Manual verification:
- ✅ Tool definition added to tools list
- ✅ Handler implemented with proper error handling
- ✅ Best practices JSON created with valid structure
- ✅ Documentation created

## Usage Example

```json
{
  "tool": "get_accelbyte_how_to",
  "arguments": {
    "topic": "get api client",
    "include_code_examples": true,
    "include_components": true
  }
}
```

Returns:
```json
{
  "guide": {
    "id": "get-apiclient",
    "title": "How to Get AccelByte API Client Instance",
    "overview": "...",
    "methods": [],
    "best_practices": [],
    "related_content": {
      "snippets": [],
      "components": []
    }
  },
  "sdkRequirement": "..."
}
```

## Future Enhancements

Potential improvements:
1. Add more guides (party management, friends, chat, statistics, etc.)
2. Implement versioning for guides (SDK version-specific guidance)
3. Add code validation/testing for templates
4. Support for Blueprint-specific guides
5. Integration with AccelByte docs API for live content updates
6. Multi-language support (C++, Blueprint Visual Scripting, etc.)

## Related Documentation

- [BEST_PRACTICES.md](BEST_PRACTICES.md) - Detailed tool documentation
- [README.md](README.md) - Main project documentation
- AccelByte Documentation:
  - [Managing AccelByte Instance](https://docs.accelbyte.io/gaming-services/knowledge-base/sdk-tools/sdk-guides/accelbyte-singleton-in-sdk/manage-ags-ue-sdk-accelbyte-instance/)
  - [Adding API Calls](https://docs.accelbyte.io/gaming-services/knowledge-base/sdk-tools/sdk-guides/adding-api-calls/)
