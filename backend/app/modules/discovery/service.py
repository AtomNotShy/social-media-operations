from datetime import datetime

from app.providers.social.base import ContentMetrics, NormalizedContent


def serialize_content(item: NormalizedContent) -> dict:
    return {
        "platform": item.platform,
        "external_id": item.external_id,
        "canonical_url": item.canonical_url,
        "content_type": item.content_type,
        "title": item.title,
        "body_text": item.body_text,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "duration_ms": item.duration_ms,
        "author": item.author,
        "metrics": {
            "views": item.metrics.views,
            "likes": item.metrics.likes,
            "comments": item.metrics.comments,
            "favorites": item.metrics.favorites,
            "shares": item.metrics.shares,
            "downloads": item.metrics.downloads,
        },
        "media": item.media,
    }


def deserialize_content(summary: dict) -> NormalizedContent:
    published_at = summary.get("published_at")
    metrics = summary.get("metrics") if isinstance(summary.get("metrics"), dict) else {}
    return NormalizedContent(
        platform=str(summary["platform"]),
        external_id=str(summary["external_id"]),
        canonical_url=str(summary["canonical_url"]),
        content_type=str(summary["content_type"]),
        title=summary.get("title"),
        body_text=summary.get("body_text"),
        published_at=datetime.fromisoformat(published_at) if published_at else None,
        duration_ms=summary.get("duration_ms"),
        author=summary.get("author") or {},
        metrics=ContentMetrics(
            views=metrics.get("views"),
            likes=metrics.get("likes"),
            comments=metrics.get("comments"),
            favorites=metrics.get("favorites"),
            shares=metrics.get("shares"),
            downloads=metrics.get("downloads"),
        ),
        media=summary.get("media") or [],
    )
