# Product Requirements Document: Medical Supply AI Assistant

| Field | Value |
| --- | --- |
| Organization | Queens Tech Bros (QTB) |
| Version | 1.1 |
| Status | Approved — Product Requirements Baseline |
| Owner | QTB product and engineering team |
| Last updated | 2026-11-02 |
| Approval | Approved for product requirements and MVP scope only. This does not approve unresolved business permissions, privacy/safety reviews, deployment readiness, implementation, or release decisions. |

## 1. Executive summary

Medical Supply AI Assistant is a portfolio-first software engineering demonstration for a family-owned medical-supply and pharmaceutical-distribution business. It will present a guest-facing AI experience that helps visitors find synthetic catalog products, understand customer-facing availability, prepare a quotation inquiry, obtain grounded company information, and optionally forward an inquiry to a human.

The demonstration is intentionally not an e-commerce or clinical-care system. It will use synthetic products, inventory, prices, customers, and operating data; it will not accept payments, create real orders, reserve inventory, or connect public submissions to real business operations. Any use of real-company branding requires permission.

## 2. Business context and problem statement

Medical-supply discovery often requires matching detailed product characteristics, packaging, quantity needs, and availability, while prospective customers may also have questions about shipping, returns, bulk ordering, or support. A conventional storefront alone does not demonstrate how an assistant can guide this process, preserve context, and produce an operationally useful request.

QTB needs a credible, safe, and inspectable demonstration of full-stack engineering, applied AI, LangGraph state orchestration, retrieval-augmented generation (RAG), database integration, automation, testing, and cloud engineering. The product must be useful as a demo without implying live commercial service or inventing business facts.

## 3. Goals and success criteria

### Goals

1. Demonstrate an end-to-end guest workflow from natural-language product need to durable synthetic quotation or support inquiry.
2. Make product matches explainable through structured attributes, indicative prices, availability status, and safe alternatives.
3. Ground business-information answers in a small, approved knowledge base and preserve appropriate medical-information boundaries.
4. Make persistence, integrations, failure handling, security controls, automated testing, and AI evaluation visible and credible to technical audiences.

### Success criteria

The MVP is successful when its critical workflows can be demonstrated reliably with synthetic data: product discovery; unambiguous-SKU quote changes; seven-day resumable guest sessions with five-request capacity; quote and support submissions; PostgreSQL persistence; and recoverable Google Sheets synchronization. Public release is quality-gated by section 13. The initial **proposed** aggregate AI-evaluation target is 90% across approximately 65 scenarios; this is not a measured result and requires refinement before release.

## 4. Stakeholders and personas

| Stakeholder/persona | Need | Product responsibility |
| --- | --- | --- |
| QTB sponsors and prospective employers/clients | Evidence of production-minded engineering | Demonstrate traceable requirements, robust workflows, safety, observability, and documentation. |
| Guest buyer (B2B or B2C) | Quickly identify suitable supplies and request a quote without an account | Offer guided discovery, clear product facts, draft quotes, and confirmed submissions. |
| Business reviewer | Receive usable inquiries without exposing operations to the public demo | Receive separate synthetic quote/support records after PostgreSQL storage and controlled Sheets sync. |
| Human support representative | Identify requests needing follow-up | Receive an explicitly consented, contactable support inquiry; no ticket platform is implied. |
| QTB engineering team | Build and validate safely | Work from approved data, business rules, interfaces, tests, and evaluation criteria. |

## 5. Scope and primary journeys

### MVP inclusions

- A synthetic catalog targeting approximately 90 sellable SKUs (acceptable planning range: 75–100), across supplies, diagnostics, consumables, sanitation, and selected OTC products.
- Conversation-led discovery with embedded product cards, deterministic product constraints, semantic retrieval, and direct database price/inventory reads.
- Guest-only sessions, conversation memory with one active and up to four saved resumable requests (maximum five stored requests), and independently persistent quote drafts.
- Draft quotations, confirmed quotation inquiry submission, optional support forwarding, PostgreSQL persistence, and one-way Google Sheets demonstration synchronization.
- Approved company-information documents, RAG, safety controls, automated tests, and an initial evaluation suite targeting approximately 65 scenarios.

### Primary user journeys

