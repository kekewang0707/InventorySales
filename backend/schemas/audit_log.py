from datetime import datetime
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: int
    action: str
    old_values: Optional[Any] = None
    new_values: Optional[Any] = None
    operator: str
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogResponse]
