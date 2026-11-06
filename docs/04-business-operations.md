# Business Operations & Knowledge Base Specification — BioMedicHospicare Medical Supply AI Assistant

| Field | Value |
| --- | --- |
| Organization | Queens Tech Bros (QTB) |
| Version | 1.0 |
| Status | Approved — Business Operations & Knowledge Base Specification |
| Owner | QTB Product and Engineering |
| Date | 2026-11-03 |
| References | [PRD v1.2](01-product-requirements.md); [Conversation Flow Specification v1.1](02-conversation-flows.md); [Product Catalog & Inventory Baseline v1.0](03-product-catalog-inventory.md) |
| Approval | Approval covers fictional demo business rules and knowledge-base specifications only; it does not approve actual knowledge-source publication, live-business claims, regulatory compliance, implementation, deployment, or public release. |

## 1. Purpose and scope

This document specifies the business-information, quotation, fulfillment-selection, support, and knowledge-governance behavior for the BioMedicHospicare portfolio demonstration. Queens Tech Bros is developing the project pro bono primarily as an engineering portfolio demonstration. The application uses synthetic catalog inventory, prices, customers, quotation requests, and operating records; it is not connected to BioMedicHospicare's live commercial systems.

It does not create real orders, accept payments, reserve inventory, guarantee fulfillment, provide clinical recommendations, or contact actual business operations. This specification does not create the six planned knowledge-base source files, database records, integrations, or implementation artifacts.

## 2. Fact status and disclosure model

Business information must be visibly classified in source metadata and internally traceable by the following status.

| Status | Meaning | Customer-facing treatment |
| --- | --- | --- |
| User-confirmed business fact | Project-supplied fact from the user; it is not necessarily an independently verified claim. | May be stated within the demonstration's stated scope, with source status retained. |
| Approved fictional demo policy | Deliberate behavior for the synthetic demonstration. | Describe as demonstration behavior, especially at submission/review points. |
| Proposed detail requiring review | Useful draft detail without final approval. | Do not present as a real business fact; use only after approval or state uncertainty. |
| Deferred/unknown real-world information | Information not supplied or verified. | Do not invent it; offer a synthetic support inquiry when appropriate. |

The application should disclose its synthetic-demo boundary before quote/support submissions, when an answer could otherwise imply a real commercial commitment, and when a visitor asks for live business contact or fulfillment facts. It need not repeat a disclaimer in every ordinary product-search response. Before submission, it encourages visitors to use fictional names, phone numbers, and email addresses, but it must not assume visitor-entered contact data is synthetic. It must never say that a request reached real BioMedicHospicare staff or systems.

## 3. Business identity and context

| Field | Status | Value or handling |
| --- | --- | --- |
| Business name | User-confirmed | BioMedicHospicare |
| Country | User-confirmed | Colombia |
| Home city | User-confirmed | Cali, Valle del Cauca |
| Industry | User-confirmed | Medical supplies and equipment distribution |
| Demo customer segments | Approved demo scope | Individual customers, caregivers, clinics, healthcare organizations, and bulk purchasers |
| Development organization | User-confirmed | Queens Tech Bros (QTB) |
| Branding | Proposed/dependent | Business identity and authorized branding may be used only after permission and approved assets are confirmed. |
| Address, telephone, email, website, legal entity, pickup address | Unknown | Not supplied; never fabricate or infer. |
| Delivery/service area and logistics commitments | Unknown | Shipping/delivery is a business offering, but exact coverage and policies require human confirmation. |

## 4. Business hours

The following are approved **fictional demonstration hours**, not verified BioMedicHospicare operating hours.

| Day | Demo hours | Time zone |
| --- | --- | --- |
| Monday–Friday | 8:00 AM–7:00 PM | `America/Bogota` |
| Saturday | 9:00 AM–1:00 PM | `America/Bogota` |
| Sunday | Closed | `America/Bogota` |

Guests may browse the synthetic catalog and submit synthetic quote/support inquiries outside these hours. The display of hours or an in-hours status does not guarantee real staff availability or response. Holiday exceptions are unknown and must not be invented.

## 5. Pricing and currency

