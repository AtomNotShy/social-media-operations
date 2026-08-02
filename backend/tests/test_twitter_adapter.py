from datetime import datetime, timezone

from app.providers.social.tikhub.twitter import TwitterAdapter


def _payload(data):
    return {"code": 200, "request_id": "fixture", "data": data}


def test_x_profile_normalized_shape_is_normalized():
    item = TwitterAdapter().parse_profile(
        _payload(
            {
                "avatar": "https://pbs.twimg.com/avatar_normal.jpg",
                "blue_verified": True,
                "created_at": "Tue Jun 02 20:12:29 +0000 2009",
                "desc": "Mars & Cars, Chips & Dips",
                "friends": 1268,
                "id": "44196397",
                "media_count": 4304,
                "name": "Elon Musk",
                "profile": "elonmusk",
                "rest_id": "44196397",
                "statuses_count": 94081,
                "sub_count": 232098434,
                "verification_type": None,
            }
        ),
        external_id="elonmusk",
    )

    assert item.platform == "x"
    assert item.external_id == "elonmusk"
    assert item.display_name == "Elon Musk"
    assert item.handle == "elonmusk"
    assert item.bio == "Mars & Cars, Chips & Dips"
    assert item.followers == 232098434
    assert item.following == 1268
    assert item.content_count == 94081
    assert item.extra_metrics["rest_id"] == "44196397"
    assert item.extra_metrics["media_count"] == 4304


def test_x_profile_real_response_contract():
    import json
    from pathlib import Path

    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "tikhub" / "x_profile_representative.json").read_text(
            encoding="utf-8"
        )
    )
    item = TwitterAdapter().parse_profile(payload, external_id="elonmusk")

    assert item.platform == "x"
    assert item.display_name == "Elon Musk"
    assert item.handle == "elonmusk"
    assert item.bio is None
    assert item.followers == 241091948
    assert item.following == 1378
    assert item.content_count == 106511
    assert (
        item.avatar_url
        == "https://pbs.twimg.com/profile_images/2053244804520427520/m8mdWZCG_normal.jpg"
    )
    assert item.extra_metrics["rest_id"] == "44196397"
    assert item.extra_metrics["media_count"] == 4676
    assert item.extra_metrics["blue_verified"] is True


def test_x_profile_graphql_legacy_shape_is_normalized():
    payload = _payload(
        {
            "user": {
                "result": {
                    "rest_id": "44196397",
                    "core": {
                        "user_results": {
                            "result": {
                                "rest_id": "44196397",
                                "is_blue_verified": True,
                                "legacy": {
                                    "created_at": "Tue Jun 02 20:12:29 +0000 2009",
                                    "description": "Legacy bio",
                                    "followers_count": 999,
                                    "friends_count": 42,
                                    "favourites_count": 7,
                                    "statuses_count": 123,
                                    "name": "Elon Musk",
                                    "profile_image_url_https": "https://pbs.twimg.com/legacy.jpg",
                                    "screen_name": "elonmusk",
                                },
                            }
                        }
                    },
                }
            }
        }
    )
    item = TwitterAdapter().parse_profile(payload, external_id="44196397")

    assert item.display_name == "Elon Musk"
    assert item.handle == "elonmusk"
    assert item.bio == "Legacy bio"
    assert item.followers == 999
    assert item.following == 42
    assert item.total_likes == 7
    assert item.content_count == 123
    assert item.extra_metrics["blue_verified"] is True


