import importlib
from uuid import UUID

from sqlalchemy import select

from app.db.models import ScoringPolicy, Workspace

migration = importlib.import_module(
    "app.db.migrations.versions.20260801_0020_backfill_x_scoring_policies"
)


def _policy_config(policy: ScoringPolicy) -> dict:
    return {
        "core_metric_formula": policy.core_metric_formula,
        "tier_thresholds": policy.tier_thresholds,
        "grade_thresholds": policy.grade_thresholds,
        "minimum_age_minutes": policy.minimum_age_minutes,
        "minimum_baseline_count": policy.minimum_baseline_count,
    }


def _workspace(db, name: str) -> Workspace:
    workspace = Workspace(name=name, timezone="Australia/Melbourne")
    db.add(workspace)
    db.flush()
    return workspace


def _x_policy(
    workspace_id,
    *,
    version: int,
    active: bool,
    core_metric_formula: dict | None = None,
) -> ScoringPolicy:
    return ScoringPolicy(
        workspace_id=workspace_id,
        platform="x",
        version=version,
        core_metric_formula=core_metric_formula or {"legacy": version},
        tier_thresholds={"legacy": version},
        grade_thresholds={"legacy": version},
        minimum_age_minutes=15,
        minimum_baseline_count=2,
        active=active,
    )


def test_backfill_x_scoring_policy_migration_preserves_existing_active_policies(
    app, monkeypatch
):
    with app.state.database.session_factory() as db:
        missing = _workspace(db, "Missing X policy")
        inactive_only = _workspace(db, "Inactive X policy")
        existing_active = _workspace(db, "Existing active X policy")
        db.add(_x_policy(inactive_only.id, version=4, active=False))
        db.add(
            _x_policy(
                existing_active.id,
                version=7,
                active=True,
                core_metric_formula={"keep": "this policy"},
            )
        )
        db.commit()

    with app.state.database.engine.begin() as connection:
        monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
        migration.upgrade()
        migration.upgrade()

    with app.state.database.session_factory() as db:
        policies = db.scalars(
            select(ScoringPolicy)
            .where(ScoringPolicy.platform == "x")
            .order_by(ScoringPolicy.workspace_id, ScoringPolicy.version)
        ).all()

    by_workspace = {}
    for policy in policies:
        by_workspace.setdefault(policy.workspace_id, []).append(policy)

    missing_policy = by_workspace[missing.id]
    assert len(missing_policy) == 1
    assert missing_policy[0].version == 1
    assert missing_policy[0].active is True
    assert _policy_config(missing_policy[0]) == migration.DEFAULT_X_SCORING_POLICY

    inactive_policies = by_workspace[inactive_only.id]
    assert [(policy.version, policy.active) for policy in inactive_policies] == [
        (4, False),
        (5, True),
    ]

    existing_policies = by_workspace[existing_active.id]
    assert len(existing_policies) == 1
    assert existing_policies[0].version == 7
    assert existing_policies[0].active is True
    assert existing_policies[0].core_metric_formula == {"keep": "this policy"}

    migration.downgrade()
    with app.state.database.session_factory() as db:
        assert db.scalar(
            select(ScoringPolicy).where(
                ScoringPolicy.workspace_id == missing.id,
                ScoringPolicy.platform == "x",
                ScoringPolicy.active.is_(True),
        )
        ) is not None


def test_x_scoring_policy_backfill_defaults_match_new_workspace_defaults(
    client, app, auth_headers
):
    response = client.post(
        "/api/v1/workspaces",
        headers=auth_headers,
        json={"name": "Current X defaults", "timezone": "Australia/Melbourne"},
    )
    assert response.status_code == 201
    workspace_id = UUID(response.json()["data"]["id"])

    with app.state.database.session_factory() as db:
        policy = db.scalar(
            select(ScoringPolicy).where(
                ScoringPolicy.workspace_id == workspace_id,
                ScoringPolicy.platform == "x",
                ScoringPolicy.active.is_(True),
            )
        )

    assert policy is not None
    assert _policy_config(policy) == migration.DEFAULT_X_SCORING_POLICY
