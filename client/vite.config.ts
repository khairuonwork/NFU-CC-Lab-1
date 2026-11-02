import adapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ mode }) => {
  const environment = loadEnv(mode, '.', '');

  return {
    plugins: [
      sveltekit({
        adapter: adapter(),
        paths: {
          origin: environment.CLIENT_ORIGIN || undefined,
        },
      }),
    ],
  };
});