Document 03's synthetic indicative USD prices remain the demonstration currency. The application does not convert prices to COP or provide exchange-rate functionality. Prices are not binding commercial offers; the assistant may retrieve and display stored variant prices but cannot negotiate, promise discounts, guarantee totals, approve special pricing, or commit the company to a sale.

Taxes, shipping fees, delivery fees, and other charges are unknown unless later approved as synthetic demonstration data. They must not be silently added to a quote. Any final price is subject to hypothetical human confirmation.

## 6. Quotation and bulk-order policies

The system handles **quotation requests**, not purchases. The following are approved fictional demo policies:

- No minimum order quantity; any positive quantity may be requested.
- Bulk quotation requests are supported, but no automatic volume discounts apply.
- Special or bulk pricing requires human review.
- No online payments, automatic order placement, inventory reservation, or inventory decrement occurs.
- No fulfillment is guaranteed; a quantity above current synthetic stock or an unavailable product may remain in a draft with warnings.

Quote quantities are positive whole numbers of the selected SKU's sales unit, not loose individual items unless that SKU is sold as `1 each`. For example, one wheelchair means one `each`; two boxes of nitrile gloves means two selected sellable boxes of 100; three packs of underpads means three packs of the selected size. If a customer says “30 medium nitrile gloves,” the assistant must clarify whether that means 30 individual gloves or 30 boxes of the selected SKU before mutating the draft. This preserves Document 03's parent-product/variant-SKU model and prevents an ambiguous quantity from becoming a quote line.

Quote creation, editing, review, explicit confirmation, durable PostgreSQL submission, immutable submission state, and draft clearing follow Documents 01 and 02. Required contact fields are first name, last name, and at least one valid email address or phone number. No account or mandatory registration is introduced.

After successful PostgreSQL persistence, the customer-facing message confirms that a **demonstration quotation inquiry was recorded**. It does not say a real business order was accepted. Google Sheets is an asynchronous downstream demonstration synchronization and cannot determine whether customer submission succeeds.

## 7. Fulfillment selection: delivery or pickup

During quote review, the guest selects one fulfillment preference and may switch it before final submission. The chosen method and applicable details are persisted as part of the quotation inquiry; this is not a logistics-management system.

| Option | Collection and customer boundary |
| --- | --- |
| Delivery | Collect destination city and only the delivery details needed for a staff-reviewed synthetic inquiry. The business is Colombia-based, but no nationwide/international coverage, carrier, rate, schedule, serviceability, or arrival date is assumed. Fees and timing require human confirmation. |
| Local pickup | Offer Cali local pickup as a fictional demo option. Do not invent a street address. Pickup location, timing, availability, and readiness require human confirmation. |

Destination collection must be privacy-conscious: ask for the minimum needed at review, do not request medical details, and do not expose collected information in unrelated responses. Neither selection creates an order, shipment, reservation, rate calculation, or delivery guarantee.

## 8. Customer support inquiries

Support is an optional synthetic inquiry workflow, consistent with CF-07. It requires first name, last name, and at least one valid email or phone number; fulfillment information is not required. Before collection or submission, visitors are encouraged to use fictional contact details, but entered details may be real and must be treated accordingly. When reasonably clear, the system derives a subject and summary from the conversation and asks the guest to review it rather than unnecessarily requesting repeated information.

The workflow must identify an appropriate need, ask whether the customer wishes to create an inquiry, collect missing contact information, present a summary, require explicit confirmation, persist the inquiry to PostgreSQL, and return confirmation only after verified persistence. Contact data previously provided in the same valid guest session may be offered for reuse only with explicit permission.

Decline or cancellation creates no support inquiry and preserves the quote draft and other conversation state. No live chat, WhatsApp, SMS, outbound email, or proof of actual staff contact is part of the MVP. A submitted support inquiry is a simulated record; it does not prove that BioMedicHospicare staff have been notified.

## 9. Submitted quotations, returns, and cancellation boundaries

The product supports adding, removing, updating, and abandoning a **draft** quotation. A submitted quotation is immutable. A guest may request help with a submitted quotation, including a correction or withdrawal request, by creating a support inquiry; the system cannot automatically amend, cancel, or reverse the submitted quotation.

