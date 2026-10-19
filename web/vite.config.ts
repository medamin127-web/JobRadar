import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The page calls /api/...; in development Vite passes those calls to the
// Python API (uvicorn api.server:app --port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});