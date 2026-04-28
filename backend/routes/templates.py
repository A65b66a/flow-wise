from fastapi import APIRouter, HTTPException
from backend.models.schemas import BaseResponse
from backend.utils.template_loader import get_all_templates, get_template_by_id

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=BaseResponse[dict])
async def list_templates():
    templates = get_all_templates()
    return BaseResponse(
        success=True,
        message="Templates retrieved",
        data={
            "count": len(templates),
            "templates": [
                {
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"],
                    "use_cases": t.get("use_cases", []),
                    "scale": t.get("scale", []),
                }
                for t in templates
            ],
        },
    )


@router.get("/{template_id}", response_model=BaseResponse[dict])
async def get_template(template_id: str):
    template = get_template_by_id(template_id)
    if not template:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return BaseResponse(success=True, message="Template retrieved", data=template)
