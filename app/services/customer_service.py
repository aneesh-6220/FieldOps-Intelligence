"""Customer creation and editing."""

from sqlalchemy.orm import Session

from app.database.models import Customer
from app.database.repositories import CustomerRepository
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.activity_service import record_activity
from app.utils.validation import DomainError


class CustomerService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = CustomerRepository(session)

    def create(self, data: CustomerCreate) -> Customer:
        customer = self.repository.add(Customer(**data.model_dump()))
        record_activity(
            self.session,
            customer.business_id,
            "customer",
            customer.id,
            "created",
            "Customer created",
        )
        return customer

    def update(self, customer_id: int, business_id: int, data: CustomerUpdate) -> Customer:
        if data.business_id != business_id:
            raise DomainError("Customer business cannot be changed.")
        customer = self.repository.require_for_business(customer_id, business_id)
        self.repository.update(customer, data.model_dump(exclude={"business_id"}))
        record_activity(
            self.session,
            business_id,
            "customer",
            customer.id,
            "updated",
            "Customer details updated",
        )
        return customer
