from __future__ import annotations

from domains.base import DomainPort
from domains.corporate_culture.domain import CorporateCultureDomain
from domains.ecommerce_cs.domain import EcommerceCsDomain
from domains.generic.domain import GenericDomain
from domains.loan_finance.domain import LoanFinanceDomain
from knowledge.errors import DomainError

DOMAIN_REGISTRY: dict[str, type[DomainPort]] = {
    "ecommerce_cs": EcommerceCsDomain,
    "corporate_culture": CorporateCultureDomain,
    "loan_finance": LoanFinanceDomain,
    "generic": GenericDomain,
}


def load_domain(name: str) -> DomainPort:
    domain_cls = DOMAIN_REGISTRY.get(name)
    if domain_cls is None:
        raise DomainError(f"unknown domain_type: {name}")
    return domain_cls()
