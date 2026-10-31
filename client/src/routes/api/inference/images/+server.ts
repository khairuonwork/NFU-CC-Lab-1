import type { RequestHandler } from './$types';

import {
  fetchMaster,
  masterUnavailableResponse,
  proxyMasterResponse,
} from '#lib/server/master-api';

export const POST: RequestHandler = async ({ request }) => {
  try {
    const formData = await request.formData();
    const response = await fetchMaster('/inference/images', {
      method: 'POST',
      body: formData,
      headers: {
        accept: 'application/json',
      },
    });

    return proxyMasterResponse(response);
  } catch {
    return masterUnavailableResponse();
  }
};
