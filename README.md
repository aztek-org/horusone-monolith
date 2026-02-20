# Horus MVP - Aviation Training Platform

AI-Powered Aviation Training & Simulation Platform built with NuxtJS, TailwindCSS, and TypeScript.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Nuxt](https://img.shields.io/badge/Nuxt-4.x-00DC82.svg)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3.x-38B2AC.svg)

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
