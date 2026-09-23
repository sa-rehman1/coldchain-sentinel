import { z, type ZodType } from 'zod';
import type { LocalIdentity } from '../contracts';

const errorEnvelopeSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    correlation_id: z.string().optional(),
    details: z.unknown().optional(),
  }),
});

export class ApiClientError extends Error {
  constructor(public readonly status: number | null, public readonly code: string, message: string, public readonly correlationId: string | null) {
    super(message);
    this.name = 'ApiClientError';
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  identity?: LocalIdentity;
  signal?: AbortSignal | undefined;
}

export class ApiClient {
  constructor(private readonly baseUrl = '/api/v1', private readonly timeoutMs = 10_000) {}

  async request<T>(path: string, schema: ZodType<T>, options: RequestOptions = {}): Promise<T> {
    const method = options.method ?? 'GET';
    const attempts = method === 'GET' ? 2 : 1;
    let lastError: unknown;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        return await this.once(path, schema, { ...options, method });
      } catch (error) {
        lastError = error;
        if (options.signal?.aborted || error instanceof ApiClientError && error.status !== null && error.status < 500) throw error;
      }
    }
    throw lastError;
  }

  private async once<T>(path: string, schema: ZodType<T>, options: RequestOptions & { method: 'GET' | 'POST' }): Promise<T> {
    const controller = new AbortController();
    const abort = () => controller.abort();
    options.signal?.addEventListener('abort', abort, { once: true });
    const timeout = window.setTimeout(abort, this.timeoutMs);
    const correlationId = crypto.randomUUID();
    try {
      const response = await fetch(`${this.baseUrl}${path}`, {
        method: options.method,
        signal: controller.signal,
        headers: {
          Accept: 'application/json',
          'X-Correlation-ID': correlationId,
          ...(options.body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...(options.identity ? { 'X-Actor-ID': options.identity.actorId, 'X-Actor-Roles': options.identity.roles.join(',') } : {}),
        },
        ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
      });
      const text = await response.text();
      if (text.length > 1_000_000) throw new ApiClientError(response.status, 'response_too_large', 'The server response exceeded the safe display limit.', response.headers.get('X-Correlation-ID'));
      let payload: unknown;
      try { payload = text ? JSON.parse(text) : null; } catch { throw new ApiClientError(response.status, 'invalid_json', 'The server returned an unreadable response.', response.headers.get('X-Correlation-ID')); }
      if (!response.ok) {
        const parsed = errorEnvelopeSchema.safeParse(payload);
        throw new ApiClientError(response.status, parsed.success ? parsed.data.error.code : 'request_failed', parsed.success ? parsed.data.error.message : 'The request could not be completed.', parsed.success ? parsed.data.error.correlation_id ?? null : response.headers.get('X-Correlation-ID'));
      }
      const parsed = schema.safeParse(payload);
      if (!parsed.success) throw new ApiClientError(response.status, 'response_validation_failed', 'The server response did not match the expected contract.', response.headers.get('X-Correlation-ID'));
      return parsed.data;
    } catch (error) {
      if (error instanceof ApiClientError) throw error;
      if (options.signal?.aborted) throw new ApiClientError(null, 'request_cancelled', 'The request was cancelled.', correlationId);
      if (controller.signal.aborted) throw new ApiClientError(null, 'request_timeout', 'The local API did not respond before the request timed out.', correlationId);
      throw new ApiClientError(null, 'network_unavailable', 'The local API is unavailable.', correlationId);
    } finally {
      window.clearTimeout(timeout);
      options.signal?.removeEventListener('abort', abort);
    }
  }
}