def test_x_profile_contents_normalized_timeline_with_pinned_and_cursor():
    page = TwitterAdapter().parse_profile_contents(
        _payload(
            {
                "next_cursor": "NEXT",
                "pinned": {
                    "tweet_id": "2010873739349823764",
                    "text": "Pinned tweet",
                    "created_at": "Tue Jan 13 00:37:14 +0000 2026",
                    "author": {
                        "screen_name": "elonmusk",
                        "name": "Elon Musk",
                        "rest_id": "44196397",
                    },
                    "favorites": 47967,
                    "replies": 4428,
                    "retweets": 8451,
                    "views": "16072495",
                },
                "timeline": [
                    {
                        "tweet_id": "2011313989737959548",
                        "text": "",
                        "created_at": "Wed Jan 14 05:46:38 +0000 2026",
                        "author": {
                            "screen_name": "elonmusk",
                            "name": "Elon Musk",
                            "rest_id": "44196397",
                        },
                        "favorites": 0,
                        "retweeted_tweet": {
                            "tweet_id": "2011295728300437848",
                            "text": "Original text",
                            "author": {"screen_name": "XFreeze", "name": "X Freeze"},
                        },
                    },
                    {
                        "tweet_id": "2011313989737959547",
                        "text": "Video tweet",
                        "created_at": "2026-01-14T05:00:00Z",
                        "author": {
                            "screen_name": "elonmusk",
                            "name": "Elon Musk",
                            "rest_id": "44196397",
                        },
                        "favorites": 1234,
                        "views": "654321",
                        "media": [
                            {
                                "type": "video",
                                "media_url_https": "https://pbs.twimg.com/cover.jpg",
                                "video_info": {"duration_millis": 214000},
                            }
                        ],
                    },
                ],
            }
        ),
        profile_id="elonmusk",
    )

    assert page.next_cursor == "NEXT"
    assert [item.external_id for item in page.items] == [
        "2010873739349823764",
        "2011313989737959548",
        "2011313989737959547",
    ]
    pinned = page.items[0]
    assert pinned.body_text == "Pinned tweet"
    assert pinned.metrics.likes == 47967
    retweet = page.items[1]
    assert retweet.body_text == "Original text"
    assert retweet.canonical_url == "https://x.com/elonmusk/status/2011313989737959548"
    video = page.items[2]
    assert video.metrics.views == 654321
    assert video.duration_ms == 214000
    assert video.media == [
        {
            "type": "video",
            "url": "https://pbs.twimg.com/cover.jpg",
            "duration_ms": 214000,
        },
    ]
    assert video.published_at is not None


def test_x_real_response_media_dict_and_user_profile():
    payload = {
        "code": 200,
        "data": {
            "next_cursor": "DAAHCgABHOmpP4o__-oLAAIAAA",
            "pinned": {
                "tweet_id": "2083034836097192096",
                "text": "Wow, the situation in Spain looks crazy!",
                "created_at": "Fri Jul 31 03:39:40 +0000 2026",
                "views": "19121612",
                "favorites": 364203,
                "replies": 17396,
                "retweets": 43295,
                "media": {
                    "video": [
                        {
                            "media_url_https": "https://pbs.twimg.com/amplify_video_thumb/thumb.jpg",
                            "variants": [
                                {
                                    "bitrate": 632000,
                                    "content_type": "video/mp4",
                                    "url": "https://video.twimg.com/low.mp4?tag=29",
                                },
                                {
                                    "bitrate": 10368000,
                                    "content_type": "video/mp4",
                                    "url": "https://video.twimg.com/high.mp4?tag=29",
                                },
                            ],
                            "id": "2083034652650975233",
                        }
                    ]
                },
                "author": {
                    "rest_id": "44196397",
                    "name": "Elon Musk",
                    "screen_name": "elonmusk",
                    "avatar": "https://pbs.twimg.com/profile_images/avatar_normal.jpg",
                    "followers_count": None,
                    "blue_verified": True,
                },
            },
            "timeline": [
                {
                    "tweet_id": "2083287619064983711",
                    "text": "Legacy media shape",
                    "created_at": "Sat Aug 01 02:02:49 +0000 2026",
                    "entities": {
                        "media": [
                            {
                                "media_url_https": "https://pbs.twimg.com/media/legacy.jpg",
                                "type": "photo",
                                "id": "legacy-media-1",
                            }
                        ]
                    },
                    "author": {"screen_name": "elonmusk", "name": "Elon Musk"},
                    "favorites": 910,
                }
            ],
            "status": "ok",
            "user": {
                "profile": "elonmusk",
                "id": "44196397",
                "created_at": "Tue Jun 02 20:12:29 +0000 2009",
                "avatar": "https://pbs.twimg.com/profile_images/avatar_normal.jpg",
                "blue_verified": True,
                "desc": None,
                "name": "Elon Musk",
                "friends": None,
                "sub_count": None,
                "statuses_count": None,
            },
        },
    }
    adapter = TwitterAdapter()
    page = adapter.parse_profile_contents(payload, profile_id="elonmusk")

    assert [item.external_id for item in page.items] == [
        "2083034836097192096",
        "2083287619064983711",
    ]
    pinned = page.items[0]
    assert pinned.media[0] == {
        "type": "video",
        "url": "https://video.twimg.com/high.mp4?tag=29",
    }
    assert pinned.media[1] == {
        "type": "cover",
        "url": "https://pbs.twimg.com/amplify_video_thumb/thumb.jpg",
    }
    legacy = page.items[1]
    assert legacy.media == [{"type": "photo", "url": "https://pbs.twimg.com/media/legacy.jpg"}]

    profile = adapter.parse_profile(payload, external_id="elonmusk")
    assert profile.display_name == "Elon Musk"
    assert profile.handle == "elonmusk"
    assert profile.avatar_url == "https://pbs.twimg.com/profile_images/avatar_normal.jpg"


