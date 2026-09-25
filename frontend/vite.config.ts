import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        // SSE: never buffer proxied streaming responses
        proxyTimeout: 0,
      },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      "/api": {
        // Overridden inside docker (see frontend/Dockerfile)
        target: process.env.CREO_API_PROXY_TARGET ?? "http://127.0.0.1:8000",
        changeOrigin: true,
        proxyTimeout: 0,
      },
    },
  },
  test: {
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
