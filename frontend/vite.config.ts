import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The cockpit is served same-origin by FastAPI in production (dist/ mounted at /), so the API
// client uses relative "/api". In dev, Vite proxies "/api" to the running `python -m jarvis serve`.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8765",
        changeOrigin: true,
      },
    },
  },
  build: { outDir: "dist", emptyOutDir: true },
});
