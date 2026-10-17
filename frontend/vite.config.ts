import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/api": { target: process.env.VITE_PROXY_TARGET ?? "http://localhost:8000", changeOrigin: true } },
  },
  preview: { port: 4173, proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } } },
  build: {
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("leaflet")) return "map";
          if (id.includes("framer-motion")) return "motion";
          if (id.includes("node_modules/three")) return "three"; // only the landing 3D scene, loaded lazily
          if (id.includes("node_modules")) return "vendor";
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    // the first render in each file pays for jsdom + framer-motion start-up, which can exceed 5 s on slow machines
    testTimeout: 30_000,
  },
});
