from crm.schemas.base import CamelModel
from crm.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadListResponse,
)
from crm.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerResponse,
    CustomerDetailResponse,
    ContactCreate,
    ContactResponse,
    CustomerListResponse,
)
from crm.schemas.opportunity import (
    OpportunityCreate,
    OpportunityUpdate,
    OpportunityResponse,
    OpportunityListResponse,
)
from crm.schemas.activity import (
    ActivityCreate,
    ActivityResponse,
    ActivityListResponse,
)

__all__ = [
    "CamelModel",
    # Lead
    "LeadCreate",
    "LeadUpdate",
    "LeadResponse",
    "LeadListResponse",
    # Customer
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerResponse",
    "CustomerDetailResponse",
    "ContactCreate",
    "ContactResponse",
    "CustomerListResponse",
    # Opportunity
    "OpportunityCreate",
    "OpportunityUpdate",
    "OpportunityResponse",
    "OpportunityListResponse",
    # Activity
    "ActivityCreate",
    "ActivityResponse",
    "ActivityListResponse",
]
