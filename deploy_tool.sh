#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/.env"
TOOL_FILE="$SCRIPT_DIR/openwebui_tool_comfyui.py"

echo "Fetching current tool state..."
CURRENT=$(curl -s "$OWUI_BASE_URL/api/v1/tools/id/$OWUI_TOOL_ID" \
  -H "Authorization: Bearer $OWUI_API_KEY")

if [ -z "$CURRENT" ] || echo "$CURRENT" | grep -q '"detail"'; then
  echo "ERROR: Could not fetch tool — check .env values"
  echo "$CURRENT"
  exit 1
fi

echo "Uploading updated tool code..."
UPDATED=$(echo "$CURRENT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
data['content'] = open('$TOOL_FILE').read()
print(json.dumps(data))
")

RESULT=$(curl -s -X POST "$OWUI_BASE_URL/api/v1/tools/id/$OWUI_TOOL_ID/update" \
  -H "Authorization: Bearer $OWUI_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$UPDATED")

if echo "$RESULT" | grep -q '"id"'; then
  echo "✅ Tool deployed: $OWUI_TOOL_ID"
else
  echo "ERROR: Deploy may have failed. Response:"
  echo "$RESULT"
  exit 1
fi
