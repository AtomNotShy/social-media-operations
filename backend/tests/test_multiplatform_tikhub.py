import asyncio

import httpx
import pytest

from app.jobs.worker import process_one
from app.providers.social.tikhub.bilibili import BilibiliAdapter
from app.providers.social.tikhub.client import TikHubHttpClient
from app.providers.social.tikhub.douyin import DouyinAppV3Adapter

DOUYIN_DETAIL = {
    "code": 200,
    "request_id": "douyin-contract",
    "data": {
        "aweme_detail": {
            "aweme_id": "7534641277405531446",
            "desc": "Representative Douyin video",
            "create_time": 1754295391,
            "duration": 29400,
            "author": {
                "sec_uid": "sec-user-contract",
                "nickname": "Douyin creator",
                "unique_id": "creator-handle",
            },
            "statistics": {
                "play_count": 1000,
                "digg_count": 100,
                "comment_count": 20,
                "collect_count": 30,
                "share_count": 10,
                "download_count": 2,
            },
            "video": {
                "cover": {"url_list": ["https://media.example.test/cover.jpg"]},
                "play_addr": {"url_list": ["https://media.example.test/video.mp4"]},
            },
        }
    },
}

BILIBILI_DETAIL = {
    "code": 200,
    "request_id": "bilibili-contract",
    "data": {
        "View": {
            "bvid": "BV1S5uKzzE4r",
            "aid": 123456,
            "title": "Representative Bilibili video",
            "desc": "Contract fixture",
            "pubdate": 1754295391,
            "duration": 30,
            "pic": "https://media.example.test/bili-cover.jpg",
            "owner": {"mid": 203680252, "name": "Bilibili creator"},
            "stat": {
                "view": 2000,
                "like": 200,
                "reply": 40,
                "favorite": 50,
                "share": 20,
            },
        }
    },
}

TIKTOK_DETAIL = {
    "code": 200,
    "request_id": "tiktok-contract",
    "data": {
        "aweme_detail": {
            "aweme_id": "7350810998023949599",
            "desc": "im so sick of being tired im so tired of being sick",
            "create_time": 1711494099,
            "author": {
                "uid": "6617578271134646277",
                "sec_uid": (
                    "MS4wLjABAAAAdsKhQYdpLrOx5hrYCM3O2FQK3Xhnncm0ZHzGROFGk43iPI"
                    "EPqxyEOK_YWom9LoKn"
                ),
                "unique_id": "jennmelon",
                "nickname": "Jenn Melon",
                "follower_count": 0,
                "following_count": 0,
            },
            "statistics": {
                "play_count": 12187417,
                "digg_count": 2004082,
                "comment_count": 7829,
                "collect_count": 211565,
                "share_count": 275192,
                "download_count": 20349,
            },
            "video": {
                "duration": 5900,
                "cover": {"url_list": ["https://p19-common-sign.tiktokcdn-us.com/cover.jpg"]},
                "play_addr": {
                    "url_list": ["https://v16m.tiktokcdn-us.com/video.mp4"],
                },
            },
        }
    },
}

X_TWEET_DETAIL = {
    "code": 200,
    "request_id": "x-contract",
    "data": {
        "likes": 285015,
        "created_at": "Tue Jul 02 15:59:23 +0000 2024",
        "text": "The New York Times is attacking *your* freedom of speech!",
        "retweets": 52791,
        "bookmarks": 6666,
        "quotes": 3934,
        "replies": 26965,
        "views": "53720034",
        "conversation_id": "1808168603721650364",
        "entities": {
            "media": [
                {
                    "media_url_https": "https://pbs.twimg.com/media/GRfnwy5X0AAwIK2.jpg",
                    "id_str": "1808168600894689280",
                    "type": "photo",
                    "url": "https://t.co/TRIa13TWdY",
                }
            ]
        },
        "author": {
            "rest_id": "44196397",
            "name": "Elon Musk",
            "screen_name": "elonmusk",
            "sub_count": 241091952,
            "blue_verified": True,
        },
        "media": {
            "photo": [
                {
                    "media_url_https": "https://pbs.twimg.com/media/GRfnwy5X0AAwIK2.jpg",
                    "id": "1808168600894689280",
                }
            ]
        },
        "id": "1808168603721650364",
    },
}


