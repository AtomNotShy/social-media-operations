from fastapi import APIRouter

from app.api.v1.routes import (
    ai_settings,
    analysis,
    assets,
    automation,
    comments,
    content_packages,
    content_projects,
    dashboard,
    discovery,
    experiments,
    generation,
    health,
    identity,
    inspirations,
    jobs,
    members,
    operations,
    owned_channels,
    patterns,
    publishing,
    scoring,
    scripts,
    search,
    topics,
    tracked_profiles,
    videos,
)

router = APIRouter()
router.include_router(ai_settings.router)
router.include_router(analysis.router)
router.include_router(automation.router)
router.include_router(assets.router)
router.include_router(comments.router)
router.include_router(content_packages.router)
router.include_router(content_projects.router)
router.include_router(dashboard.router)
router.include_router(discovery.router)
router.include_router(experiments.router)
router.include_router(generation.router)
router.include_router(health.router)
router.include_router(identity.router)
router.include_router(tracked_profiles.router)
router.include_router(inspirations.router)
router.include_router(jobs.router)
router.include_router(members.router)
router.include_router(operations.router)
router.include_router(owned_channels.router)
router.include_router(patterns.router)
router.include_router(publishing.router)
router.include_router(scoring.router)
router.include_router(search.router)
router.include_router(scripts.router)
router.include_router(topics.router)
router.include_router(videos.router)
