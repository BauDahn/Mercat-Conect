"""Cabeceras de seguridad (§18.2). ASGI puro: no rompe el streaming SSE."""
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
       "font-src 'self'; connect-src 'self'; worker-src 'self'; manifest-src 'self'; object-src 'none'; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


class SecurityHeadersMiddleware:
    def __init__(self, app, hsts: bool = False) -> None:
        self.app = app
        self.extra = [(b"content-security-policy", CSP.encode()), (b"x-content-type-options", b"nosniff"),
                      (b"referrer-policy", b"strict-origin-when-cross-origin"), (b"x-frame-options", b"DENY"),
                      (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")]
        if hsts:
            self.extra.append((b"strict-transport-security", b"max-age=31536000; includeSubDomains"))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def wrapped(message):
            if message["type"] == "http.response.start":
                have = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [h for h in self.extra if h[0] not in have]
            await send(message)
        return await self.app(scope, receive, wrapped)
