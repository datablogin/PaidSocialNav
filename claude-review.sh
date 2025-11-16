#!/bin/bash

# PaidSocialNav — Local PR Review Script (Claude Code)
# Adapted for paid social advertising campaigns management (Meta, Reddit, Pinterest, TikTok, X)
# Dependencies: gh (GitHub CLI), claude (Claude Code CLI), jq

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Config
FOCUS_AREAS=""         # comma-separated; supported: security,performance,testing,style,adapters,core,cli,render,storage,docs
MODEL=""               # optional model override if supported by claude CLI
POST_COMMENT=true
OUTPUT_MODE="comment"   # comment|draft-comment|file
DRY_RUN=false
MAX_DIFF_LINES=500

ORIGINAL_BRANCH=$(git branch --show-current || true)

usage() {
  echo "Usage: $0 [OPTIONS] [PR_NUMBER]"
  echo ""
  echo "Options:"
  echo "  --focus AREA        Focus review: security, performance, testing, style, adapters, core, cli, render, storage, docs"
  echo "  --model MODEL       Use specific Claude model (if supported by CLI)"
  echo "  --save-file         Save review to file instead of posting a comment"
  echo "  --draft-comment     Post review as a draft PR comment"
  echo "  --max-diff-lines N  Maximum diff lines to include (default: 500, 0 = no limit)"
  echo "  --dry-run           Show what would be reviewed without calling Claude"
  echo "  --help              Show this help"
  echo ""
  echo "Examples:"
  echo "  $0                           # Review current PR and post as comment"
  echo "  $0 12                        # Review PR #12 and post as comment"
  echo "  $0 --focus adapters,core 12   # Focus adapters and core modules"
}

check_dependencies() {
  local missing=()
  command -v gh >/dev/null 2>&1 || missing+=("GitHub CLI (gh)")
  command -v claude >/dev/null 2>&1 || missing+=("Claude Code CLI (claude)")
  command -v jq >/dev/null 2>&1 || missing+=("jq")
  if [ ${#missing[@]} -ne 0 ]; then
    echo -e "${RED}Missing dependencies:${NC} ${missing[*]}"
    exit 1
  fi
}

check_dependencies

# Parse args
while [[ $# -gt 0 ]]; do
  case $1 in
    --focus) FOCUS_AREAS="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    --save-file) POST_COMMENT=false; OUTPUT_MODE="file"; shift ;;
    --draft-comment) POST_COMMENT=true; OUTPUT_MODE="draft-comment"; shift ;;
    --max-diff-lines) MAX_DIFF_LINES="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --help) usage; exit 0 ;;
    -*) echo -e "${RED}Unknown option: $1${NC}"; usage; exit 1 ;;
    *)
      if [[ $1 =~ ^[0-9]+$ ]]; then PR_NUM=$1; shift; else echo -e "${RED}Invalid PR number: $1${NC}"; usage; exit 1; fi ;;
  esac
done

# Resolve PR number
if [ -z "$PR_NUM" ]; then
  PR_NUM=$(gh pr view --json number -q .number 2>/dev/null || echo "")
  if [ -z "$PR_NUM" ]; then
    echo -e "${RED}Not on a PR branch; specify PR number${NC}"; usage; exit 1
  fi
fi

gh pr view "$PR_NUM" >/dev/null || { echo -e "${RED}PR #$PR_NUM not found${NC}"; exit 1; }

# Heuristics for additional prompts
has_adapters_files() { gh pr diff "$PR_NUM" --name-only | grep -E "paid_social_nav/adapters/" >/dev/null 2>&1; }
has_core_files()     { gh pr diff "$PR_NUM" --name-only | grep -E "paid_social_nav/core/" >/dev/null 2>&1; }
has_cli_files()      { gh pr diff "$PR_NUM" --name-only | grep -E "paid_social_nav/cli/" >/dev/null 2>&1; }
has_render_files()   { gh pr diff "$PR_NUM" --name-only | grep -E "paid_social_nav/render/" >/dev/null 2>&1; }
has_storage_files()  { gh pr diff "$PR_NUM" --name-only | grep -E "paid_social_nav/storage/" >/dev/null 2>&1; }

create_diff_summary() {
  local pr_num="$1"; local max_lines="$2"
  if [ "$max_lines" -eq 0 ]; then gh pr diff "$pr_num"; return; fi
  local full; full=$(gh pr diff "$pr_num")
  local n; n=$(echo "$full" | wc -l | tr -d ' ')
  if [ "$n" -le "$max_lines" ]; then echo "$full"; else
    echo "### ⚠️ Large Diff Summary (${n} lines total, showing first ${max_lines} lines)"
    echo ""
    echo "\`\`\`diff"; echo "$full" | head -n "$max_lines"; echo "\`\`\`"
    local owner; owner=$(gh repo view --json owner -q '.owner.login')
    local name;  name=$(gh repo view --json name -q '.name')
    echo "Full diff: https://github.com/${owner}/${name}/pull/${pr_num}/files"
  fi
}

