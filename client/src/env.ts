import { defineEnvVars } from '@sveltejs/kit/env';

export const variables = defineEnvVars({
  MASTER_API_BASE_URL: {
    schema: (value) => value ?? 'http://127.0.0.1:18000',
    description: 'Private base URL used by the SvelteKit server to reach the Master API.',
  },
});
