import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig, type PluginOption } from "vite";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

function copyManifest(): PluginOption {
  return {
    name: "copy-extension-manifest",
    writeBundle() {
      const target = resolve(rootDir, "dist", "manifest.json");
      mkdirSync(dirname(target), { recursive: true });
      copyFileSync(resolve(rootDir, "manifest.json"), target);
    },
  };
}

export default defineConfig({
  plugins: [react(), copyManifest()],
  publicDir: "public",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      input: {
        "src/popup/popup": resolve(rootDir, "src/popup/popup.html"),
        "src/background/serviceWorker": resolve(rootDir, "src/background/serviceWorker.ts"),
        "src/content/shopeeContentScript": resolve(rootDir, "src/content/shopeeContentScript.ts"),
      },
      output: {
        entryFileNames: "[name].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
