# AccelByte How-To Tool

The `get_accelbyte_how_to` tool provides implementation guidance and how-to instructions for common AccelByte tasks.

## Usage

```javascript
// Get guidance on obtaining an AccelByte API client
get_accelbyte_how_to({
  topic: "get api client",
  include_code_examples: true,
  include_components: true
})

// Get guidance on adding new API calls
get_accelbyte_how_to({
  topic: "add api call"
})

// Get guidance on authentication
get_accelbyte_how_to({
  topic: "authentication"
})

// Get guidance on matchmaking
get_accelbyte_how_to({
  topic: "matchmaking"
})
```

## Parameters

- **topic** (required): The topic or question you need guidance on. Supports partial matches and keywords.
  - Examples: `"get api client"`, `"add api call"`, `"authentication"`, `"matchmaking"`, `"achievements"`
  
- **include_code_examples** (optional, default: `true`): Whether to include related code snippets from the snippet index
  
- **include_components** (optional, default: `true`): Whether to include related example components

## Available Topics

The tool currently provides guides for:

1. **get-apiclient** - How to Get AccelByte API Client Instance
   - Keywords: `apiclient`, `instance`, `initialize`, `setup`, `access sdk`, `get api`, `obtain client`, `fapilientptr`
   
2. **add-api-call** - How to Add New API Calls to Unreal SDK
   - Keywords: `add api`, `extend sdk`, `new endpoint`, `custom api`, `add function`, `new service`
   
3. **authentication** - How to Authenticate Users with AccelByte
   - Keywords: `login`, `authenticate`, `sign in`, `credentials`, `device id`, `email password`
   
4. **matchmaking** - How to Implement Matchmaking with AccelByte
   - Keywords: `matchmaking`, `find match`, `quick play`, `session`, `multiplayer`, `p2p`
   
5. **achievements** - How to Query and Display Player Achievements
   - Keywords: `achievements`, `unlock`, `progress`, `query achievements`

## Response Structure

The tool returns a structured guide with:

```json
{
  "guide": {
    "id": "get-apiclient",
    "title": "How to Get AccelByte API Client Instance",
    "source_url": "https://docs.accelbyte.io/...",
    "overview": "Description of the topic",
    "methods": [
      {
        "name": "Method name",
        "when_to_use": "When to use this approach",
        "prerequisites": ["List of prerequisites"],
        "code_template": "Code example",
        "steps": ["Step-by-step instructions"]
      }
    ],
    "steps": ["Overall implementation steps"],
    "best_practices": ["Best practice recommendations"],
    "common_pitfalls": ["Things to avoid"],
    "related_content": {
      "snippets": [
        {
          "id": "snippet-id",
          "uri": "snippet://...",
          "name": "Snippet name",
          "area": "auth",
          "function": "Login"
        }
      ],
      "components": [
        {
          "id": "component-id",
          "service": "auth",
          "description": "Component description",
          "fileResourceUris": ["example-file://..."]
        }
      ]
    }
  },
  "sdkRequirement": "SDK installation note"
}
```

## Examples

### Example 1: Getting API Client Instance

```json
{
  "topic": "get api client",
  "include_code_examples": true,
  "include_components": true
}
```

Returns guidance on:
- Via AccelByte OSS (Recommended)
- Via AccelByte OSS with Custom ID
- Create Manual AccelByte Instance
- For Game Server

Plus related snippets from auth/login areas and the AccelByteLoginPanel component.

### Example 2: Adding New API Calls

```json
{
  "topic": "add api call",
  "include_code_examples": true
}
```

Returns step-by-step guide with:
- File naming conventions
- Directory structure
- Code templates for models, API headers, and implementations
- Blueprint wrapping (optional)
- Best practices and common pitfalls

### Example 3: Authentication

```json
{
  "topic": "login"
}
```

Returns guidance on:
- Device ID Login (Guest Account)
- Email and Password Login
- Related snippets and components

## Data Source

Best practices content is stored in `data/best-practices.json` and is enhanced with:
- Live code snippets from the tutorial modules
- Related example components
- Links to AccelByte documentation

## Adding New Topics

To add new best practice guides, edit `data/best-practices.json`:

```json
{
  "guides": [
    {
      "id": "your-topic-id",
      "title": "How to Do Something with AccelByte",
      "keywords": ["keyword1", "keyword2", "..."],
      "source_url": "https://docs.accelbyte.io/...",
      "overview": "Brief overview",
      "methods": [...],
      "steps": [...],
      "best_practices": [...],
      "common_pitfalls": [...],
      "related_snippets": {
        "areas": ["area1", "area2"],
        "tags": ["tag1", "tag2"],
        "query": "search query"
      },
      "related_components": ["ComponentName"]
    }
  ]
}
```

The tool will automatically match topics using fuzzy matching on:
- Keywords (score: +10 per match)
- Title (score: +20 if matches)
- ID (score: +15 if matches)
