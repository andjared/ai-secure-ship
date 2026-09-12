import { defineConfig } from 'orval'

// Generated output — do not hand-edit. Run `npm run generate-api` to regenerate
// against the backend's live OpenAPI schema (backend must be running).
export default defineConfig({
  chat: {
    input: {
      target: 'http://localhost:8000/openapi.json',
    },
    output: {
      target: 'src/api/generated/chat.ts',
      client: 'react-query',
      mock: false,
    },
  },
})