1. **Find and quote:** A guest sees the demo/privacy disclosure before entering a quote or support submission, describes a need, and receives useful matches when possible or only material clarifying questions. The guest selects an unambiguous SKU, adjusts quantity through chat or UI, reviews a draft, supplies first/last name plus email or phone, and explicitly confirms submission. The user sees a request number after PostgreSQL persistence.
2. **Change context:** A guest moves among topics. The system retains one active conversational request plus up to four saved resumable requests (maximum five), evicts the least-recently-used inactive request when capacity is reached, retains conversation history separately, and cannot silently add, remove, or alter the independently persistent draft quote.
3. **Availability exception:** A requested product or quantity is unavailable. The assistant reports a status rather than exact stock, proposes up to three validated available alternatives with meaningful differences, and still allows an inquiry for the original item without promising fulfillment.
4. **Business-information question:** A guest asks an approved company/policy question. The assistant retrieves approved documents and answers only from grounded information; where information is unavailable, it avoids fabrication and offers human support when appropriate.
5. **Human support:** A guest requests or is offered human help, opts in, provides contact information and an inquiry description, reviews, and explicitly submits. The record is stored and later synchronized to a separate Sheets tab.

## 6. Functional requirements

| ID | Requirement | Acceptance criteria |
| --- | --- | --- |
| BR-001 | Operate as a hybrid B2B/B2C, guest-only demonstration; label synthetic data/demo functionality; use branding only with permission; prohibit commercial ordering and payment. | Guest access requires no registration; before a quote/support submission, the UI clearly says this is a demonstration, requests fictional data, asks users not to enter medical or sensitive personal information, and says submissions are not forwarded to business operations; no payment/order action is available. |
| BR-002 | Maintain structured PostgreSQL catalog data for approximately 75–100 synthetic SKUs, target 90, including category, variant, specifications, price, packaging, and availability. | Catalog records contain required fields; prices are labeled indicative and subject to human confirmation. |
| BR-003 | Provide a representative SKU image, licensed/permitted/generated as appropriate, plus fallback; persist a URL or object reference rather than binary image data in PostgreSQL. | Every SKU resolves to an image or fallback; database schema stores only reference metadata. |
| FR-001 | Render product cards within the conversation, including image, name, variant, package size, indicative price, availability, and Add to Quote action. | Each returned product result exposes these fields, or an explicit image fallback when its image is unavailable; Add to Quote routes through SKU validation; no storefront is required. |
| FR-002 | Manage flexible request state: one active conversational request plus up to four additional saved, resumable requests, for a maximum of five stored requests; preserve each saved request's filters, selected SKU, requested quantity, relevant context, and unanswered clarification; support natural-language resumption and clickable saved-topic chips; evict the least-recently-used inactive request at capacity; retain conversation history separately from a persistent draft quote. | State-transition tests cover topic creation, switching, natural-language and chip-based resumption, and least-recently-used inactive-request eviction at capacity; at every transition the draft's SKU lines and quantities are unchanged unless the guest explicitly mutates the draft. Detailed transition diagrams are specified in Document 02. |
| FR-003 | Support one active persistent draft quote per guest session with multiple SKU lines and add/remove/quantity changes through natural language and UI; collect first/last name and valid email or phone; require review and confirmation. | For a resolved SKU, add, remove, and quantity changes update only the named line and persist across conversation switches; submission is blocked until contact and explicit confirmation are valid. |
| FR-004 | Persist secure opaque guest sessions; restore chat, the active request, up to four saved requests and their associated conversational context, and the active draft in the same browser; expire inactive sessions after seven days with activity renewal; use LangGraph checkpoints and PostgreSQL authoritative draft tables. | Browser refresh and same-browser restoration restore the active request, up to four saved requests, associated context, and the draft within the rolling seven-day activity window; an expired session cannot resume protected state; quote drafts remain authoritative in PostgreSQL; submissions follow a separate retention policy. |
| FR-005 | After durable quote submission, show a unique request number and read-only confirmation, clear the current draft, keep the chat and session usable, support later independent submissions, and require a new inquiry for post-submission changes. | Confirmation is produced only after PostgreSQL persistence; the submitted request is immutable; the successful submission clears only the current draft and does not end chat; contact reuse requires confirmation. |
| FR-006 | Use PostgreSQL-first, one-way Google Sheets synchronization with a transactionally created durable synchronization record, stable request identifier, retries, duplicate protection, and reconciliation for uncertain writes. | Customer confirmation depends on PostgreSQL only; each Sheets attempt uses the stable request identifier; automatic retries do not blindly create duplicate rows; failed/ambiguous outcomes remain observable, traceable, and recoverable through reconciliation. |
| FR-007 | Maintain structured basic company facts and about six approved knowledge documents for overview, shipping, returns, bulk ordering, product inquiries, and support; use embeddings and pgvector RAG. | Answers rely on approved retrieved content or state uncertainty; unsupported policy/product claims are not emitted. |
| FR-008 | Discover products through keyword/attribute search plus semantic retrieval; embed descriptions and meaningful attributes; apply deterministic filters; read price/inventory directly from PostgreSQL. | SKU-specific tests show a requested exact SKU is selected when present; constraint tests show deterministic filters override semantic similarity where required; displayed price/availability fields originate from database records. |
| FR-009 | Hold numeric synthetic stock for every SKU while showing status only; check requested quantities; include predefined low/out-of-stock examples; do not reserve/decrement stock for quotes. | Quantity-specific tests distinguish a request at or below available synthetic stock from one above it; customer output shows categorical availability rather than exact count; quote submission does not mutate stock. |
| FR-010 | Suggest up to three appropriate available alternatives for unavailable product/quantity, validate attributes and stock, explain relevant differences, and avoid unsupported medical/pharmaceutical substitutions. | Every suggested alternative is validated as available for the requested quantity, identifies at least one relevant difference, and is capped at three; the original item remains inquiry-eligible without fulfillment promise. |
| FR-011 | Return useful matches promptly when safe; ask clarification when material information is missing; retain preferences; require an unambiguous SKU before quote addition. | Ambiguous requests produce clarification; no line item is created without a resolved SKU. |
| FR-012 | Recognize human-assistance needs; offer optional forwarding with accept/decline/cancel; then collect name, contact, description, and final confirmation; persist and sync to a separate Sheets tab. | Declining or cancelling creates no support record; no support inquiry is sent absent acceptance and confirmation; records are separate from quote records. |
| FR-013 | Provide only verified factual OTC label information (ingredients, formulation, packaging, factual warnings); refuse/redirection for personalized advice, diagnosis, treatment, dosage, and clinical substitutions. | Safety evaluations include requests for diagnosis, treatment, dosage, and clinical substitutions; each rejects/redirection response avoids personalized advice and invented certifications/safety claims. |
| FR-014 | Protect public demo with validation, rate limits, per-session/global AI caps, cost safeguards, opaque sessions, server-side credentials, restricted tools, injection resistance, privacy protections, duplicate prevention, and accessible failure handling. | Security review/tests validate controls; duplicate-submission tests show repeated confirmation cannot create more than one immutable submission for the same protected submission action; configuration values and final thresholds are documented before release. |
| FR-015 | Provide unit, backend/API integration, and approximately 65 reproducible AI-evaluation scenarios spanning retrieval, inventory, state, quotes, RAG, support, failures, and safety. | Test/evaluation definitions and results are recorded; results are not claimed before execution. |
| FR-016 | Permit public synthetic-demo quote/support submissions with limits, duplicate protection, safe cleanup, separate Sheets tabs, private spreadsheet access, and no link to real operations. | Public flow minimizes fields to those required for the selected inquiry and does not claim it can guarantee synthetic input; it prevents exposure of Sheets access and any forwarding or trigger of real business operations. |

