# Saliency-Aware Collage Generator - Web UI

This directory contains the React Web UI for the Saliency-Aware Collage Generator.

The UI is built using:
- **React** (via Vite)
- **TypeScript**
- **Lucide React** (for icons)

## Prerequisites

- Node.js (v18 or newer recommended)
- A running instance of the FastAPI backend (see project root `README.md` and `api.py`)

## Development Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Start the development server:**
   ```bash
   npm run dev
   ```
   This will start Vite on `http://localhost:5173`.

   *Note: If you run `./start.sh` from the project root, it will start both the backend and this frontend concurrently.*

## Production Build

To build the UI for production, run:
```bash
npm run build
```
This generates static files in the `dist` folder.

## Linting

To run ESLint:
```bash
npm run lint
```
