---
description: Append one timestamped step line to LOG.md for the current feature (F1/F2 capstone log).
argument-hint: "<what was done> [| metrics, e.g. prompt#3, stuck: …, REPEAT docs: a.ts → CLAUDE.md]"
allowed-tools: Read, Edit, Bash(date *), Bash(git branch --show-current)
---

Append exactly one line to `LOG.md` in the project root. Change nothing else in the file.

1. Get the time with `date "+%H:%M"` and the branch with `git branch --show-current`.
2. Pick the section from the branch: `feature-1/*` → `## F1 …`, `feature-2/*` → `## F2 …`.
   On any other branch, stop and ask which section to use.
3. Insert the line at the end of that section's `### Кроки` list (before the next `###` heading), in the
   format the file header defines:

   `- HH:MM | F1 | <what was done> | <metrics>`

   Take `<what was done>` and `<metrics>` from the arguments: `$ARGUMENTS`.
   If the arguments contain no metrics part, leave the last column empty — do not invent metrics.
4. Show the inserted line. Do not stage or commit.