## 7. Nonfunctional requirements

**NFR-001 — Quality-gated public release.** Before public release, all critical workflows must pass: security/authorization controls, duplicate prevention, medical safety, end-to-end quote/support submission, PostgreSQL persistence, and Google Sheets synchronization. AI evaluation must be documented. The proposed 90% overall target is provisional; noncritical failures may be explicitly deferred only when core experience and safety are not compromised.

Additional quality expectations are implementation constraints, not asserted outcomes: responsive mobile layouts; keyboard-accessible controls and visible focus behavior; understandable loading, empty, and error states; an image fallback; an explicit unavailable-product state; and clear submission confirmation. Backend, model, and integration failures must present a safe, non-misleading recovery message without falsely confirming a submission or synchronization. Request, sync, error, and cost signals must be observable; deterministic business rules must be testable. Performance targets, availability objectives, supported browsers, rate-limit values, model/provider, and retention durations beyond the approved seven-day session inactivity rule remain open decisions.

## 8. Business rules

- Prices are indicative, synthetic catalog prices and require human confirmation; quotes do not approve price, reserve inventory, or create an order.
- Customer-facing availability is categorical, not an exact stock count, but the system validates requested quantities using numeric synthetic inventory.
- A quote may include only unambiguously identified SKUs. Submitted quotes and support records are immutable to guests; later changes create a new inquiry.
- A valid quote contact consists of first name, last name, and at least one valid email address or phone number. Previously provided contact information may be reused only after confirmation.
- A guest can maintain exactly one active quote draft per session. Conversation-topic state never silently removes it.
- The active conversational request and up to four saved resumable requests (maximum five stored requests) are separate from the persistent draft quote. Switching or resuming conversation state cannot mutate the draft unless the guest explicitly performs a draft action. When at capacity, the least-recently-used inactive request is evicted.
- A submitted quotation request is immutable and distinct from the draft from which it was submitted. Successful submission clears the current draft but leaves the chat usable for a new, independent draft.
- Customer success messaging confirms PostgreSQL persistence, not Google Sheets completion. It must not imply successful Sheets synchronization when synchronization is pending, failed, or uncertain.
- RAG may answer only from approved information. Medical-related output remains factual and non-personalized.
- Visitors may submit actual personal information despite instructions to use fictional data. The public demo must minimize collection, clearly discourage real medical and sensitive personal information, retain and clean up inquiries under a defined policy, and never route submissions into actual operations.