generate_review_prompt() {
  local base="Please review this pull request for:\n- Code quality and correctness\n- Potential bugs\n- Performance considerations\n- Security concerns\n- Test coverage and determinism\n\nBe constructive and specific."
  local domain=""
  if has_adapters_files || [[ "$FOCUS_AREAS" == *"adapters"* ]]; then
    domain+="\n\nFor the platform adapters:\n- API integration correctness (Meta, Reddit, Pinterest, TikTok, X)\n- Authentication and token handling\n- Rate limiting and error handling\n- Data transformation and validation\n- Platform-specific campaign management"
  fi
  if has_core_files || [[ "$FOCUS_AREAS" == *"core"* ]]; then
    domain+="\n\nFor the core modules:\n- Campaign synchronization logic\n- Enum definitions and type safety\n- Configuration management\n- Cross-platform data models\n- Error handling and logging"
  fi
  if has_cli_files || [[ "$FOCUS_AREAS" == *"cli"* ]]; then
    domain+="\n\nFor the CLI interface:\n- Command structure and argument parsing\n- User experience and error messages\n- Configuration file handling\n- Output formatting and verbosity levels\n- Help documentation clarity"
  fi
  if has_render_files || [[ "$FOCUS_AREAS" == *"render"* ]]; then
    domain+="\n\nFor the rendering module:\n- Template processing and data binding\n- Output format generation\n- Performance optimization\n- Error handling in template rendering"
  fi
  if has_storage_files || [[ "$FOCUS_AREAS" == *"storage"* ]]; then
    domain+="\n\nFor the storage module:\n- Data persistence strategies\n- Database integration and queries\n- Transaction handling\n- Data integrity and validation\n- Performance and indexing"
  fi
  case "$FOCUS_AREAS" in
    *security*) domain+="\n\nFocus security: input validation, schema validation, SSRF/download risks, secrets handling.";;
  esac
  case "$FOCUS_AREAS" in
    *performance*) domain+="\n\nFocus performance: API call efficiency, bulk operations, caching strategies, response times.";;
  esac
  case "$FOCUS_AREAS" in
    *testing*) domain+="\n\nFocus testing: unit coverage for adapters/core, integration tests, mock API responses, fixtures quality.";;
  esac
  case "$FOCUS_AREAS" in
    *style*) domain+="\n\nFocus style: readability, naming, modularity, docs.";;
  esac
  case "$FOCUS_AREAS" in
    *docs*) domain+="\n\nFocus docs: README clarity, platform integration examples, CLI usage documentation.";;
  esac
  echo -e "$base$domain"
}

# PR info
PR_INFO=$(gh pr view "$PR_NUM" --json title,author,baseRefName,headRefName,additions,deletions,changedFiles,commits)
PR_TITLE=$(echo "$PR_INFO" | jq -r .title)
PR_AUTHOR=$(echo "$PR_INFO" | jq -r .author.login)
PR_BRANCH=$(echo "$PR_INFO" | jq -r .headRefName)
PR_BASE_BRANCH=$(echo "$PR_INFO" | jq -r .baseRefName)
PR_ADDITIONS=$(echo "$PR_INFO" | jq -r .additions)
PR_DELETIONS=$(echo "$PR_INFO" | jq -r .deletions)
PR_CHANGED_FILES=$(echo "$PR_INFO" | jq -r .changedFiles)
PR_COMMITS=$(echo "$PR_INFO" | jq -r '.commits | length')

echo -e "${GREEN}Reviewing PR #$PR_NUM: $PR_TITLE${NC}"
echo -e "Author: $PR_AUTHOR"
echo -e "Branch: $PR_BRANCH → $PR_BASE_BRANCH"
echo -e "Changes: ${GREEN}+$PR_ADDITIONS${NC} ${RED}-$PR_DELETIONS${NC} lines across $PR_CHANGED_FILES files"
echo -e "Commits: $PR_COMMITS"
if [ -n "$FOCUS_AREAS" ]; then echo -e "Focus: ${BLUE}$FOCUS_AREAS${NC}"; fi

echo ""

# Ensure on PR branch
CURRENT_BRANCH=$(git branch --show-current || true)
if [ "$CURRENT_BRANCH" != "$PR_BRANCH" ]; then
  echo -e "${YELLOW}Checking out PR branch...${NC}"
  gh pr checkout "$PR_NUM"
