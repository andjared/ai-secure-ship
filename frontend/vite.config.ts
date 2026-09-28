import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    // The backend's CORS allows only http://localhost:3000, so fail loudly
    // instead of silently moving to another port.
    strictPort: true,
  },
});
