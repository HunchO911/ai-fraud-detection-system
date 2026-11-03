import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development, "/api/..." requests are forwarded to Django, so the browser
// sees one origin and no CORS setup is needed. In production, set VITE_API_URL.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
    },
  },
});