## 9. Explicit MVP exclusions

The MVP excludes customer accounts; checkout/payments; real orders, fulfillment, and tracking; inventory restocking; negotiated pricing; autonomous quote approval; full admin dashboard; full ticket-management platform; real pharmaceutical transactions; personalized clinical recommendations; and complex autonomous multi-agent systems.

## 10. Data and integration requirements

PostgreSQL is the private source of truth for structured catalog records, numeric stock, guest-session metadata, quote drafts and immutable submissions, support submissions, and synchronization tasks/results. Public visitors have no direct database access. pgvector stores or supports retrieval vectors for approved documents and relevant product descriptions/attributes. Product images are held externally or generated under acceptable rights and referenced by URL/object key. The data model must distinguish one active conversational request, up to four saved resumable requests (maximum five stored requests), the persistent draft, and immutable submitted records, and retain idempotency/deduplication data.

Google Sheets is a downstream, one-way demonstration integration. Quote and support records synchronize to distinct tabs in a dedicated synthetic spreadsheet. Sheets credentials stay server-side; the spreadsheet is private and access is restricted to authorized project personnel; visitors receive neither access nor spreadsheet identifiers that create access paths. PostgreSQL persistence and a durable synchronization record are created transactionally before customer confirmation. Every Sheets write uses the stable request identifier, and ambiguous write outcomes require reconciliation before they can be treated as synchronized. Specific retry algorithms and database contracts are deferred to later technical documents.

The approved knowledge corpus is expected to contain approximately six documents: company overview, shipping, returns, bulk ordering, product inquiries, and support. Exact source content, company facts, final public privacy/disclosure wording, inquiry retention and cleanup schedule, Google workspace ownership/access list, and image-license provenance must be supplied and approved before use. See future [technical architecture](05-technical-architecture.md), [database/API design](06-database-api-design.md), and [catalog/inventory](03-product-catalog-inventory.md) documentation.

## 11. AI safety and security requirements

LangGraph is the proposed orchestrator for explicit conversation/checkpoint state; LangChain is the proposed integration layer for models, tools, structured outputs, and retrieval. Tool access must be least-privilege: AI output cannot directly authorize payments, inventory changes, submitted-record edits, private Sheets access, or unsupervised policy creation. Server-side validation must treat model output as untrusted.

The assistant must defend against prompt injection by separating instructions, retrieved content, and untrusted input; constrain tools and structured outputs; and ground answers in approved sources. Before a public submission, it must clearly disclose the demonstration/synthetic-data boundary, ask visitors to use fictional data, state that submissions do not reach real business operations, and tell visitors not to enter real medical or sensitive personal information. It must minimize collection to the fields required for the chosen inquiry, validate and limit inputs, rate-limit abuse, cap AI use per session and globally, and monitor cost. These controls reduce risk but cannot guarantee that all visitor-entered information is synthetic. It must never fabricate company policies, product claims, certifications, medical safety claims, or clinical advice. Escalation language should direct users to qualified healthcare professionals where appropriate.

## 12. Architectural baseline and delivery boundaries

This is a proposed baseline, not an implementation claim:

