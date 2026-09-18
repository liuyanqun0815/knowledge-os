from __future__ import annotations

from akos.domain.ports.domain import DomainPort
from akos.domains.corporate_culture.domain import CorporateCultureDomain
from akos.domains.ecommerce_cs.domain import EcommerceCsDomain
from akos.domains.generic.domain import GenericDomain
from akos.domains.loan_finance.domain import LoanFinanceDomain
from akos.domain.errors import DomainError

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