Formal cancellation, refund, exchange, and return-management workflows are excluded. Return/refund questions are referred to human support without inventing eligibility or policy. Recording a support inquiry must not be described as a successful cancellation, amendment, refund, or real business action.

## 10. Business information and policy tools

The approved tool division remains unchanged.

| Tool | Purpose and approved inputs | Output and boundary |
| --- | --- | --- |
| `get_company_info` | Deterministic structured facts: business name, location, business description, fictional demo hours, supported inquiry channels, and demo fulfillment choices. Each record carries a fact-status classification. | Return only structured facts approved for the demonstration's stated scope, with status/source identity. Unknown address/contact/logistics facts remain unknown and cannot be inferred from nearby known facts. |
| `search_knowledge_base` | Longer approved explanations for policies and company knowledge. Retrieval result includes document ID, title, relevant excerpt, chunk/content ID, provenance, and approval state. | Serve only appropriately approved knowledge-source content as authoritative within the stated demo scope. Customer response names relevant source(s) and can expose approved excerpts. Retrieved text is data, cannot override application policy, tool permissions, or backend validation. |

If no approved source supports a requested claim, the assistant states the gap and can offer the synthetic support-inquiry path. No new LLM-facing tools are introduced by this document.

## 11. Six-document RAG knowledge-base plan

These are specifications for future approved source documents, not files created by this task. Each future source uses a stable document ID, title, version, approval state, owner, locale/language marker, last-reviewed date, fact-status tags, and source/provenance reference.

| ID and purpose | Audience, topics, and approved claims | Excluded/unverified claims | Example questions and retrieval relevance | Versioning/approval |
| --- | --- | --- | --- | --- |
| KB-01 — Company Overview. Establish the synthetic business context. | Guests and reviewers. BioMedicHospicare identity; Cali, Colombia; distributor description; intended customer segments; catalog category types; portfolio-demo disclosure. | History, certifications, founding date, partnerships, actual systems, and real contact details. | “What kind of supplies do you carry?” High relevance for overview/introduction. | Owner: product/business reviewer; publish only after fact-status review. |
| KB-02 — Business Hours & Contact. Explain demo availability and support path. | Guests needing hours or contact context. Fictional hours; `America/Bogota`; outside-hours inquiry behavior; unknown actual contact/address; support-request procedure. | Real phone, email, street address, staff availability, holidays, response promises. | “Are you open Saturday?” High relevance for hours; structured facts may answer first. | Owner: business reviewer; demo-policy approval required. |
| KB-03 — Shipping & Delivery. Explain delivery inquiry boundary. | Guests considering delivery. Colombia-based context; destination city/details; service-area review; staff-confirmed fees/timing; no automatic estimate/guarantee. | Carrier, coverage map, rates, delivery times, international service. | “Do you deliver to Bogotá?” High relevance; answer requires human confirmation. | Owner: operations reviewer; policy approval required. |
| KB-04 — Quotations & Bulk Orders. Explain quote workflow. | Individual and bulk guests. Draft/submission behavior; positive quantities/no minimum; bulk inquiries; indicative USD pricing; inventory warnings; no payment/reservation; human confirmation. | Binding offer, discount percentage, tax, final total, guaranteed fulfillment. | “Can I request 500 boxes?” High relevance for bulk boundary. | Owner: product/business reviewer; aligns to PRD/CF review. |
| KB-05 — Local Pickup. Explain pickup preference. | Guests choosing pickup. Cali pickup context; selection during review; no invented address; staff confirmation of location/timing/readiness; change method before submission. | Actual pickup address, hours, readiness, appointment confirmation. | “Where can I pick it up?” High relevance; state address is not available. | Owner: operations reviewer; policy approval required. |
| KB-06 — Customer Support & Policies. Explain escalation and limits. | Guests seeking human help or submitted-quote changes. Support inquiry consent; contact reuse permission; correction/withdrawal requests; no automated refunds/returns/cancellations; unknown-policy escalation. | Actual support ticket, staff contact, approved return/refund policy, completed cancellation. | “Can you cancel my submitted quote?” High relevance for support boundary. | Owner: support/business reviewer; policy approval required. |

