from __future__ import annotations

PORTAL_HOSTS = frozenset({"portal.bpwaterheaters.com"})

JUNK_PROBE_ROUTES = (
	"/wp-admin/install.php",
	"/wp-login.php",
	"/xmlrpc.php",
	"/.env",
	"/phpinfo.php",
	"/adminer.php",
	"/ads.txt",
	"/llms.txt",
)


def is_portal_host(host: str | None) -> bool:
	return (host or "").split(":", 1)[0].strip().lower() in PORTAL_HOSTS
