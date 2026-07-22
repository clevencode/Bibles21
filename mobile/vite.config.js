import { defineConfig } from "vite";

export default defineConfig({
  root: ".",
  publicDir: "public",
  build: {
    outDir: "www",
    emptyOutDir: true,
    assetsDir: "assets",
  },
});
