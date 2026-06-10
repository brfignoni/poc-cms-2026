#!/usr/bin/env bash
# Validate that the current branch name follows the project's naming convention.
# Convention: <type>/<short-desc>   e.g. feat/add-hero-section
#
# Exit codes:
#   0 - valid (or branch is a protected/main/release branch)
#   1 - invalid branch name
set -euo pipefail

# During rebase/cherry-pick, `git rev-parse --abbrev-ref HEAD` is "HEAD" (detached).
# Resolve the real branch from git's rebase metadata so hooks don't false-fail.
resolve_branch_name() {
  local branch git_dir ref
  branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  if [[ -n "$branch" && "$branch" != "HEAD" ]]; then
    printf '%s' "$branch"
    return
  fi
  git_dir="$(git rev-parse --git-dir 2>/dev/null || true)"
  if [[ -z "$git_dir" ]]; then
    printf '%s' "${branch:-}"
    return
  fi
  for ref_file in rebase-merge/head-name rebase-apply/head-name; do
    if [[ -f "${git_dir}/${ref_file}" ]]; then
      ref="$(< "${git_dir}/${ref_file}")"
      printf '%s' "${ref#refs/heads/}"
      return
    fi
  done
  printf '%s' "${branch:-}"
}

# Accept branch name via $1 (CI) or read from git (local)
BRANCH="${1:-$(resolve_branch_name)}"

if [[ -z "$BRANCH" ]]; then
  echo "❌ Could not determine branch name"
  exit 1
fi

# Exempt branches — managed by release/infra flows
EXEMPT_REGEX='^(main|develop|release/.+|dependabot/.+|renovate/.+|revert-.+)$'
if [[ "$BRANCH" =~ $EXEMPT_REGEX ]]; then
  exit 0
fi

# Convention: <type>/<3-50 chars: lowercase, digits, dashes>
VALID_REGEX='^(feat|fix|docs|chore|refactor|test|perf|ci|build|revert|hotfix)/[a-z0-9][a-z0-9-]{2,49}$'

if [[ "$BRANCH" =~ $VALID_REGEX ]]; then
  exit 0
fi

cat <<EOF >&2
❌ Branch name '$BRANCH' does not match the required convention.

Required format:  <type>/<short-desc>
  - <type>:  feat | fix | docs | chore | refactor | test | perf | ci | build | revert | hotfix
  - <short-desc>:  3-50 chars, lowercase letters / digits / dashes, starts with letter or digit

Examples:
  ✓ feat/add-hero-section
  ✓ fix/cms-slug-query
  ✓ chore/upgrade-astro
  ✗ my-feature         (missing type/)
  ✗ feat/MyFeature     (not lowercase)
  ✗ feature/foo        (use 'feat', not 'feature')

To rename the current branch:
  git branch -m <type>/<short-desc>
EOF

exit 1
