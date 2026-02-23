
import { z } from 'zod';
import { insertMessageSchema, threads, messages } from './schema';

export const errorSchemas = {
  validation: z.object({
    message: z.string(),
    field: z.string().optional(),
  }),
  notFound: z.object({
    message: z.string(),
  }),
  internal: z.object({
    message: z.string(),
  }),
};

export const api = {
  chat: {
    sendMessage: {
      method: 'POST' as const,
      path: '/api/chat' as const,
      input: z.object({
        message: z.string(),
        threadId: z.number().optional(),
        model: z.enum(['sonar', 'sonar-pro', 'sonar-reasoning', 'sonar-reasoning-pro']).optional(),
      }),
      // Response is a stream, but we define the success status
      responses: {
        200: z.void(), 
        400: errorSchemas.validation,
      },
    },
  },
  threads: {
    list: {
      method: 'GET' as const,
      path: '/api/threads' as const,
      responses: {
        200: z.array(z.custom<typeof threads.$inferSelect>()),
      },
    },
    get: {
      method: 'GET' as const,
      path: '/api/threads/:id' as const,
      responses: {
        200: z.custom<typeof threads.$inferSelect & { messages: typeof messages.$inferSelect[] }>(),
        404: errorSchemas.notFound,
      },
    },
    create: {
      method: 'POST' as const,
      path: '/api/threads' as const,
      input: z.object({ title: z.string().optional() }),
      responses: {
        201: z.custom<typeof threads.$inferSelect>(),
      },
    }
  },
};

export function buildUrl(path: string, params?: Record<string, string | number>): string {
  let url = path;
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (url.includes(`:${key}`)) {
        url = url.replace(`:${key}`, String(value));
      }
    });
  }
  return url;
}
