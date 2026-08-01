import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit, urlunsplit


class UnsupportedSocialURL(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class SocialURLReference:
    platform: str
    canonical_url: str
    external_id: str | None
    share_text: str


_XHS_CONTENT_PATTERNS = (
    re.compile(r"^/explore/(?P<id>[A-Za-z0-9_-]{8,128})/?$"),
    re.compile(r"^/discovery/item/(?P<id>[A-Za-z0-9_-]{8,128})/?$"),
)
_DOUYIN_CONTENT_PATTERNS = (
    re.compile(r"^/video/(?P<id>[0-9]{8,32})/?$"),
    re.compile(r"^/note/(?P<id>[0-9]{8,32})/?$"),
)
_BILIBILI_CONTENT_PATTERNS = (
    re.compile(r"^/video/(?P<id>BV[A-Za-z0-9]{8,20})/?$", re.IGNORECASE),
    re.compile(r"^/video/(?P<id>av[0-9]{1,20})/?$", re.IGNORECASE),
)
_TWITTER_CONTENT_PATTERNS = (
    re.compile(r"^/(?P<handle>[A-Za-z0-9_]{1,15})/status/(?P<id>[0-9]{1,32})/?$"),
)


def normalize_content_url(value: str) -> SocialURLReference:
    if len(value) > 2048:
        raise UnsupportedSocialURL("URL is too long")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"}:
        raise UnsupportedSocialURL("Only HTTP and HTTPS social URLs are supported")
    if parsed.username or parsed.password:
        raise UnsupportedSocialURL("URLs containing credentials are not allowed")
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise UnsupportedSocialURL("URL host is missing")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise UnsupportedSocialURL("IP address URLs are not allowed")
    if parsed.port not in {None, 80, 443}:
        raise UnsupportedSocialURL("Non-standard URL ports are not allowed")

    path = unquote(parsed.path)
    if _is_host(host, "xiaohongshu.com"):
        external_id = None
        for pattern in _XHS_CONTENT_PATTERNS:
            matched = pattern.fullmatch(path)
            if matched:
                external_id = matched.group("id")
                break
        if external_id is None:
            raise UnsupportedSocialURL("The URL is not a supported Xiaohongshu content URL")
        canonical_url = f"https://www.xiaohongshu.com/explore/{external_id}"
        return SocialURLReference(
            platform="xiaohongshu",
            canonical_url=canonical_url,
            external_id=external_id,
            share_text=value.strip(),
        )

    if _is_host(host, "xhslink.com"):
        normalized_path = "/" + "/".join(segment for segment in path.split("/") if segment)
        if normalized_path == "/":
            raise UnsupportedSocialURL("The Xiaohongshu share URL path is missing")
        canonical_url = urlunsplit(("https", host, normalized_path, "", ""))
        return SocialURLReference(
            platform="xiaohongshu",
            canonical_url=canonical_url,
            external_id=None,
            share_text=value.strip(),
        )

    if _is_host(host, "douyin.com"):
        external_id = None
        for pattern in _DOUYIN_CONTENT_PATTERNS:
            matched = pattern.fullmatch(path)
            if matched:
                external_id = matched.group("id")
                break
        if external_id is None:
            raise UnsupportedSocialURL("The URL is not a supported Douyin content URL")
        return SocialURLReference(
            platform="douyin",
            canonical_url=f"https://www.douyin.com/video/{external_id}",
            external_id=external_id,
            share_text=value.strip(),
        )

    if _is_host(host, "bilibili.com"):
        external_id = None
        for pattern in _BILIBILI_CONTENT_PATTERNS:
            matched = pattern.fullmatch(path)
            if matched:
                external_id = matched.group("id")
                break
        if external_id is None:
            raise UnsupportedSocialURL("The URL is not a supported Bilibili video URL")
        if external_id.lower().startswith("bv"):
            external_id = f"BV{external_id[2:]}"
        return SocialURLReference(
            platform="bilibili",
            canonical_url=f"https://www.bilibili.com/video/{external_id}",
            external_id=external_id,
            share_text=value.strip(),
        )

    if _is_host(host, "twitter.com") or _is_host(host, "x.com"):
        external_id = None
        handle = None
        for pattern in _TWITTER_CONTENT_PATTERNS:
            matched = pattern.fullmatch(path)
            if matched:
                external_id = matched.group("id")
                handle = matched.group("handle")
                break
        if external_id is None:
            raise UnsupportedSocialURL("The URL is not a supported X/Twitter content URL")
        canonical_url = f"https://x.com/{handle}/status/{external_id}"
        return SocialURLReference(
            platform="x",
            canonical_url=canonical_url,
            external_id=external_id,
            share_text=value.strip(),
        )

    if _is_host(host, "b23.tv"):
        normalized_path = "/" + "/".join(segment for segment in path.split("/") if segment)
        if normalized_path == "/":
            raise UnsupportedSocialURL("The Bilibili share URL path is missing")
        return SocialURLReference(
            platform="bilibili",
            canonical_url=urlunsplit(("https", host, normalized_path, "", "")),
            external_id=None,
            share_text=value.strip(),
        )

    raise UnsupportedSocialURL("The social platform or URL format is not supported")


def _is_host(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")
