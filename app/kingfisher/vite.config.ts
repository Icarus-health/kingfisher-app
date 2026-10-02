import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  publicDir: resolve(import.meta.dirname, "../../design-source"),
  build: {
    outDir: resolve(import.meta.dirname, "../dist"),
    emptyOutDir: true,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8890", "/context": "http://127.0.0.1:8890" },
  },
});
