from fastapi import FastAPI

from app.api.v1 import dashboard


def test_dashboard_router_mounts_without_app_lifespan():
    app = FastAPI()
    app.include_router(dashboard.router, prefix="/api/v1")

    paths = {route.path for route in app.routes}

    assert "/api/v1/dashboard/summary" in paths