def _headers(auth_headers, workspace):
    return {**auth_headers, "X-Workspace-Id": workspace["id"]}


def test_douyin_demo_shape_is_normalized():
    item = DouyinAppV3Adapter().parse_content_detail(DOUYIN_DETAIL)

    assert item.platform == "douyin"
    assert item.external_id == "7534641277405531446"
    assert item.metrics.views == 1000
    assert item.metrics.downloads == 2
    assert {media["type"] for media in item.media} == {"cover", "video"}


def test_bilibili_contract_shape_is_normalized():
    item = BilibiliAdapter().parse_content_detail(BILIBILI_DETAIL)

    assert item.platform == "bilibili"
    assert item.external_id == "BV1S5uKzzE4r"
    assert item.duration_ms == 30_000
    assert item.metrics.favorites == 50


@pytest.mark.parametrize(
    ("url", "endpoint_path", "payload", "expected_platform", "expected_external_id"),
    [
        (
            "https://www.douyin.com/video/7534641277405531446",
            "/api/v1/douyin/app/v3/fetch_one_video_v3",
            DOUYIN_DETAIL,
            "douyin",
            "7534641277405531446",
        ),
        (
            "https://www.bilibili.com/video/BV1S5uKzzE4r",
            "/api/v1/bilibili/web/fetch_one_video_v3",
            BILIBILI_DETAIL,
            "bilibili",
            "BV1S5uKzzE4r",
        ),
        (
            "https://x.com/elonmusk/status/1808168603721650364",
            "/api/v1/twitter/web/fetch_tweet_detail",
            X_TWEET_DETAIL,
            "x",
            "1808168603721650364",
        ),
        (
            "https://www.tiktok.com/@jennmelon/video/7350810998023949599",
            "/api/v1/tiktok/app/v3/fetch_one_video",
            TIKTOK_DETAIL,
            "tiktok",
            "7350810998023949599",
        ),
    ],
)
def test_multiplatform_url_import_uses_registered_adapter(
    client,
    app,
    auth_headers,
    workspace,
    url,
    endpoint_path,
    payload,
    expected_platform,
    expected_external_id,
):
    headers = _headers(auth_headers, workspace)
    accepted = client.post(
        "/api/v1/inspirations/import-url",
        headers=headers,
        json={"url": url, "hydrate": "detail", "analyze": False},
    )
    assert accepted.status_code == 202
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload)

    async def run_job():
        async with httpx.AsyncClient(
            base_url="https://api.example.test",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            provider_client = TikHubHttpClient(
                base_url="https://api.example.test",
                api_key="test",
                client=http_client,
            )
            with app.state.database.session_factory() as db:
                return await process_one(
                    db,
                    client=provider_client,
                    worker_id=f"{expected_platform}-worker",
                )

    assert asyncio.run(run_job()) is True
    assert [request.url.path for request in requests] == [endpoint_path]
    listing = client.get(
        f"/api/v1/inspirations?platform={expected_platform}",
        headers=headers,
    )
    content = listing.json()["data"][0]["content"]
    assert content["platform"] == expected_platform
    assert content["external_id"] == expected_external_id
    if expected_platform == "x":
        assert content["content_type"] == "tweet"
        assert content["canonical_url"] == "https://x.com/elonmusk/status/1808168603721650364"
        assert content["media_manifest"][0] == {
            "type": "photo",
            "url": "https://pbs.twimg.com/media/GRfnwy5X0AAwIK2.jpg",
        }
    if expected_platform == "tiktok":
        assert content["content_type"] == "video"
        assert content["canonical_url"] == "https://www.tiktok.com/video/7350810998023949599"
