---
description: Set up and verify the development environment
agent: general
---

Check and verify the development environment setup:

## Frontend Environment

**Node.js and pnpm:**
!`node --version && pnpm --version`

**Frontend dependencies:**
!`pnpm list --depth=0 2>&1 | head -20`

**Nuxt status:**
!`ls -la nuxt.config.ts package.json`

## Backend Environment

**Python and uv:**
!`python --version 2>&1; uv --version 2>&1`

**Backend status:**
!`ls -la backend/`

## Git Status

**Repository status:**
!`git status --short`

## Analysis

Based on the above checks, provide:

1. **What's working:** List properly configured tools and dependencies
2. **What needs setup:** Identify missing tools or configuration
3. **Installation commands:** Provide specific commands to fix any issues
4. **Next steps:** Suggest what to do next based on the current state

## Common Setup Issues

If issues are found, check for:
- **Missing tools:** Provide installation instructions
- **Version mismatches:** Suggest upgrades
- **Permission issues:** Recommend fixes
- **Path problems:** Help configure environment variables
- **Dependency conflicts:** Suggest resolution strategies

Provide a clear, actionable setup plan.
