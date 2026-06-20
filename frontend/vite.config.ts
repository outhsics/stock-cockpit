import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During dev (vite dev server on :5173), proxy /api to the backend on :8000.
// In production, the FastAPI container serves the built bundle directly.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: false,
  },
});
