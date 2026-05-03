import os
import sys
from urllib.parse import urlparse

import requests

WEBSITE_REPOS = [
	"bpwaterheaters",
]

DOCUMENTATION_DOMAINS = [
	"bpwaterheaters.com",
]


def is_valid_url(url: str) -> bool:
	parts = urlparse(url)
	return all((parts.scheme, parts.netloc, parts.path))


def is_documentation_link(word: str) -> bool:
	if not word.startswith("http") or not is_valid_url(word):
		return False

	parsed_url = urlparse(word)
	if parsed_url.netloc in DOCUMENTATION_DOMAINS:
		return True

	if parsed_url.netloc == "github.com":
		parts = parsed_url.path.split("/")
		if len(parts) >= 3 and parts[2] in WEBSITE_REPOS:
			return True

	return False


def contains_documentation_link(body: str) -> bool:
	return any(is_documentation_link(word) for line in body.splitlines() for word in line.split())


def check_pull_request(number: str) -> "tuple[int, str]":
	repository = os.environ.get("GITHUB_REPOSITORY", "erikcode-create/bpwaterheaters")
	headers = {"Accept": "application/vnd.github+json"}
	token = os.environ.get("GITHUB_TOKEN")
	if token:
		headers["Authorization"] = f"Bearer {token}"

	response = requests.get(
		f"https://api.github.com/repos/{repository}/pulls/{number}",
		headers=headers,
		timeout=15,
	)
	if not response.ok:
		return 1, "Pull request not found."

	payload = response.json()
	title = (payload.get("title") or "").lower().strip()
	head_sha = (payload.get("head") or {}).get("sha")
	body = (payload.get("body") or "").lower()

	if not title.startswith("feat") or not head_sha or "no-docs" in body or "backport" in body:
		return 0, "Skipping documentation checks."

	if contains_documentation_link(body):
		return 0, "Documentation link found."

	return 1, "Documentation link not found."


if __name__ == "__main__":
	exit_code, message = check_pull_request(sys.argv[1])
	print(message)
	sys.exit(exit_code)
