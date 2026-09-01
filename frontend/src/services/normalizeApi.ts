export interface NormalizeApiResponse {
  status: string;
  original_text: string;
  normalized_text: string;
  latency_ms: number;
}

export class NormalizeApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'NormalizeApiError';
    this.status = status;
  }
}

export function getApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (typeof envUrl === 'string' && envUrl.trim().length > 0) {
    return envUrl.trim().replace(/\/+$/, '');
  }

  // Development environment fallback
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:8000';
  }

  // Production build requires VITE_API_BASE_URL
  throw new NormalizeApiError('Chưa cấu hình địa chỉ máy chủ API (VITE_API_BASE_URL).');
}

export async function normalizeText(text: string): Promise<string> {
  const baseUrl = getApiBaseUrl();
  const endpoint = `${baseUrl}/api/normalize`;

  let response: Response;
  try {
    response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ text }),
    });
  } catch (err) {
    if (err instanceof NormalizeApiError) {
      throw err;
    }
    throw new NormalizeApiError('Không thể kết nối đến máy chủ. Vui lòng thử lại sau.');
  }

  if (!response.ok) {
    let errorDetail = 'Không thể chuẩn hóa văn bản. Vui lòng thử lại.';
    try {
      const errorJson = await response.json();
      if (errorJson && typeof errorJson.detail === 'string') {
        errorDetail = errorJson.detail;
      }
    } catch {
      // Use default friendly error message if parsing response fails
    }
    throw new NormalizeApiError(errorDetail, response.status);
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new NormalizeApiError('Phản hồi từ máy chủ không hợp lệ. Vui lòng thử lại.');
  }

  if (
    typeof data === 'object' &&
    data !== null &&
    'normalized_text' in data &&
    typeof (data as { normalized_text: unknown }).normalized_text === 'string'
  ) {
    return (data as { normalized_text: string }).normalized_text;
  }

  throw new NormalizeApiError('Dữ liệu kết quả không đúng định dạng mong đợi.');
}
