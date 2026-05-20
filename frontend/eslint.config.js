// ESLint flat config — minimal, focused on catching real bugs.
//
// Why these rules:
//   - `no-undef` catches the `error is not defined` pattern where a catch
//     block was accidentally closed too early, and missing imports.
//   - `no-unreachable` catches dead code after malformed control flow.
//   - The rest are kept as warnings so the error count stays meaningful.
//
// How to run:
//   1) If `frontend/node_modules` is writable to your user:
//        npm install --save-dev eslint eslint-plugin-vue globals
//        npx eslint src
//   2) Otherwise install into a side directory:
//        mkdir -p /tmp/erp-lint && cd /tmp/erp-lint
//        npm init -y && npm pkg set type=module
//        npm install eslint eslint-plugin-vue globals
//        ln -sfn /home/administrator/erp/frontend/src src
//        cp /home/administrator/erp/frontend/eslint.config.js .
//        ./node_modules/.bin/eslint src
import js from '@eslint/js'
import vue from 'eslint-plugin-vue'
import globals from 'globals'

export default [
  js.configs.recommended,
  ...vue.configs['flat/essential'],
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      'no-undef': 'error',
      'no-unreachable': 'error',
      'no-unused-vars': ['warn', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrors: 'none',
      }],
      'no-empty': ['warn', { allowEmptyCatch: true }],
      'vue/multi-word-component-names': 'off',
      'vue/no-mutating-props': 'warn',
      'vue/no-unused-vars': ['warn', { ignorePattern: '^_' }],
    },
  },
  {
    ignores: ['**/node_modules/**', '**/dist/**', '**/*.bak', '**/*.bak2'],
  },
]
