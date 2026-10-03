// Fetch wrapper with error normalization.
// Backend error shape: {"detail": "human readable message"} + HTTP status.

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options) {
  let res;
  try {
    res = await fetch(path, options);
  } catch (networkErr) {
    throw new ApiError(0, "Cannot reach the RideShield API. Is the backend running on this machine?");
  }
  let body = null;
  try {
    body = await res.json();
  } catch (parseErr) {
    body = null;
  }
  if (!res.ok) {
    let detail = body && body.detail !== undefined ? body.detail : null;
    if (Array.isArray(detail)) {
      detail = detail.map(function (d) { return d && d.msg ? d.msg : JSON.stringify(d); }).join("; ");
    }
    if (detail === null || detail === "") {
      detail = "Request failed (HTTP " + res.status + ")";
    }
    throw new ApiError(res.status, String(detail));
  }
  return body;
}

export const api = {
  get: function (path) {
    return request(path);
  },
  post: function (path, data) {
    return request(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {}),
    });
  },
};
