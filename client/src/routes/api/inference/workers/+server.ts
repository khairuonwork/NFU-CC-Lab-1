import type { RequestHandler } from './$types';

import {
  masterApiUrl,
  masterUnavailableResponse,
  proxyMasterResponse,
} from '#lib/server/master-api';

export const GET: RequestHandler = async () => {
  try {
    const response = await fetch(masterApiUrl('/inference/workers'), {
      headers: {
        accept: 'application/json',
      },
    });

    return proxyMasterResponse(response);
  } catch {
    return masterUnavailableResponse();
  }
};
