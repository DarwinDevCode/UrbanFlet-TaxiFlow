// Config ESLint compartida por las 3 apps (web-pasajero, web-conductor,
// web-interno) y shared-ui — mismo stack en las 4 (React 18 + TypeScript +
// Vite), sin diferencias reales entre ellas que justifiquen configs
// separadas. Sigue el patrón que genera el propio template de Vite
// (npm create vite -- --template react-ts): js recommended + typescript-eslint
// recommended (sin type-checking, para no requerir parserOptions.project por
// paquete) + react-hooks + react-refresh.
//
// Cada app llama a este archivo con `eslint .` desde su propio directorio
// (ver script "lint" en cada package.json) — ESLint flat config busca
// eslint.config.js subiendo desde el cwd hasta encontrarlo, así que no hace
// falta un eslint.config.js por app.
import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["**/dist/**", "**/node_modules/**", "**/*.tsbuildinfo"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["apps/*/src/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      // shared-ui exporta muchos componentes + tipos desde el mismo archivo
      // index.ts a propósito (es una librería interna, no una app con HMR de
      // páginas) — no aplica la advertencia de react-refresh ahí.
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
  {
    files: ["apps/shared-ui/src/**/*.{ts,tsx}"],
    rules: {
      "react-refresh/only-export-components": "off",
    },
  },
  {
    files: ["apps/*/src/**/*.test.{ts,tsx}", "apps/*/src/setupTests.ts"],
    languageOptions: {
      globals: globals.vitest,
    },
  },
);
