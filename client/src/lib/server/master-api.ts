import { MASTER_API_BASE_URL } from '$app/env/private';

export function masterApiUrl(path: string): string {
  if (!MASTER_API_BASE_URL) {
    throw new Error('MASTER_API_BASE_URL is not configured for the SvelteKit server.');
  }

  const baseUrl = MASTER_API_BASE_URL.replace(/\/$/, '');
  return `${baseUrl}${path}`;
}

export async function fetchMaster(path: string, init: RequestInit): Promise<Response> {
  try {
    const url = masterApiUrl(path);
    return await fetch(url, init);
  } catch (error) {
    console.error(`Master API proxy request failed for path: ${path}`, error);
    throw error;
  }
}

export async function proxyMasterResponse(response: Response): Promise<Response> {
  const headers = new Headers();
  const contentType = response.headers.get('content-type');

  if (contentType) {
    headers.set('content-type', contentType);
  }

  headers.set('cache-control', 'no-store');

  return new Response(await response.arrayBuffer(), {
    status: response.status,
    headers,
  });
}

export function masterUnavailableResponse(): Response {
  return Response.json(
    {
      status: 'master_unavailable',
      message: 'The Master API cannot be reached from the client server.',
    },
    {
      status: 503,
      headers: {
        'cache-control': 'no-store',
      },
    },
  );
}