def test_x_content_detail_flat_shape_is_normalized():
    item = TwitterAdapter().parse_content_detail(
        _payload(
            {
                "tweet_id": "1808168603721650364",
                "text": "Detail tweet",
                "created_at": "Wed Jan 14 05:46:38 +0000 2026",
                "author": {"screen_name": "elonmusk", "name": "Elon Musk", "rest_id": "44196397"},
                "favorites": 4210,
                "retweets": 880,
                "replies": 192,
                "quotes": 64,
                "bookmarks": 88,
                "views": "312000",
            }
        ),
        fallback_external_id=None,
    )

    assert item.platform == "x"
    assert item.external_id == "1808168603721650364"
    assert item.content_type == "tweet"
    assert item.metrics.likes == 4210
    assert item.metrics.shares == 880
    assert item.metrics.comments == 192
    assert item.metrics.favorites == 88
    assert item.metrics.views == 312000
    assert item.canonical_url == "https://x.com/elonmusk/status/1808168603721650364"


def test_x_article_detail_prefers_article_title_body_and_cover():
    item = TwitterAdapter().parse_content_detail(
        _payload(
            {
                "id": "2083090241683128626",
                "text": "https://t.co/C3sEAMGsu1",
                "created_at": "Fri Jul 31 07:19:50 +0000 2026",
                "author": {
                    "screen_name": "AdrianPunk115",
                    "name": "Adrian Punk",
                },
                "article": {
                    "title": "最近大火的 AI 岗位，FDE 到底是干嘛的？普通人怎么上车？",
                    "preview_text": "这两年，AI 圈最抢手的人……",
                    "full_text": "这两年，AI 圈最抢手的人。\n\n这是完整长文。",
                    "cover_media": "https://pbs.twimg.com/media/article-cover.jpg",
                },
            }
        ),
        fallback_external_id=None,
    )

    assert item.external_id == "2083090241683128626"
    assert item.content_type == "article"
    assert item.title == "最近大火的 AI 岗位，FDE 到底是干嘛的？普通人怎么上车？"
    assert item.body_text == "这两年，AI 圈最抢手的人。\n\n这是完整长文。"
    assert item.media == [
        {"type": "cover", "url": "https://pbs.twimg.com/media/article-cover.jpg"}
    ]
    assert item.canonical_url == (
        "https://x.com/AdrianPunk115/status/2083090241683128626"
    )


def test_x_content_detail_real_response_contract():
    import json
    from pathlib import Path

    payload = json.loads(
        (
            Path(__file__).parent / "fixtures" / "tikhub" / "x_tweet_detail_representative.json"
        ).read_text(encoding="utf-8")
    )
    item = TwitterAdapter().parse_content_detail(payload, fallback_external_id=None)

    assert item.platform == "x"
    assert item.external_id == "1808168603721650364"
    assert item.content_type == "tweet"
    assert item.body_text == (
        "The New York Times is attacking *your* freedom of speech! https://t.co/TRIa13TWdY"
    )
    assert item.metrics.likes == 285015
    assert item.metrics.comments == 26965
    assert item.metrics.shares == 52791
    assert item.metrics.favorites == 6666
    assert item.metrics.views == 53720034
    assert item.canonical_url == "https://x.com/elonmusk/status/1808168603721650364"
    assert item.media == [
        {"type": "photo", "url": "https://pbs.twimg.com/media/GRfnwy5X0AAwIK2.jpg"}
    ]
    assert item.original_content == {
        "format": "x",
        "blocks": [
            {
                "type": "paragraph",
                "runs": [
                    {
                        "text": "The New York Times is attacking *your* freedom of speech! ",
                        "style": "text",
                    },
                    {"text": "[图片]", "style": "media_placeholder"},
                ],
            },
            {
                "type": "image",
                "url": "https://pbs.twimg.com/media/GRfnwy5X0AAwIK2.jpg",
            },
        ],
    }
    assert item.published_at == datetime(2024, 7, 2, 15, 59, 23, tzinfo=timezone.utc)
    assert item.author["handle"] == "elonmusk"
    assert item.provider_metadata["quotes"] == 3934


