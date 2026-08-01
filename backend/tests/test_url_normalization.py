import pytest

from app.providers.social.url_normalization import (
    UnsupportedSocialURL,
    normalize_content_url,
)


def test_normalizes_direct_xiaohongshu_content_url():
    reference = normalize_content_url(
        "https://www.xiaohongshu.com/explore/697c0eee000000000a03c308?source=web"
    )

    assert reference.platform == "xiaohongshu"
    assert reference.external_id == "697c0eee000000000a03c308"
    assert reference.canonical_url == "https://www.xiaohongshu.com/explore/697c0eee000000000a03c308"


def test_accepts_share_domain_without_following_redirect():
    reference = normalize_content_url("http://xhslink.com/o/8GqargIxrko?tracking=1")

    assert reference.platform == "xiaohongshu"
    assert reference.external_id is None
    assert reference.canonical_url == "https://xhslink.com/o/8GqargIxrko"


@pytest.mark.parametrize(
    ("url", "platform", "external_id", "canonical_url"),
    [
        (
            "https://www.douyin.com/video/7534641277405531446?from=web",
            "douyin",
            "7534641277405531446",
            "https://www.douyin.com/video/7534641277405531446",
        ),
        (
            "https://www.bilibili.com/video/bv1S5uKzzE4r?p=1",
            "bilibili",
            "BV1S5uKzzE4r",
            "https://www.bilibili.com/video/BV1S5uKzzE4r",
        ),
        (
            "https://x.com/elonmusk/status/1808168603721650364?s=20",
            "x",
            "1808168603721650364",
            "https://x.com/elonmusk/status/1808168603721650364",
        ),
        (
            "https://mobile.twitter.com/elonmusk/status/1808168603721650364",
            "x",
            "1808168603721650364",
            "https://x.com/elonmusk/status/1808168603721650364",
        ),
        (
            "https://www.tiktok.com/@jennmelon/video/7350810998023949599",
            "tiktok",
            "7350810998023949599",
            "https://www.tiktok.com/@jennmelon/video/7350810998023949599",
        ),
        (
            "https://www.tiktok.com/video/7350810998023949599",
            "tiktok",
            "7350810998023949599",
            "https://www.tiktok.com/video/7350810998023949599",
        ),
    ],
)
def test_normalizes_supported_content_urls(url, platform, external_id, canonical_url):
    reference = normalize_content_url(url)

    assert reference.platform == platform
    assert reference.external_id == external_id
    assert reference.canonical_url == canonical_url


@pytest.mark.parametrize(
    "url",
    [
        "https://x.com/elonmusk",
        "https://twitter.com/elonmusk/status/abc",
        "https://t.co/abc123",
        "https://x.com/elonmusk/status/",
        "https://vm.tiktok.com/ZMabcdef/",
        "https://www.tiktok.com/@jennmelon/video/abc",
    ],
)
def test_rejects_unsupported_twitter_urls(url):
    with pytest.raises(UnsupportedSocialURL):
        normalize_content_url(url)


def test_accepts_bilibili_share_domain_without_following_redirect():
    reference = normalize_content_url("https://b23.tv/example123?tracking=1")

    assert reference.platform == "bilibili"
    assert reference.external_id is None
    assert reference.canonical_url == "https://b23.tv/example123"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data",
        "https://xiaohongshu.com.evil.example/explore/697c0eee000000000a03c308",
        "file:///etc/passwd",
        "https://user:password@www.xiaohongshu.com/explore/697c0eee000000000a03c308",
        "https://www.xiaohongshu.com:8443/explore/697c0eee000000000a03c308",
    ],
)
def test_rejects_unsafe_or_unsupported_urls(url):
    with pytest.raises(UnsupportedSocialURL):
        normalize_content_url(url)
