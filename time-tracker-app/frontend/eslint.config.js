import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";
import eslintConfigPrettier from "eslint-config-prettier";

export default tseslint.config(
  { ignores: ["dist", "coverage"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2023,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
      // This React Compiler-oriented rule flags the standard "setLoading(true); fetch().finally(...)"
      // data-fetching effect pattern used throughout src/hooks and src/pages — a legitimate,
      // widely-used pattern here (this app doesn't use the React Compiler). Disabled rather than
      // contorting straightforward async-effect code to satisfy a not-yet-applicable lint rule.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  eslintConfigPrettier,
);