def test_x_content_detail_reconstructs_entities_and_quote():
    item = TwitterAdapter().parse_content_detail(
        _payload(
            {
                "tweet_id": "1900000000000000001",
                "full_text": (
                    "Read @elonmusk and #freedom today https://t.co/linkAbc1 "
                    "https://t.co/linkAbc2"
                ),
                "created_at": "Wed Jan 14 05:46:38 +0000 2026",
                "author": {
                    "screen_name": "observer",
                    "name": "Observer",
                    "rest_id": "101",
                },
                "entities": {
                    "urls": [
                        {
                            "url": "https://t.co/linkAbc1",
                            "expanded_url": "https://example.com/article",
                        }
                    ],
                    "media": [
                        {
                            "url": "https://t.co/linkAbc2",
                            "media_url_https": "https://pbs.twimg.com/media/photo.jpg",
                            "type": "photo",
                        }
                    ],
                    "user_mentions": [{"screen_name": "elonmusk"}],
                    "hashtags": [{"text": "freedom"}],
                },
                "quoted_tweet": {
                    "tweet_id": "1800000000000000002",
                    "full_text": "Quoted original text",
                    "author": {
                        "screen_name": "quoteduser",
                        "name": "Quoted User",
                        "rest_id": "202",
                    },
                    "media": {
                        "photo": [
                            {
                                "media_url_https": "https://pbs.twimg.com/media/q.jpg",
                                "id": "q1",
                            }
                        ]
                    },
                },
            }
        ),
        fallback_external_id=None,
    )

    assert item.original_content is not None
    paragraph = item.original_content["blocks"][0]
    assert paragraph["type"] == "paragraph"
    assert paragraph["runs"] == [
        {"text": "Read ", "style": "text"},
        {"text": "@elonmusk", "style": "mention"},
        {"text": " and ", "style": "text"},
        {"text": "#freedom", "style": "hashtag"},
        {"text": " today ", "style": "text"},
        {
            "text": "https://example.com/article",
            "style": "url",
            "url": "https://example.com/article",
        },
        {"text": " ", "style": "text"},
        {"text": "[图片]", "style": "media_placeholder"},
    ]
    assert item.original_content["blocks"][1] == {
        "type": "image",
        "url": "https://pbs.twimg.com/media/photo.jpg",
    }
    quote = item.original_content["blocks"][2]
    assert quote["type"] == "quote"
    assert quote["text"] == "Quoted original text"
    assert quote["author"] == {"display_name": "Quoted User", "handle": "quoteduser"}
    assert quote["url"] == "https://x.com/quoteduser/status/1800000000000000002"
    assert quote["media_url"] == "https://pbs.twimg.com/media/q.jpg"


def test_x_comments_timeline_shape_is_normalized():
    page = TwitterAdapter().parse_comments(
        _payload(
            {
                "next_cursor": "NEXT",
                "timeline": [
                    {
                        "tweet_id": "2011314000000000001",
                        "text": "Representative reply text",
                        "created_at": "Wed Jan 14 06:00:00 +0000 2026",
                        "in_reply_to_status_id": "2011313989737959548",
                        "author": {
                            "screen_name": "replyuser",
                            "name": "Reply User",
                            "rest_id": "100200300",
                        },
                        "favorites": 5,
                    }
                ],
            }
        )
    )

    assert page.has_more is True
    assert page.cursor == "NEXT"
    assert len(page.items) == 1
    comment = page.items[0]
    assert comment.external_id == "2011314000000000001"
    assert comment.parent_external_id == "2011313989737959548"
    assert comment.body_text == "Representative reply text"
    assert comment.like_count == 5
    assert comment.author["handle"] == "replyuser"
    assert comment.published_at == datetime(2026, 1, 14, 6, 0, tzinfo=timezone.utc)


def test_x_comments_real_response_thread_contract():
    import json
    from pathlib import Path

    payload = json.loads(
        (
            Path(__file__).parent / "fixtures" / "tikhub" / "x_comments_representative.json"
        ).read_text(encoding="utf-8")
    )
    page = TwitterAdapter().parse_comments(payload)

    assert page.has_more is True
    assert page.cursor == "DAAKCgABHOmq4dM__pULAAIAAAGoRW1QQzZ3QUFBZlEvZ0dKTjB2R3Av"
    assert [item.external_id for item in page.items] == [
        "1835124568618680425",
        "1835124564308822038",
    ]
    first = page.items[0]
    assert first.body_text == "@elonmusk By buying Twitter, Elon saved freedom of speech."
    assert first.like_count == 612
    assert first.parent_external_id == "1835124037934367098"
    assert first.author["handle"] == "BoLoudon"
    assert first.author["display_name"] == "Bo Loudon"
    assert first.published_at == datetime(2024, 9, 15, 1, 12, 46, tzinfo=timezone.utc)


def test_x_profile_missing_name_raises():
    try:
        TwitterAdapter().parse_profile(_payload({"profile": "elonmusk"}), external_id="elonmusk")
    except ValueError as exc:
        assert "missing name" in str(exc)
    else:
        raise AssertionError("expected ValueError for missing name")
