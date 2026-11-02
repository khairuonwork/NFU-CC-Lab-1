import type { RequestHandler } from './$types';

export const GET: RequestHandler = () => {
  return Response.json({
    service: 'cc-client',
    status: 'ready',
  });
};