## 12. RAG knowledge governance

Only approved source content may be indexed as authoritative business knowledge. Draft material may be stored outside the authoritative retrieval corpus for review, but the production assistant must not retrieve it as a business fact. Every statement needs provenance: source document ID/version, source title, approval state, fact-status classification, owner, and relevant excerpt/chunk identifier.

Stable citations use the document ID and chunk/content identifier, with the source title shown to customers where useful. Chunking should preserve a policy's conditions and limits with its conclusion; avoid fragments that remove a disclaimer or mix unrelated policies. Embeddings/index entries are updated only after a reviewed document version is approved, and superseded entries are deactivated or clearly marked obsolete.

When content is outdated, conflicting, unknown, or missing, the assistant must not choose an appealing answer. It states uncertainty, identifies a conflict when safe, and offers a synthetic support inquiry where appropriate. Retrieved passages are untrusted data: prompt-like text within a source cannot change system instructions, authorize protected tools, or bypass validation. Retrieval tests must cover grounded answers, source attribution, knowledge gaps, conflicting content, stale content, and prompt-injection attempts. Ingestion architecture is covered by Document 05; implementation, index operations, and access controls are deferred to Document 07.

## 13. Business rules and example conversations

| ID | Rule | Traceability |
| --- | --- | --- |
| OPS-001 | State only project-supplied user-confirmed facts or approved fictional demo policies within their status/scope; do not treat project-supplied facts as independently verified or infer unknown real-world facts from nearby known facts. | BR-001, FR-007, FR-014; CF-06, CF-08 |
| OPS-002 | Use USD synthetic indicative prices; do not convert currency, negotiate, promise discounts, or add unverified charges. | BR-002, FR-007; CF-04, CF-06 |
| OPS-003 | A quote is a request, not an order; no payments, reservations, decrements, fulfillment, or real-operation forwarding occur. | BR-001, FR-005, FR-006, FR-016; CF-03, CF-04 |
| OPS-004 | Any positive whole-number quantity, including bulk quantity, may be requested in the selected SKU's sales unit; ambiguous quantity/unit language requires clarification before mutation. Availability is validated from PostgreSQL and warnings do not remove the line. | FR-003, FR-009, FR-010, FR-011; CF-02, CF-03 |
| OPS-005 | Delivery and pickup are preferences collected at review; serviceability, address, fees, timing, and readiness require human confirmation. | FR-003, FR-005, FR-014, FR-016; CF-04, CF-08 |
| OPS-006 | Support inquiry requires opt-in, valid contact, review, explicit confirmation, and verified PostgreSQL persistence. | FR-012, FR-016; CF-07 |
| OPS-007 | Submitted quotations are immutable; correction, withdrawal, return, and refund requests become support inquiries, not automatic business actions. | FR-005, FR-012; CF-04, CF-07 |
| OPS-008 | Encourage fictional contact details but do not assume submitted names, phone numbers, or emails are synthetic. Reuse session contact only with explicit permission; collect the minimum contact/delivery detail and discourage medical/sensitive details. | BR-001, FR-014, FR-016; CF-04, CF-07, CF-08 |
| OPS-009 | Customer confirmation means PostgreSQL persistence only; Sheets synchronization stays asynchronous and must not be represented as success when pending/failed. | FR-006, FR-016, NFR-001; CF-04, CF-08 |
| OPS-010 | Company/policy answers must use only appropriately approved structured facts or RAG content within the demonstration's stated scope and name relevant sources; retrieval cannot override deterministic boundaries. | FR-007, FR-013, FR-014; CF-06, CF-08 |