fi

REVIEW_PROMPT=$(generate_review_prompt)

echo -e "${BLUE}Preparing PR context (max diff lines: $MAX_DIFF_LINES)...${NC}"
PR_CONTEXT=$(cat <<EOF
### PR Context
- **Title:** $PR_TITLE
- **Author:** $PR_AUTHOR
- **Branch:** $PR_BRANCH → $PR_BASE_BRANCH
- **Additions:** $PR_ADDITIONS
- **Deletions:** $PR_DELETIONS
- **Files Changed:** $PR_CHANGED_FILES
- **Commits:** $PR_COMMITS

### Files in this PR:
\`\`\`
$(gh pr diff "$PR_NUM" --name-only)
\`\`\`

### Code Changes:
$(create_diff_summary "$PR_NUM" "$MAX_DIFF_LINES")
EOF
)

if [ "$DRY_RUN" = true ]; then
  echo -e "${BLUE}DRY RUN — Files to review:${NC}"
  gh pr diff "$PR_NUM" --name-only | sed 's/^/  - /'
  echo ""; echo "Generated prompt:"; echo "$REVIEW_PROMPT" | sed 's/^/  /'
  exit 0
fi

case "$OUTPUT_MODE" in
  comment|draft-comment)
    echo -e "${YELLOW}Running Claude review and posting to PR...${NC}"
    TMP=$(mktemp)
    echo "$PR_CONTEXT" > "$TMP"
    echo -e "\n---\n\n$REVIEW_PROMPT" >> "$TMP"
    OUT="${TMP}.out"
    # If MODEL is set and supported by CLI, you can add e.g.: claude chat --model "$MODEL"
    if claude chat < "$TMP" > "$OUT" 2>&1; then
      COMMENT=$(mktemp)
      cat > "$COMMENT" <<EOC
# 🔍 Claude Code Review

## Review Feedback

$(cat "$OUT")

---
*Generated by PaidSocialNav PR Review Tool*
EOC
      if [ "$OUTPUT_MODE" = "draft-comment" ]; then
        gh pr comment "$PR_NUM" --body-file "$COMMENT" --draft >/dev/null || true
      else
        gh pr comment "$PR_NUM" --body-file "$COMMENT" >/dev/null || true
      fi
      echo -e "${GREEN}✓ Review comment posted${NC}"
      rm -f "$COMMENT"
    else
      echo -e "${RED}✗ Claude review failed${NC}"; [ -f "$OUT" ] && head -n 40 "$OUT" || true
    fi
    rm -f "$TMP" "$OUT"
    ;;
  file)
    DATE=$(date +%Y%m%d_%H%M)
    OUTDIR="reviews/paid_social_nav"
    mkdir -p "$OUTDIR"
    SUF=""; [ -n "$FOCUS_AREAS" ] && SUF="-$(echo "$FOCUS_AREAS" | tr ',' '-')"
    OUTFILE="$OUTDIR/pr-${PR_NUM}${SUF}-${DATE}.md"
    echo -e "${YELLOW}Running Claude review and saving to $OUTFILE...${NC}"
    {
      echo "# 🔍 Claude Code Review: PR #$PR_NUM"; echo "";
      echo "**Title:** $PR_TITLE  "; echo "**Author:** $PR_AUTHOR  ";
      echo "**Date:** $(date +"%Y-%m-%d %H:%M:%S")  ";
      echo "**Branch:** $PR_BRANCH → $PR_BASE_BRANCH"; echo "";
      echo "$PR_CONTEXT"; echo "\n---\n\n## Review Prompt Used\n\n$REVIEW_PROMPT\n\n---\n\n## Claude Review Output\n";
    } > "$OUTFILE"
    TMP=$(mktemp)
    echo "$PR_CONTEXT" > "$TMP"; echo -e "\n---\n\n$REVIEW_PROMPT" >> "$TMP"
    if claude chat < "$TMP" >> "$OUTFILE" 2>&1; then
      echo -e "${GREEN}✓ Review saved: $OUTFILE${NC}"
    else
      echo -e "${RED}✗ Review failed${NC}"; echo "See $OUTFILE for details";
    fi
    rm -f "$TMP"
    ;;
esac

# Return to original branch
if [ -n "$ORIGINAL_BRANCH" ] && [ "$ORIGINAL_BRANCH" != "$PR_BRANCH" ]; then
  echo -e "${YELLOW}Returning to branch: $ORIGINAL_BRANCH${NC}"
  git checkout "$ORIGINAL_BRANCH"
fi

echo -e "${BLUE}PaidSocialNav PR Review Script ready.${NC}"
