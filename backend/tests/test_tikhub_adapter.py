import json
from pathlib import Path

from app.providers.social.tikhub.xiaohongshu import (
    XiaohongshuAppV2Adapter,
    parse_count,
)

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_count_handles_chinese_display_units():
    assert parse_count("1.2万") == 12_000
    assert parse_count("3.5亿") == 350_000_000
    assert parse_count("1,234") == 1_234
    assert parse_count(None) is None
    assert parse_count("unknown") is None


def test_profile_normalization_uses_null_for_missing_metrics():
    profile = XiaohongshuAppV2Adapter().parse_profile(
        _fixture("xhs_profile_representative.json"),
        external_id="profile-fixture-001",
    )

    assert profile.display_name == "示例餐饮运营"
    assert profile.followers == 12_000
    assert profile.following == 88
    assert profile.total_likes == 34_000
    assert profile.content_count == 128


def test_profile_contents_normalization_preserves_missing_views_as_null():
    page = XiaohongshuAppV2Adapter().parse_profile_contents(
        _fixture("xhs_profile_notes_representative.json"),
        profile_id="profile-fixture-001",
    )

    assert page.next_cursor == "note-fixture-001"
    assert len(page.items) == 1
    item = page.items[0]
    assert item.external_id == "note-fixture-001"
    assert item.metrics.views is None
    assert item.metrics.likes == 15_000
    assert item.metrics.favorites == 6_800
    assert item.canonical_url.endswith("/note-fixture-001")


def test_content_detail_normalization():
    item = XiaohongshuAppV2Adapter().parse_content_detail(
        _fixture("xhs_content_detail_representative.json"),
        content_type="image_text",
    )

    assert item.external_id == "note-detail-fixture-001"
    assert item.body_text == "用于链接导入契约测试的去敏代表性正文。"
    assert item.metrics.likes == 2_300
    assert item.metrics.views is None
    assert len(item.media) == 2
