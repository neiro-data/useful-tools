/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-only proxy so the app can call same-origin `/api/...` paths (see `src/api/client.ts`)
    // without CORS, while the FastAPI backend actually listens on its own origin (default
    // http://127.0.0.1:8000 — see `app/API_CONTRACT.md`). Override via VITE_BACKEND_ORIGIN.
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_ORIGIN ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (requestPath) => requestPath.replace(/^\/api/, ""),
      },
    },
    fs: {
      // Allow importing `../../design/tokens.css` from outside the frontend/ package root.
      allow: [path.resolve(__dirname, ".."), path.resolve(__dirname)],
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
  },
});
