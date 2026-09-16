// MedPilot API Client

const API_BASE = '/api';

export function getAuthToken() {
  return localStorage.getItem('medpilot_token') || '';
}

export function setAuthToken(token) {
  if (token) {
    localStorage.setItem('medpilot_token', token);
  } else {
    localStorage.removeItem('medpilot_token');
  }
}

export async function apiRequest(endpoint, options = {}) {
  const token = getAuthToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Unauthorized - clear token
    setAuthToken(null);
    window.dispatchEvent(new Event('auth:unauthorized'));
  }

  if (!response.ok) {
    let errorDetail = 'API Request Failed';
    try {
      const errJson = await response.json();
      if (typeof errJson.detail === 'string') {
        errorDetail = errJson.detail;
      } else if (Array.isArray(errJson.detail)) {
        errorDetail = errJson.detail
          .map((d) => {
            if (typeof d === 'string') return d;
            const field = d.loc && d.loc.length > 1 ? d.loc.slice(1).join('.') : '';
            return field ? `${field}: ${d.msg || JSON.stringify(d)}` : (d.msg || JSON.stringify(d));
          })
          .join('; ');
      } else if (errJson.detail && typeof errJson.detail === 'object') {
        errorDetail = JSON.stringify(errJson.detail);
      } else if (errJson.message) {
        errorDetail = errJson.message;
      } else {
        errorDetail = JSON.stringify(errJson);
      }
    } catch {
      errorDetail = response.statusText || `HTTP error ${response.status}`;
    }
    throw new Error(errorDetail);
  }

  // If response is a file/blob (like PDF download)
  const contentType = response.headers.get('content-type');
  if (contentType && contentType.includes('application/pdf')) {
    return response.blob();
  }

  return response.json();
}
