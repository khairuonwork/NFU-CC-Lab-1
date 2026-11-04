import type { RequestHandler } from './$types';

import {
  fetchMaster,
  masterUnavailableResponse,
  proxyMasterResponse,
} from '#lib/server/master-api';

export const POST: RequestHandler = async () => {
  try {
    const response = await fetchMaster('/inference/workers/refresh', {
      method: 'POST',
      headers: {
        accept: 'application/json',
      },
    });

    return proxyMasterResponse(response);
  } catch {
    return masterUnavailableResponse();
  }
};
