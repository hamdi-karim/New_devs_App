from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import authenticate_request as get_current_user
from app.models.auth import AuthenticatedUser
from app.services.cache import get_revenue_summary
from app.services.revenue_rules import PropertyNotFound, RevenueUnavailable

router = APIRouter()


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    tenant_id = getattr(current_user, "tenant_id", None)
    if not tenant_id:
        raise HTTPException(status_code=403, detail="User is not assigned to a tenant")

    try:
        revenue_data = await get_revenue_summary(property_id, tenant_id)
    except PropertyNotFound:
        raise HTTPException(status_code=404, detail="Property not found")
    except RevenueUnavailable:
        raise HTTPException(
            status_code=503, detail="Revenue data is temporarily unavailable"
        )

    return {
        "property_id": revenue_data["property_id"],
        # The service returns an exact, already-rounded decimal string;
        # converting to a JSON number happens only here at the edge.
        "total_revenue": float(revenue_data["total"]),
        "currency": revenue_data["currency"],
        "reservations_count": revenue_data["count"],
    }
