---
description: Debug common Nuxt.js issues and configuration problems
agent: nuxt-expert
---

Analyze the current Nuxt.js error or issue:
!`pnpm dev 2>&1 | head -50`

Identify the issue and provide a fix. Check for:
- PostCSS/TailwindCSS configuration issues
- Module loading problems
- TypeScript errors
- Build configuration issues
- Component import problems
- Routing issues
- Asset loading failures

If the dev server is already running, check:
!`ps aux | grep "nuxt dev" | grep -v grep`

And provide the next steps to resolve the issue.
