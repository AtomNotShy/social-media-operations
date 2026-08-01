import json
from pathlib import Path

from app.providers.social.tikhub.douyin import TikTokAppV3Adapter
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


def test_profile_real_response_contract():
    profile = XiaohongshuAppV2Adapter().parse_profile(
        _fixture("xhs_profile_representative.json"),
        external_id="61b46d790000000010008153",
    )

    assert profile.display_name == "JeremyLin林书豪"
    assert profile.handle == "1429907658"
    assert profile.bio == "职业篮球运动员"
    assert profile.followers == 189_402
    assert profile.following == 7
    assert profile.total_likes == 518_721
    assert profile.content_count == 311


def test_profile_contents_real_response_contract():
    page = XiaohongshuAppV2Adapter().parse_profile_contents(
        _fixture("xhs_profile_notes_representative.json"),
        profile_id="61b46d790000000010008153",
    )

    assert page.next_cursor == "6a6b4b0b000000002c004cb2"
    assert len(page.items) == 3
    item = page.items[0]
    assert item.external_id == "68b39115000000001c037dad"
    assert item.content_type == "video"
    assert item.duration_ms == 55_000
    assert item.metrics.views == 0
    assert item.metrics.likes == 20_074
    assert item.metrics.comments == 890
    assert item.metrics.favorites == 1_156
    assert item.metrics.shares == 2_187
    assert item.author["external_id"] == "61b46d790000000010008153"
    assert item.author["display_name"] == "JeremyLin林书豪"
    assert item.media[0]["type"] == "cover"
    assert item.media[0]["url"].startswith("https://sns-i11.rednotecdn.com/")
    assert item.canonical_url.endswith("/68b39115000000001c037dad")
    assert page.items[1].content_type == "image_text"


def test_content_detail_real_response_contract():
    item = XiaohongshuAppV2Adapter().parse_content_detail(
        _fixture("xhs_content_detail_representative.json"),
        content_type="image_text",
    )

    assert item.external_id == "697c0eee000000000a03c308"
    assert item.title == "68岁传奇大师和妻子造房隐居，美得像电影"
    assert item.body_text.startswith("68岁的摄影师上田义彦与妻子桐岛加恋")
    assert item.metrics.likes == 8_874
    assert item.metrics.comments == 194
    assert item.metrics.favorites == 4_253
    assert item.metrics.shares == 2_830
    assert item.metrics.views == 0
    assert len(item.media) == 1
    assert item.media[0]["type"] == "image"
    assert item.media[0]["url"].startswith("https://sns-i11.rednotecdn.com/")
    assert item.author["display_name"] == "一条"
    assert item.author["handle"] == "332831015"
    assert item.author["external_id"] == "5efc6e660000000001006da1"


def test_video_detail_real_response_contract():
    item = XiaohongshuAppV2Adapter().parse_content_detail(
        _fixture("xhs_video_detail_representative.json"),
        content_type="video",
    )

    assert item.external_id == "697c0eee000000000a03c308"
    assert item.content_type == "video"
    assert item.duration_ms == 410_000
    assert item.metrics.likes == 8_874
    assert item.metrics.comments == 194
    assert item.metrics.favorites == 4_253
    assert item.metrics.shares == 2_830
    assert item.metrics.views == 0
    video = next(media for media in item.media if media["type"] == "video")
    assert video["url"].startswith("sns-v28.rednotecdn.com/stream/") or video["url"].startswith(
        "http://sns-v28.rednotecdn.com/stream/"
    )
    assert any(media["type"] == "cover" for media in item.media)
    assert item.author["display_name"] == "一条"


def test_tiktok_video_detail_real_response_contract():
    item = TikTokAppV3Adapter().parse_content_detail(
        _fixture("tiktok_video_detail_representative.json"),
        content_type="video",
    )

    assert item.platform == "tiktok"
    assert item.external_id == "7350810998023949599"
    assert item.canonical_url == "https://www.tiktok.com/video/7350810998023949599"
    assert item.content_type == "video"
    assert item.duration_ms == 5_900
    assert item.body_text == "im so sick of being tired im so tired of being sick"
    assert item.metrics.views == 12_187_417
    assert item.metrics.likes == 2_004_082
    assert item.metrics.comments == 7_829
    assert item.metrics.favorites == 211_565
    assert item.metrics.shares == 275_192
    assert item.metrics.downloads == 20_349
    assert item.author["display_name"] == "Jenn Melon"
    assert item.author["handle"] == "jennmelon"
    assert (
        item.author["external_id"]
        == "MS4wLjABAAAAdsKhQYdpLrOx5hrYCM3O2FQK3Xhnncm0ZHzGROFGk43iPIEPqxyEOK_YWom9LoKn"
    )
    assert {media["type"] for media in item.media} == {"cover", "video"}
    assert item.media[0]["url"].startswith("https://p19-common-sign.tiktokcdn-us.com/")
