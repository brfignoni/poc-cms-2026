// Commit message rules enforced by Husky on every commit.
// These rules are mirrored in .cursorrules for Cursor AI-generated commit suggestions.
// If you update or delete this file, update .cursorrules to match.
export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "docs",
        "chore",
        "refactor",
        "test",
        "perf",
        "ci",
        "build",
        "revert",
        "style",
        "hotfix",
      ],
    ],
    "scope-empty": [2, "never"],
    "subject-case": [2, "never", ["start-case", "pascal-case", "upper-case"]],
    "subject-empty": [2, "never"],
    "subject-full-stop": [2, "never", "."],
    "header-max-length": [2, "always", 100],
    "body-max-line-length": [1, "always", 120],
  },
};
