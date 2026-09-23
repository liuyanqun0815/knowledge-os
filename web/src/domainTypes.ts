/** 知识库领域选项：中文标签 + 枚举值（与 akos.domains.registry 对齐）。 */
export const DOMAIN_TYPE_OPTIONS = [
  { value: "ecommerce_cs", label: "电商客服" },
  { value: "corporate_culture", label: "企业文化" },
  { value: "loan_finance", label: "贷款金融" },
  { value: "generic", label: "通用" },
] as const;

export type DomainTypeValue = (typeof DOMAIN_TYPE_OPTIONS)[number]["value"];

const LABEL_BY_VALUE: Record<string, string> = Object.fromEntries(
  DOMAIN_TYPE_OPTIONS.map((item) => [item.value, item.label]),
);

/** 列表/详情展示用中文名；未知枚举原样返回。 */
export function domainTypeLabel(domainType: string): string {
  return LABEL_BY_VALUE[domainType] ?? domainType;
}
