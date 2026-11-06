import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    // Extra hostnames allowed to reach the dev server, comma-separated. Needed
    // when the app is served behind a tunnel or reverse proxy.
    allowedHosts: process.env.VITE_ALLOWED_HOSTS?.split(",") ?? [],
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