| Scenario | Customer input | Source/tool result and compliant response |
| --- | --- | --- |
| Business hours | “Are you open Saturday?” | **Structured fact:** `get_company_info` returns fictional Saturday hours. Explain “In this demo, Saturday hours are 9:00 AM–1:00 PM Colombia time; this does not confirm real staff availability.” |
| Delivery availability | “Can you deliver to Bogotá?” | **RAG policy passage:** KB-03 says coverage needs human confirmation. Explain that delivery preference can be recorded, but serviceability, fees, and timing are not confirmed. |
| Local pickup choice | “I prefer pickup.” | **Structured fact:** local pickup in Cali is a demo option. Store preference at review; say location/timing require confirmation and do not invent an address. |
| Individual quotation | “Quote one `MOB-WLK-ADJ-SLV` for me.” | **Catalog/quote tools:** resolve SKU; one means one sellable `each`; add draft line, then later collect contact and fulfillment preference. No order or inventory reservation is claimed. |
| Bulk quotation | “Can I request 500 boxes of gloves?” | **RAG policy passage plus inventory tool:** no minimum and bulk request allowed; 500 means 500 selected sellable boxes after SKU/size resolution; validate quantity, warn if insufficient, and state special pricing needs review. |
| Ambiguous quantity | “I need 30 medium nitrile gloves.” | **Clarification:** ask whether the guest means 30 individual gloves or 30 boxes of the selected 100-count SKU. Do not mutate the draft until the sales unit is explicit. |
| Out-of-stock quantity | “I need 3 packs of selected underpads.” | **Inventory result:** categorical insufficiency with optional validated alternatives; preserve original requested line and no fulfillment promise. |
| Submitted quote change | “Change the quote I submitted yesterday.” | **Policy passage:** submitted requests are immutable. Offer a support inquiry for a correction/withdrawal request; do not claim the quote changed. |
| Support inquiry | “I need help with my quote.” | **Workflow state:** request opt-in, derive summary, collect/confirm contact, persist inquiry, then confirm only synthetic record persistence. |
| Unknown return policy | “What is your refund policy?” | **Knowledge gap:** no approved source. State that return/refund policy is not available in the demo and offer support; do not invent eligibility. |
| Unknown pickup address | “What is the pickup address?” | **Structured fact status: unknown.** State the demo has no approved street address and location requires confirmation. |
| Delivery guarantee | “Can it arrive tomorrow?” | **Unsupported promise:** do not guarantee delivery or timing; explain the preference can be recorded for review. |
| Out-of-hours support | “Can someone call me tonight?” | **Structured fact + support boundary:** browsing/inquiry submission is available; no real outreach or staff response is promised. |

## 14. Privacy and safety

Collect only first name, last name, email or phone, and the minimum fulfillment/delivery information necessary for the selected synthetic inquiry. Encourage visitors to use fictional names, phone numbers, and email addresses; nevertheless, do not assume entered information is synthetic. Do not request payment-card data, medical history, diagnosis details, or sensitive personal information. When visitors volunteer such details, avoid repeating or expanding them and redirect to the minimal information needed.

The assistant provides no diagnosis, personalized medication advice, dosage recommendation, or clinical device-suitability promise. It handles stored session contact only within the valid session and only with permission for reuse. Before submission it presents the synthetic-demo disclosure, discourages real medical/sensitive data, and clarifies that no real staff outreach or actual business operation is triggered.

Retention duration, encryption configuration, authentication, data-residency, and deployment-specific security controls remain governed by the PRD's open decisions and later technical documentation. This document introduces no new retention commitment.

## 15. Approved, proposed, and deferred decisions

| Status | Decisions |
| --- | --- |
| Approved | BioMedicHospicare identity and Cali, Colombia base location; synthetic USD pricing; fictional operating hours; quotation-request workflow; positive whole-number SKU-unit quantities; delivery versus local-pickup preference; no guaranteed fees/timelines; support inquiries; no automated cancellations/refunds; six-document RAG scope. |
| Proposed | Detailed delivery/pickup form fields beyond minimum city/details; future source wording; document metadata refinements; operational edge cases requiring review. |
| Deferred | Real contact/pickup details; verified actual policies/business claims; branding/image/supplier rights; exact database/API contracts; hosting/storage; actual RAG source creation/ingestion; live commercial integration; privacy/safety and public-release approval. |

Baseline approval covers the fictional demo business rules and knowledge-base specifications in this document. It does not approve actual knowledge-source publication, live-business claims, regulatory compliance, implementation, deployment, or public release, and it does not alter the approved catalog, conversation architecture, protected submission flows, or synthetic-data boundaries in Documents 01–03.
