import { defineConfig } from "vite";
export default defineConfig({ root: "site-static", base: "/spendcourt-genlayer/", build: { outDir: "../pages-dist", emptyOutDir: true } });
