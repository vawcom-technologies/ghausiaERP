"""Host and CSRF origin helpers for local, LAN, and Railway HTTPS."""


def hostname_from(value):
    """Turn a domain, URL, or host:port into a hostname Django can allow."""
    if not value:
        return ""
    host = str(value).strip()
    if not host:
        return ""
    host = host.replace("https://", "").replace("http://", "").split("/")[0]
    return host.strip().rstrip(".")


def parse_host_list(*values):
    """Split comma-separated hosts/URLs and drop empties, keeping order."""
    hosts = []
    seen = set()
    for value in values:
        if not value:
            continue
        parts = value if isinstance(value, (list, tuple)) else str(value).split(",")
        for part in parts:
            host = hostname_from(part)
            if host and host not in seen:
                seen.add(host)
                hosts.append(host)
    return hosts


def csrf_trusted_origins(hosts, extra_origins=()):
    """Build CSRF origins so sign-in POST works on HTTP local and HTTPS Railway."""
    origins = []
    seen = set()

    def add(origin):
        origin = (origin or "").rstrip("/")
        if origin and origin not in seen:
            seen.add(origin)
            origins.append(origin)

    for origin in extra_origins or ():
        for part in str(origin).split(","):
            add(part.strip())

    for host in hosts or ():
        hostname = hostname_from(host)
        if not hostname or hostname == "*" or hostname.startswith("."):
            continue
        if hostname in ("localhost", "127.0.0.1", "testserver"):
            add(f"http://{hostname}")
            add(f"http://{hostname}:8000")
            add(f"https://{hostname}")
            add(f"https://{hostname}:8000")
        else:
            add(f"https://{hostname}")
            add(f"http://{hostname}")
    return origins
