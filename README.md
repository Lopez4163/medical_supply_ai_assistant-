# Medical Supply AI Assistant

A portfolio-first, full-stack AI engineering demonstration by **Queens Tech Bros (QTB)**. The project models a guest-facing assistant for a family-owned medical-supply and pharmaceutical-distribution business, helping visitors discover products, check indicative availability, draft quotation requests, and request human support.

## Demonstration boundaries

This is a pro bono, real-business-inspired demonstration. Catalog items, inventory, prices, customers, operational information, and public submissions are synthetic. Use of any real business branding is contingent on permission. The project is not represented as a production system, does not take payments or create commercial orders, and does not connect public demo submissions to real business operations.

## Planned MVP capabilities

- AI-guided catalog discovery with in-chat product result cards
- Hybrid keyword, attribute, and semantic product retrieval
- Guest sessions, resumable conversation state, and persistent draft quotation requests
- Availability-aware alternatives and a confirmed quotation-submission flow
- Approved-information RAG for company and policy questions
- Optional human-support inquiry workflow
- PostgreSQL-first persistence with one-way Google Sheets demonstration synchronization
- Medical-information safety controls, abuse safeguards, automated tests, and AI evaluations

## Architectural baseline

The proposed stack is Next.js, React, TypeScript, and Tailwind CSS on the frontend; Python, FastAPI, and Pydantic on the backend; LangGraph and LangChain for AI orchestration; PostgreSQL with pgvector; Google Sheets API; Docker; GitHub Actions; and automated testing/evaluation. An LLM provider remains to be selected. AWS validation is planned as a separate, time-bounded milestone and is not assumed to host the permanent public demo.

## Documentation status

The [Product Requirements Document baseline](docs/01-product-requirements.md) is approved at version 1.0 for product requirements and MVP scope. This approval does not resolve business permissions, privacy/safety review, deployment readiness, implementation, or release decisions; its documented open decisions remain outstanding. The documentation set will later add conversation flows, catalog/inventory design, business operations, technical architecture, database/API design, and a development roadmap.

## Planned phases

1. Requirements, architecture, data model, and safety design
2. Synthetic catalog and backend foundations
3. Conversational product discovery, RAG, and quotation workflows
4. Integration, testing, AI evaluation, and public-demo hardening
5. Affordable public-demo deployment, followed by a separately documented AWS validation and teardown milestone

No application code, dependencies, cloud resources, or deployment configurations have been created in this repository.
