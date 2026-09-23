from __future__ import annotations

from akos.application.ingest.extraction_spec import LlmExtractionSpec
from akos.application.ingest.rule_extractor import RuleExtractor
from akos.domains.ecommerce_cs.formatter import format_ecommerce_claim
from akos.domains.ecommerce_cs.rules import ECOMMERCE_RULES
from akos.domains.ecommerce_cs.seed import ENTITY_SEEDS, PREDICATES, register_ecommerce_cs
from akos.domain.models.knowledge import Claim
from akos.domain.ports.ontology import OntologyPort


class EcommerceCsDomain:
    name = "ecommerce_cs"

    def register_ontology(self, ontology: OntologyPort) -> None:
        register_ecommerce_cs(ontology)

    def get_extractor(self) -> RuleExtractor:
        return RuleExtractor(ECOMMERCE_RULES)

    def get_aliases(self) -> list[str]:
        from akos.domains.ecommerce_cs.seed import ALIASES

        # 问句归一化扫表面形式；规范名由本体实体覆盖，此处不重复列入
        return list(ALIASES.keys())

    def format_claim(self, claim: Claim) -> str:
        return format_ecommerce_claim(claim)

    def low_confidence_message(self) -> str:
        return "依据不足，无法根据现有知识库内容回答该问题。"

    def high_risk_predicates(self) -> list[str]:
        return ["运费承担方", "退货时限_天", "排除"]

    def llm_extraction_spec(self) -> LlmExtractionSpec:
        predicates = sorted({predicate for _, predicate, _ in PREDICATES})
        entity_types = sorted(
            set(ENTITY_SEEDS.values())
            | {subject for subject, _, _ in PREDICATES}
            | {obj for _, _, obj in PREDICATES}
        )
        return LlmExtractionSpec(
            allowed_predicates=predicates,
            entity_types=entity_types,
            few_shot_hints=[
                "正例：七天无理由适用类目为非定制商品 → predicate=适用类目，object=非定制商品",
                "正例：定制商品不适用七天无理由退货 → subject=七天无理由，predicate=排除，object=定制商品",
                "正例：下列商品不适用七日无理由退货：定作商品、鲜活易腐 → 多条排除，object 各取一类",
                "正例：自收到商品之日起七日内可无理由退货 → predicate=退货时限_天，object=7",
                "正例：商品退回所产生的运费依法由消费者承担 → predicate=运费承担方，object=消费者",
                "正例：退回的商品应当完好 → predicate=需包装完好，object=完好",
                "正例：本商品支持七天无理由退货 → predicate=是否支持无理由退货，object=支持",
                "反例：subject=运费承担方 / 排除（谓词不可作 subject）",
                "反例：把整段政策标题当作 object，而不拆具体类目",
            ],
        )
