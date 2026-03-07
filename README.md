# Horus — Aviation Training Platform

AI-Powered Aviation Training & Simulation Platform with real-time ATC voice communication.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Nuxt](https://img.shields.io/badge/Nuxt-4.x-00DC82.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)
![Python](https://img.shields.io/badge/Python-3.11-3776AB.svg)

## Architecture

| Layer | Tech | Deployment |
|-------|------|-----------|
| Frontend | Nuxt 4 + Vue 3 + TailwindCSS | Cloudflare Pages |
| Backend | FastAPI + Python 3.11 | Private VPS (Docker Compose) |
| Database | PostgreSQL 16 via SQLAlchemy 2 async | VPS (Docker) |
| LLM | Ollama (llama3) + LangChain | VPS (Docker) |
| STT | OpenAI Whisper | VPS |
| TTS | Coqui TTS / gTTS | VPS |

## 🚀 Quick Start

```bash
# Install dependencies
cd frontend
pnpm install

# Start development server
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview
```

Open [http://localhost:3000](http://localhost:3000) to view the application.

> **Full setup guide**: see [`docs/development.md`](docs/development.md)

## 📁 Project Structure

```
horus-mvp/
├── frontend/                       # Nuxt.js application
│   ├── app/
│   │   ├── components/
│   │   │   ├── ui/                    # Design system components (H prefix)
│   │   │   ├── shared/                # Shared layout components
│   │   │   ├── scenario-architect/    # Route & Scenario configuration
│   │   │   └── mission-hub/           # Live mission components
│   │   ├── composables/               # State management
│   │   ├── layouts/                   # Page layouts
│   │   ├── pages/                     # Route pages
│   │   └── assets/css/                # Global styles
│   ├── nuxt.config.ts
│   ├── tailwind.config.ts
│   └── package.json
└── backend/                       # Python FastAPI backend
```

## 🎨 Design System

### Color Palette

| Category | Token | Color |
|----------|-------|-------|
| Background | `horus-bg-primary` | `#0a0f1a` |
| Background | `horus-bg-secondary` | `#111827` |
| Accent | `horus-accent-cyan` | `#00d4ff` |
| Status | `horus-status-success` | `#10b981` |
| Status | `horus-status-warning` | `#f59e0b` |
| Status | `horus-status-danger` | `#ef4444` |

### UI Components

- HButton, HCard, HBadge, HSlider, HProgress
- HCheckbox, HChecklistItem, HDropdown
- HDataPanel, HSection, HStatusIndicator
- HStatusPill, HLogEntry, HRadioGroup, HButtonGroup

## 📱 Pages

| Route | Description |
|-------|-------------|
| `/configurator` | Route & Scenario Architect |
| `/library` | Scenario Library |
| `/performance` | Performance Analytics |
| `/mission/:id` | Live Mission Decision Hub |

## 📱 Responsive Design

- **Mobile** (< 768px): Collapsible sidebars, drawer navigation
- **Tablet** (768px - 1024px): Adjusted grid layouts
- **Desktop** (> 1024px): Full three-column layout

## 🧩 Architecture

Follows micro-frontend principles:

1. **Feature-based modules** - Components grouped by domain
2. **Shared composables** - Cross-cutting state management
3. **Design system** - Consistent UI components
4. **Independent modules** - Each module can render independently

## 📄 License

MIT
