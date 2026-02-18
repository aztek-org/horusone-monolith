# OpenCode Expert Agents for Horus Aviation Platform

This directory contains specialized OpenCode agents and custom commands for the Horus Aviation Training Platform. These agents provide expert assistance for frontend (Nuxt.js/TailwindCSS), Python development, and backend API development with FastAPI and LangChain.

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Expert Agents](#expert-agents)
- [Custom Commands](#custom-commands)
- [Package Managers](#package-managers)
- [Common Workflows](#common-workflows)
- [Replication Guide](#replication-guide)
- [Troubleshooting](#troubleshooting)
- [Customization](#customization)

---

## 🎯 Overview

The Horus platform includes three specialized AI agents that understand our tech stack and coding conventions:

### **Frontend Expert** (`@nuxt-expert`)
Specializes in Nuxt.js 4.x, Vue 3 Composition API, and TailwindCSS with deep knowledge of our Horus design system (custom colors, components, aviation UI patterns).

### **Python Expert** (`@python-expert`)
Focuses on clean Python code, modern best practices (Python 3.10+), type safety, testing with pytest, and PEP compliance.

### **API Expert** (`@api-expert`)
Expert in FastAPI backend development with LangChain integration for AI-powered features, including chains, agents, tools, and async patterns.

---

## 📦 Prerequisites

### Required Tools

1. **OpenCode** - AI coding agent
   ```bash
   curl -fsSL https://opencode.ai/install | bash
   ```

2. **Node.js** (v18+) and **pnpm** - Frontend development
   ```bash
   # Install pnpm globally
   curl -fsSL https://get.pnpm.io/install.sh | sh -
   ```

3. **Python** (v3.10+) and **uv** - Backend development
   ```bash
   # Install uv package manager
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### API Keys

You'll need API keys for your preferred LLM provider:
- **Recommended**: OpenCode Zen (curated models)
- **Alternatives**: OpenAI, Anthropic, Google, etc.

Configure via OpenCode:
```bash
opencode
/connect
```

---

## 🚀 Quick Start

### 1. Clone and Navigate

```bash
git clone <repository-url>
cd horus-mvp
```

### 2. Initialize OpenCode

```bash
opencode
/init
```

This analyzes your project and loads the agent configurations.

### 3. Install Dependencies

**Frontend:**
```bash
pnpm install
```

**Backend (when ready):**
```bash
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

### 4. Start Using Agents!

```bash
# In OpenCode TUI
@nuxt-expert Help me create a flight status component
@python-expert Review my code for best practices
@api-expert Create a FastAPI endpoint for scenarios
```

---

## 🤖 Expert Agents

### Frontend Expert: `@nuxt-expert`

**Specializations:**
- Nuxt 4.x architecture and best practices
- Vue 3 Composition API with TypeScript
- TailwindCSS utility-first design
- Horus design system (colors, components, animations)
- Component development and state management
- Performance optimization and accessibility

**Knowledge of Your Project:**
- Custom Tailwind colors: `horus-accent-cyan`, `horus-bg-*`, `horus-text-*`
- Component library: `HButton`, `HCard`, `HBadge`, `MapVisualization`, etc.
- Project structure: `app/components/`, `app/pages/`, `app/layouts/`
- Aviation-specific UI patterns

**Example Usage:**
```bash
@nuxt-expert Create a new component for displaying real-time flight metrics with:
- Animated status indicators using horus-accent-cyan
- Card-elevated styling
- Proper TypeScript types
- Responsive design
```

### Python Expert: `@python-expert`

**Specializations:**
- Modern Python 3.10+ features
- Type hints and mypy strict mode
- PEP 8, PEP 257, PEP 484 compliance
- Testing with pytest (fixtures, parametrize, async)
- Clean architecture patterns
- Async/await best practices

**Code Quality Focus:**
- Comprehensive type annotations
- Docstrings for all public APIs
- Proper error handling
- Security considerations
- Performance optimization
- Test coverage

**Example Usage:**
```bash
@python-expert Review this service layer code for:
- Type safety
- Async patterns
- Error handling
- Test coverage
```

### API Expert: `@api-expert`

**Specializations:**
- FastAPI async patterns and dependency injection
- LangChain chains, agents, and tools
- Pydantic models for validation
- RESTful API design
- OpenAPI/Swagger documentation
- CORS configuration for Nuxt integration
- Real-time features with WebSockets

**LangChain Expertise:**
- Custom chain design
- Agent creation with tools
- Prompt engineering
- Memory management
- Vector stores and embeddings
- Output parsing and structured responses

**Example Usage:**
```bash
@api-expert Create a POST /api/scenarios/generate endpoint that:
- Accepts scenario parameters (aircraft, difficulty, duration)
- Uses LangChain to generate realistic training scenarios
- Returns structured JSON with waypoints
- Handles errors gracefully
```

---

## ⚡ Custom Commands

Quick-access commands for common workflows:

### `/fix-nuxt`
Debug Nuxt.js issues automatically.

```bash
/fix-nuxt
```

**What it does:**
- Runs `pnpm dev` and captures errors
- Analyzes PostCSS, TailwindCSS, TypeScript issues
- Checks for module loading problems
- Provides specific fixes

### `/review-python`
Comprehensive Python code review.

```bash
/review-python backend/app/services/scenario_service.py
```

**What it checks:**
- PEP 8 compliance and style
- Type hints completeness
- Potential bugs and edge cases
- Performance issues
- Security vulnerabilities
- Test coverage
- Modern Python features usage

### `/test-api`
Run and analyze API tests.

```bash
/test-api
```

**What it does:**
- Runs pytest with coverage
- Analyzes test failures
- Checks for async issues
- Suggests fixes for integration problems

### `/setup-dev`
Verify development environment.

```bash
/setup-dev
```

**What it checks:**
- Node.js and pnpm versions
- Python and uv installation
- Dependency status
- Git repository status
- Provides setup instructions for missing tools

---

## 📦 Package Managers

### Frontend: pnpm

**Why pnpm?**
- Fast, efficient, disk-space saving
- Strict dependency resolution
- Monorepo support

**Common Commands:**
```bash
pnpm install              # Install dependencies
pnpm add <package>        # Add dependency
pnpm add -D <package>     # Add dev dependency
pnpm remove <package>     # Remove dependency
pnpm dev                  # Start dev server
pnpm build                # Build for production
pnpm preview              # Preview production build
pnpm run <script>         # Run package.json script
```

### Backend: uv

**Why uv?**
- Extremely fast Python package installer
- Drop-in replacement for pip
- Better dependency resolution
- Virtual environment management

**Common Commands:**
```bash
uv venv                            # Create virtual environment
uv pip install -r requirements.txt # Install dependencies
uv pip install <package>           # Install package
uv pip freeze > requirements.txt   # Save dependencies
uv run <command>                   # Run command in venv
uv run uvicorn app.main:app --reload  # Start FastAPI
uv run pytest                      # Run tests
```

---

## 🔄 Common Workflows

### Creating a New Nuxt Component

```bash
# 1. Ask the Nuxt expert
@nuxt-expert I need to create a FlightPathVisualization component that:
- Shows a 3D flight path on a map
- Uses the horus-accent-cyan for the path line
- Accepts props for waypoints array
- Has smooth animations
- Responsive design

# 2. Review the generated code
# The agent will create the component with proper TypeScript, styling, and structure

# 3. Test it
pnpm dev
```

### Building a FastAPI Endpoint with LangChain

```bash
# 1. Ask the API expert
@api-expert Create a POST /api/training/evaluate endpoint that:
- Accepts student performance data
- Uses LangChain to generate feedback
- Returns evaluation with scores and recommendations
- Integrates with our scenario system

# 2. Review the implementation
# The agent will create endpoint, service layer, and LangChain chain

# 3. Test it
/test-api
```

### Code Review Workflow

```bash
# Python code review
/review-python backend/app/services/mission_planner.py

# Or ask directly
@python-expert Review this code and check for async issues, type safety, and test coverage

# For frontend code
@nuxt-expert Review this component for accessibility and performance issues
```

### Debugging Issues

```bash
# Nuxt issues
/fix-nuxt

# API issues
/test-api

# Environment issues
/setup-dev
```

---

## 🔁 Replication Guide

### For New Team Members

Follow these steps to set up the same development environment on a new machine:

#### Step 1: Install Prerequisites

```bash
# Install OpenCode
curl -fsSL https://opencode.ai/install | bash

# Install pnpm
curl -fsSL https://get.pnpm.io/install.sh | sh -

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Step 2: Clone Repository

```bash
git clone <repository-url>
cd horus-mvp
```

#### Step 3: Configure OpenCode

```bash
opencode
/connect
# Select your LLM provider and enter API key
```

#### Step 4: Initialize Project

```bash
# Still in OpenCode TUI
/init
# This loads the agent configurations automatically
```

#### Step 5: Install Dependencies

```bash
# Frontend
pnpm install

# Backend (when structure is created)
cd backend
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

#### Step 6: Verify Setup

```bash
# In OpenCode TUI
/setup-dev
# This checks everything is configured correctly
```

#### Step 7: Start Developing!

All expert agents and custom commands are now available:
- `@nuxt-expert`, `@python-expert`, `@api-expert`
- `/fix-nuxt`, `/review-python`, `/test-api`, `/setup-dev`

---

## 🐛 Troubleshooting

### OpenCode Issues

**Agent not responding:**
```bash
# Check connection
/connect

# Verify API keys are configured
# Check ~/.config/opencode/config.json
```

**Agents not found:**
```bash
# Reinitialize the project
/init

# Check agents exist
ls -la .opencode/agents/
```

### Frontend Issues

**pnpm commands not working:**
```bash
# Check pnpm is installed
pnpm --version

# If not installed
curl -fsSL https://get.pnpm.io/install.sh | sh -

# Add to PATH (usually automatic)
export PATH="$HOME/.local/share/pnpm:$PATH"
```

**Nuxt build errors:**
```bash
# Use the fix-nuxt command
/fix-nuxt

# Or clean and reinstall
rm -rf .nuxt node_modules
pnpm install
```

### Backend Issues

**uv commands not working:**
```bash
# Check uv is installed
uv --version

# If not installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Add to PATH
export PATH="$HOME/.cargo/bin:$PATH"
```

**Python virtual environment issues:**
```bash
# Recreate venv
rm -rf .venv
uv venv
source .venv/bin/activate

# Reinstall dependencies
uv pip install -r requirements.txt
```

### Common Errors

**"Module not found" errors:**
- Frontend: Run `pnpm install`
- Backend: Run `uv pip install -r requirements.txt`

**Port already in use:**
- Frontend: Nuxt will auto-select alternate port (3001, 3002, etc.)
- Backend: Kill existing process or use different port

**Permission denied:**
- Check file permissions: `ls -la`
- May need to use `chmod` for execute permissions

---

## 🎨 Customization

### Modifying Agents

Agent configuration files are in `.opencode/agents/`:
- `nuxt-expert.md`
- `python-expert.md`
- `api-expert.md`

**To customize an agent:**

1. Edit the frontmatter (YAML section):
   ```yaml
   ---
   description: Your custom description
   temperature: 0.3  # Adjust creativity (0.0-1.0)
   model: anthropic/claude-sonnet-4-20250514  # Change model
   ---
   ```

2. Modify the system prompt (markdown content)

3. Save and reinitialize:
   ```bash
   # In OpenCode
   /init
   ```

### Creating New Commands

Create a new `.md` file in `.opencode/commands/`:

```markdown
---
description: Your command description
agent: nuxt-expert
---

Your prompt template here.
Use $ARGUMENTS for command arguments.
Use !`bash command` for shell output injection.
Use @filename for file references.
```

Example - Create `/check-types`:
```bash
# File: .opencode/commands/check-types.md
---
description: Check TypeScript types in frontend
agent: nuxt-expert
---

Run TypeScript type checking:
!`pnpm run type-check`

Analyze any type errors and provide fixes.
```

### Adding New Agents

1. Create a new file in `.opencode/agents/`:
   ```bash
   touch .opencode/agents/my-expert.md
   ```

2. Add configuration:
   ```markdown
   ---
   description: Expert in XYZ technology
   mode: subagent
   temperature: 0.2
   ---
   
   You are an expert in...
   ```

3. Reinitialize:
   ```bash
   /init
   ```

4. Use it:
   ```bash
   @my-expert help me with XYZ
   ```

---

## 📂 File Structure

```
.opencode/
├── agents/
│   ├── nuxt-expert.md       # Nuxt.js/Vue/TailwindCSS expert
│   ├── python-expert.md     # Python best practices expert
│   └── api-expert.md        # FastAPI/LangChain expert
├── commands/
│   ├── fix-nuxt.md          # Debug Nuxt issues
│   ├── review-python.md     # Python code review
│   ├── test-api.md          # Run API tests
│   └── setup-dev.md         # Environment setup
└── README.md                # This file
```

---

## 📚 Additional Resources

### OpenCode Documentation
- [Agents](https://opencode.ai/docs/agents/)
- [Commands](https://opencode.ai/docs/commands/)
- [Configuration](https://opencode.ai/docs/config/)

### Technology Documentation
- [Nuxt.js 4.x](https://nuxt.com/)
- [Vue 3](https://vuejs.org/)
- [TailwindCSS](https://tailwindcss.com/)
- [FastAPI](https://fastapi.tiangolo.com/)
- [LangChain](https://python.langchain.com/)
- [pnpm](https://pnpm.io/)
- [uv](https://github.com/astral-sh/uv)

---

## 💡 Tips and Best Practices

### Working with Agents

1. **Be Specific**: Provide detailed requirements and context
   ```bash
   # ❌ Bad
   @nuxt-expert create a button
   
   # ✅ Good
   @nuxt-expert create a primary action button with:
   - horus-accent-cyan background
   - Hover effect with glow animation
   - Loading state with spinner
   - TypeScript props for label, onClick, disabled, loading
   ```

2. **Reference Existing Code**: Point agents to similar implementations
   ```bash
   @nuxt-expert Create a component similar to @app/components/ui/HButton.vue
   but with additional icon support
   ```

3. **Iterate**: Start with planning, then implement
   ```bash
   # First: Plan mode (Tab key)
   @api-expert Plan an endpoint for user authentication
   
   # Review the plan, then switch to Build mode
   # Second: Implement
   Go ahead and implement the plan
   ```

4. **Use Commands for Repetitive Tasks**: Save time with custom commands
   ```bash
   /fix-nuxt    # Instead of manually debugging
   /test-api    # Instead of running pytest manually
   ```

### Code Organization

1. **Frontend**: Follow Nuxt conventions
   - Components in `app/components/`
   - Pages in `app/pages/`
   - Composables in `app/composables/`
   - Use `<script setup lang="ts">` syntax

2. **Backend**: Follow layered architecture
   - Routes in `api/`
   - Business logic in `services/`
   - LangChain code in `chains/` and `agents/`
   - Pydantic models in `schemas/`

3. **Always Use Type Safety**:
   - TypeScript for frontend
   - Type hints for Python

---

## 🎯 Next Steps

After setup is complete:

1. **Explore the codebase** with agents:
   ```bash
   @nuxt-expert Explain how the MapVisualization component works
   ```

2. **Start building features**:
   ```bash
   @api-expert Help me create an endpoint for scenario generation
   ```

3. **Set up your workflow**:
   - Use `/fix-nuxt` for quick debugging
   - Use `/review-python` before commits
   - Use `/test-api` during development

4. **Customize agents** to match your team's conventions

---

## 🤝 Contributing

To improve these agents for the team:

1. Test agent responses and refine prompts
2. Add new custom commands for common tasks
3. Update agent knowledge as the codebase evolves
4. Share useful prompts and workflows with the team
5. Keep this README updated

---

## 📝 Notes

- **Backend Structure**: Waiting for instruction to create backend structure. Agents are ready for when backend is initialized.
- **Git Tracking**: All `.opencode/` files are tracked in Git for team sharing.
- **Per-Project Config**: These agents are specific to the Horus project.
- **Global Config**: You can also add personal agents in `~/.config/opencode/agents/`.

---

**Happy Coding! 🚀✈️**

For questions or issues, consult this README or ask the expert agents for help!
