const GATEWAY_URL = process.env.NEXT_PUBLIC_GATEWAY_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly problem: {
      type: string
      title: string
      status: number
      detail: string
      instance?: string
      contract_version?: string
      retry_after?: number
    },
  ) {
    super(problem.detail)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${GATEWAY_URL}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  })

  if (!res.ok) {
    const contentType = res.headers.get('content-type') ?? ''
    if (contentType.includes('problem+json') || contentType.includes('json')) {
      const problem = await res.json()
      throw new ApiError(res.status, {
        type: problem.type ?? 'about:blank',
        title: problem.title ?? res.statusText,
        status: res.status,
        detail: problem.detail ?? 'Erro desconhecido.',
        instance: problem.instance,
        contract_version: problem.contract_version,
        retry_after: problem['retry-after'] ?? res.headers.get('Retry-After')
          ? Number(res.headers.get('Retry-After'))
          : undefined,
      })
    }
    throw new ApiError(res.status, {
      type: 'about:blank',
      title: res.statusText,
      status: res.status,
      detail: `HTTP ${res.status}`,
    })
  }

  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'POST', body: JSON.stringify(body) }),
  postForm: <T>(path: string, body: FormData) =>
    request<T>(path, {
      method: 'POST',
      body,
      headers: {},
    }),
}
