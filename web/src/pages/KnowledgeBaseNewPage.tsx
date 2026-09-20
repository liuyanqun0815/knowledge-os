import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { createKnowledgeBase } from "../api/knowledgeBases";
import { useKb } from "../app/KbContext";
import { ErrorBanner } from "../components/ErrorBanner";

const domain_types = [
  { value: "ecommerce_cs", label: "电商客服" },
  { value: "corporate_culture", label: "企业文化" },
  { value: "loan_finance", label: "贷款金融" },
  { value: "generic", label: "通用" },
] as const;

export function KnowledgeBaseNewPage() {
  const navigate = useNavigate();
  const { setKbId } = useKb();
  const [name, setName] = useState("");
  const [domainType, setDomainType] = useState<(typeof domain_types)[number]["value"]>("generic");
  const [description, setDescription] = useState("");
  const [graphEnabled, setGraphEnabled] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);

    try {
      const created = await createKnowledgeBase({
        name: name.trim(),
        domain_type: domainType,
        description: description.trim(),
        graph_enabled: graphEnabled,
      });
      setKbId(created.id);
      window.dispatchEvent(new CustomEvent("akos:kb-list-changed"));
      navigate(`/knowledge-bases/${created.id}`);
    } catch {
      setError("知识库创建失败，请检查输入后重试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="page-section form-page">
      <div className="page-header">
        <div>
          <h1>新建知识库</h1>
          <p>选择业务领域并填写知识库基本信息。</p>
        </div>
      </div>

      {error ? <ErrorBanner message={error} /> : null}
      <form className="form-card" onSubmit={handleSubmit}>
        <label htmlFor="knowledge-base-name">名称</label>
        <input
          id="knowledge-base-name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
          autoFocus
        />

        <label htmlFor="knowledge-base-domain">领域类型</label>
        <select
          id="knowledge-base-domain"
          value={domainType}
          onChange={(event) => setDomainType(event.target.value as typeof domainType)}
        >
          {domain_types.map((domainTypeOption) => (
            <option key={domainTypeOption.value} value={domainTypeOption.value}>
              {domainTypeOption.label}（{domainTypeOption.value}）
            </option>
          ))}
        </select>

        <label htmlFor="knowledge-base-description">描述</label>
        <textarea
          id="knowledge-base-description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
          rows={5}
        />

        <label className="form-checkbox-row" htmlFor="knowledge-base-graph">
          <input
            id="knowledge-base-graph"
            type="checkbox"
            checked={graphEnabled}
            onChange={(event) => setGraphEnabled(event.target.checked)}
          />
          <span>
            开启知识图谱
            <small className="form-hint">
              关闭后上传不再维护实体/关系，问答也不走图谱召回；适合图谱价值不大的知识库。
            </small>
          </span>
        </label>

        <div className="form-actions">
          <Link className="button button-secondary" to="/knowledge-bases">
            取消
          </Link>
          <button className="button button-primary" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "正在创建…" : "创建知识库"}
          </button>
        </div>
      </form>
    </section>
  );
}