| Layer | Proposed technology |
| --- | --- |
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic |
| AI | LangGraph, LangChain, selected LLM provider, embeddings/RAG |
| Data | PostgreSQL, pgvector, database-backed state/drafts/submissions/sync tasks |
| Integration | Google Sheets API |
| Engineering | Docker, GitHub Actions, automated tests and AI evaluation |

Delivery proceeds from local development to an affordable/free-tier public demo, then to a separately validated AWS milestone. AWS is not presumed to be the permanent demo host. A reference AWS design may use ECS/Fargate, RDS, S3, ECR, CloudWatch, IAM, and Terraform; billable resources must be documented and torn down after validation. No code, dependency installation, resource provisioning, or deployment exists as part of this document.

## 13. Quality and release criteria

Release evidence must include: passing critical automated tests; completed end-to-end quote and support demonstrations; persistence verification showing the request exists before customer confirmation; sync retry/reconciliation verification including an ambiguous Sheets-write outcome; security and authorization checks; duplicate-submission checks; medical-safety evaluation; documented AI evaluation methodology and results for approximately 65 scenarios against the proposed 90% aggregate target; and confirmation that public demo boundaries, privacy disclosures, restricted Sheets access, and inquiry cleanup policy remain intact. The project must not report test, performance, security, or evaluation results until measured.

## 14. Assumptions, constraints, dependencies, and open decisions

### Approved assumptions and constraints

- The demonstration uses synthetic operations data and has no real transaction path.
- Branding requires permission before use.
- Sessions expire after seven days of inactivity and activity renews the window.
- PostgreSQL is authoritative; Sheets synchronization is downstream and asynchronous.

### Dependencies

- Approved synthetic catalog, stock distribution, prices, image rights/creation plan, and knowledge documents.
- Chosen LLM/embedding provider, credentials, budget, and acceptable-use review.
- PostgreSQL/pgvector-capable environment, Google Sheets API service identity and dedicated demonstration spreadsheet.
- Privacy, security, and business-review approvals before public release.

### Open decisions (must not be invented)

- Actual business identity details, addresses, hours, contacts, and branding permission status.
- LLM/embedding provider, model, cost caps, rate limits, and evaluation scoring/threshold refinement.
- Exact availability labels, contact validation rules, inquiry retention duration, cleanup procedure and responsible owner, and final public privacy/disclosure wording.
- Catalog taxonomy, final SKU attributes, image sourcing/licenses, approved document text, and user-facing disclosures.
- Public-demo host, domain, observability platform, data-residency expectations, and AWS validation budget/teardown owner.

## 15. Approved amendment history

| Version | Date | Approved amendment | Approval boundary |
| --- | --- | --- | --- |
| 1.1 | 2026-11-02 | Replaces the previous one-active/one-previous conversational-request capacity with one active request plus up to four saved resumable requests (maximum five), natural-language and chip-based resumption, and least-recently-used inactive-request eviction. | This approves only the product-requirements and MVP-scope amendment. It does not approve unresolved business permissions, privacy/safety reviews, provider selection, deployment readiness, implementation, or release decisions. |

## 16. Requirement traceability and acceptance management

The functional-requirements table is the authoritative initial mapping from approved identifiers to acceptance criteria. NFR-001 maps to section 13. Before implementation, each requirement should be decomposed into design references, test cases, owner, priority, release target, and evidence link in the future [development roadmap](07-development-roadmap.md). Conversation-specific state transitions should be specified in [conversation flows](02-conversation-flows.md); operating procedures in [business operations](04-business-operations.md).

| Requirement group | Evidence required for acceptance |
| --- | --- |
| Identity, scope, catalog, and imagery (BR-001–BR-003) | Synthetic-data/branding disclosures, catalog schema/data validation, image-reference and fallback checks. |
| Conversation, quotes, and sessions (FR-001–FR-005) | UI/API and state-transition tests; durable draft/submission verification; idempotency and immutability tests. |
| Sync, knowledge, discovery, and inventory (FR-006–FR-011) | Outbox/retry/reconciliation tests; retrieval-grounding tests; filter/quantity/alternative tests. |
| Support, safety, and public security (FR-012–FR-016) | Consent-flow tests; safety evaluation cases; security/rate-limit/credential/duplicate-protection review. |
| Release quality (NFR-001) | Recorded release checklist, evaluation report, exception log for permitted noncritical deferrals. |

Any requirement change must retain its identifier, describe the rationale and approval, update acceptance evidence, and avoid converting proposed thresholds or unknown business facts into approved commitments.
