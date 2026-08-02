import json
from pathlib import Path

from app.providers.social.tikhub.xiaohongshu import XiaohongshuAppV2Adapter

FIXTURES = Path(__file__).parent / "fixtures" / "tikhub"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_xhs_content_detail_desc_fallback_keeps_paragraphs_hashtags_and_media():
    payload = _fixture("xhs_content_detail_representative.json")
    item = XiaohongshuAppV2Adapter().parse_content_detail(
        payload,
        content_type="image_text",
    )

    assert item.platform == "xiaohongshu"
    assert item.original_content is not None
    assert item.original_content["format"] == "xhs"
    blocks = item.original_content["blocks"]
    assert blocks[0]["type"] == "paragraph"
    assert blocks[0]["runs"][0]["style"] == "text"
    assert blocks[0]["runs"][-1] == {"text": "#人物#", "style": "hashtag"}
    assert any(
        block["type"] == "image" and "sns-i11.rednotecdn.com" in block["url"]
        for block in blocks
    )


def test_xhs_video_detail_desc_fallback_drops_title_line_and_keeps_video():
    payload = _fixture("xhs_video_detail_representative.json")
    item = XiaohongshuAppV2Adapter().parse_content_detail(
        payload,
        content_type="video",
    )

    blocks = item.original_content["blocks"]
    paragraph = blocks[0]
    assert paragraph["type"] == "paragraph"
    assert paragraph["runs"][0]["text"].startswith("68岁的摄影师上田义彦")
    assert not paragraph["runs"][0]["text"].startswith("68岁传奇大师")
    video_blocks = [
        block for block in blocks if block["type"] == "video" and block.get("url")
    ]
    assert video_blocks
    assert video_blocks[0]["cover_url"] is not None


def test_xhs_content_detail_structured_blocks_are_preserved():
    payload = {
        "code": 200,
        "request_id": "xhs-blocks-contract",
        "data": {
            "note_list": [
                {
                    "note_id": "1002003004005006001",
                    "title": "标题",
                    "desc": "",
                    "type": "normal",
                    "blocks": [
                        {
                            "type": "heading1",
                            "inline_data": [{"type": "text", "text": "小标题"}],
                        },
                        {
                            "type": "paragraph",
                            "inline_data": [
                                {"type": "text", "text": "第一段"},
                                {"type": "strong", "text": "加粗"},
                                {"type": "hash_tag", "text": "#灵感#"},
                                {"type": "at", "text": "@博主"},
                                {
                                    "type": "url",
                                    "text": "网页链接",
                                    "url": "https://example.com/a",
                                },
                            ],
                        },
                        {
                            "type": "image",
                            "image_list": [
                                {
                                    "url_default": "https://example.com/block-1.jpg",
                                    "width": 1080,
                                    "height": 1440,
                                }
                            ],
                        },
                        {"type": "divider"},
                        {
                            "type": "video",
                            "video": {
                                "master_url": "https://example.com/video.mp4",
                                "cover": {"url": "https://example.com/cover.jpg"},
                            },
                        },
                    ],
                }
            ]
        },
    }
    item = XiaohongshuAppV2Adapter().parse_content_detail(
        payload,
        content_type="image_text",
    )

    blocks = item.original_content["blocks"]
    assert blocks[0] == {
        "type": "heading",
        "runs": [{"text": "小标题", "style": "text", "url": None}],
    }
    assert blocks[1]["runs"] == [
        {"text": "第一段", "style": "text", "url": None},
        {"text": "加粗", "style": "bold", "url": None},
        {"text": "#灵感#", "style": "hashtag", "url": None},
        {"text": "@博主", "style": "mention", "url": None},
        {
            "text": "网页链接",
            "style": "url",
            "url": "https://example.com/a",
        },
    ]
    assert blocks[2] == {"type": "image", "url": "https://example.com/block-1.jpg"}
    assert blocks[3] == {"type": "divider"}
    assert blocks[4] == {
        "type": "video",
        "url": "https://example.com/video.mp4",
        "cover_url": "https://example.com/cover.jpg",
    }
