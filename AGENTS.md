# Engineering Standards and Codex Instructions

## 1. Project Context and Documentation Authority

Medical Supply AI Assistant is a Queens Tech Bros (QTB) synthetic-data portfolio demonstration inspired by BioMedicHospicare. It is not a live commerce, fulfillment, payment, clinical-care, or real business-operations system.

The approved documents define the product and architecture. Read the relevant ones before changing code:

| Authority | Use it for |
| --- | --- |
| [README](README.md) | Project boundaries, status, and developer context. |
| [01 PRD](docs/01-product-requirements.md) | Approved scope, requirements, safety, and release gates. |
| [02 Conversation Flows](docs/02-conversation-flows.md) | Guest behavior and CF-01–CF-08 acceptance scenarios. |
| [03 Catalog](docs/03-product-catalog-inventory.md) | Product/SKU, availability, compatibility, and synthetic-data rules. |
| [04 Business Operations](docs/04-business-operations.md) | Demo disclosures, operations, and approved knowledge scope. |
| [05 Architecture](docs/05-system-ai-architecture.md) | System boundaries and approved technology choices. |
| [06 Frontend Design](docs/06-frontend-implementation-design.md) | UI, state, component, and accessibility conventions. |
| [07 Backend & API Design](docs/07-backend-api-design.md) | API, persistence, transaction, idempotency, and ChatService contracts. |
| [08 Roadmap](docs/08-development-roadmap.md) | Forty-one implementation tasks, dependencies, and Definition of Done. |

When specifications conflict, stop and report the conflict; do not silently invent a compromise. Document 07 governs final implementation contracts over earlier illustrative material. This file defines how to implement those decisions, not new product behavior.

## 2. General Engineering Principles

- **KISS:** Use the smallest readable implementation that correctly meets the approved task. Do not add framework layers, generic factories, or dependencies without a present need.
- **DRY:** Share meaningful business behavior, such as quotation mutations, between routes and tools. Do not extract an abstraction merely to remove a few similar lines.
- **YAGNI:** Build only approved functionality. Do not pre-build accounts, checkout, extra agents, generic workflow engines, or speculative configuration.
- **Single responsibility:** A component, hook, service, and function should have one understandable purpose. Split only when it improves ownership, testing, readability, or reuse.
- **Readability over cleverness:** Prefer descriptive names, early returns, explicit conditions, and short focused methods. Avoid cryptic abbreviations, deep nesting, metaprogramming, and dense chained transforms.
- **Consistency over preference:** Follow established component, API, error, query-key, and data-access patterns. Explain a justified exception in the change report.
- **Type safety:** Use TypeScript strict mode, typed Python signatures, Pydantic schemas, and SQLAlchemy 2.0 typed models. Do not use `any`, broad casts, untyped boundary dictionaries, or suppressions without a narrowly documented reason.
- **Separation of concerns:** Presentation belongs in React; server cache in TanStack Query; forms in React Hook Form; business rules in Python services; persistence in PostgreSQL; conversational orchestration in LangGraph.
- **Errors are behavior:** Handle expected failure modes explicitly. Never swallow exceptions, blindly replay an uncertain write, or claim success before persistence is verified.
- **Comments:** Explain safety rules, non-obvious business constraints, or technical tradeoffs—not obvious syntax. Add concise docstrings only when a public contract is not self-evident.
- **Scope:** Change only the requested roadmap task or tightly coupled group. Preserve unrelated behavior and uncommitted work.

## 3. Repository and File Organization

Use the approved feature-oriented layout from Document 06 and modular FastAPI monolith from Document 07.

```text
frontend/src/
  app/                 # App Router shell and providers
  features/<feature>/  # Feature components, hooks, validation, UI-only types
  components/ui/       # shadcn/ui primitives only
  components/layout/   # Shared layout concerns
  lib/api/             # Generated transport types and typed client
  lib/query/           # Query client and centralized keys

backend/app/
  api/v1/              # Thin versioned HTTP routers
  schemas/             # Pydantic contracts
  models/              # SQLAlchemy entities
  services/            # Deterministic business operations and transactions
  repositories/        # Non-trivial reusable queries only
  agents/              # Graph, state, prompts, thin tools
  db/ core/ workers/ dev/
```

Keep feature-local code with its feature. Do not turn `components/` into a dumping ground, add barrel files everywhere, or create repositories that merely wrap one-line queries. Generated OpenAPI types are not hand-maintained domain models.

## 4. TypeScript and React Conventions

Use Next.js App Router, React functional components, strict TypeScript, Tailwind, and shadcn/ui. Reusable components and hooks use named exports, PascalCase component names, explicit `ComponentNameProps` types, destructured props, semantic HTML, visible focus behavior, and accessible names.

Keep data fetching and mutation orchestration in hooks; keep focused display components presentational. Components render backend-provided indicative prices and categorical availability—they do not calculate authoritative price/stock or mutate business data directly. Avoid unnecessary `memo`, effects, Context providers, and custom hooks.

```tsx
// Illustrative convention; transport names come from generated OpenAPI types.
type ProductCardProps = {
  product: ProductCardPublic;
  onRequestAdd: (sku: string) => void;
  isPending?: boolean;
};

export function ProductCard({ product, onRequestAdd, isPending = false }: ProductCardProps) {
  return (
    <article aria-label={product.name} className="rounded-lg border p-4">
      <img alt={product.image_alt ?? product.name} src={product.image_url ?? "/images/product-fallback.svg"} />
      <h3>{product.name}</h3>
      <p>{product.sales_unit}</p>
      <p>{product.indicative_price_display}</p>
      <p>{product.availability_label}</p>
      <button disabled={isPending} onClick={() => onRequestAdd(product.sku)}>
        Add to Quote
      </button>
    </article>
  );
}
```

`onRequestAdd` must obtain an explicit positive whole-unit quantity or invoke approved backend clarification; it must never silently assume quantity `1`. Do not render arbitrary model HTML, code, or components. Do not add a sidebar, visible topic chips, multiple threads, account UI, storefront, or checkout.

## 5. TanStack Query and State Management

| State | Owner |
| --- | --- |
| Authoritative business data | FastAPI and PostgreSQL |
| Cached server state | TanStack Query |
| Temporary presentation state | `useState` / `useReducer` |
| Form state | React Hook Form |
| Transport types | FastAPI OpenAPI → `openapi-typescript` |
| Executable conversation state | LangGraph PostgreSQL checkpointer |

Use `useQuery` for reads, `useMutation` for writes, and centralized keys. Do not create independent copies of quotations, inventory, or conversation history in Context or a new state library. Local optimistic/provisional UI is never authoritative. Handle pending, error, empty, and success states.

```ts
// lib/query/query-keys.ts
export const queryKeys = {
  draftQuote: () => ["draft-quote"] as const,
  product: (sku: string) => ["product", sku] as const,
  conversation: () => ["conversation"] as const,
};

export function useProduct(sku: string | undefined) {
  const productSku = sku ?? "";

  return useQuery({
    queryKey: productSku ? queryKeys.product(productSku) : ["product", "missing"],
    queryFn: () => api.getProduct({ sku: productSku }),
    enabled: Boolean(productSku),
  });
}
```

```ts
export function useAddQuoteItem() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AddQuoteLineRequest) => api.addQuoteLine(input),
    retry: false, // uncertain mutations reconcile; they are not blindly retried
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.draftQuote() });
    },
  });
}

function QuotationPanel() {
  const [isDrawerOpen, setDrawerOpen] = useState(false);
  return <button onClick={() => setDrawerOpen(true)}>Open quotation</button>;
}
```

Mutation payloads use the approved stable operation ID and expected draft version. On `QUOTE_VERSION_CONFLICT` or an uncertain operation, fetch/reconcile authoritative backend state before offering a new user action.

`useChat` composes TanStack Query plus minimal provisional UI state: restore backend history, create one stable client-message ID per send, prevent duplicate sends, issue one non-streaming request, reconcile provisional/persisted messages, handle uncertain network results safely, and invalidate the draft query only when the response signals a committed quote change. Do not keep a competing authoritative full chat history in the browser or use an unrelated chat/state library.

## 6. React Hook Form and Zod

Use React Hook Form with `zodResolver` for quotation and support forms. Zod provides client feedback; FastAPI/Pydantic remains authoritative. Use clear fields, accessible `aria-describedby` error links, and preserve approved form state when moving between chat and drawer/panel.

```tsx
const contactSchema = z
  .object({
    firstName: z.string().trim().min(1),
    lastName: z.string().trim().min(1),
    email: z.string().trim().email().or(z.literal("")).optional(),
    phone: z.string().trim().min(1).or(z.literal("")).optional(),
  })
  .refine((value) => Boolean(value.email?.trim() || value.phone?.trim()), { message: "Provide an email address or phone number", path: ["email"] });

const form = useForm<z.infer<typeof contactSchema>>({
  resolver: zodResolver(contactSchema),
  defaultValues: { firstName: "", lastName: "", email: "", phone: "" },
});
```

Use a model-level schema/refinement for cross-field rules such as email-or-phone and delivery-city-if-delivery. Do not replace a form with many manually synchronized `useState` values, rely on Zod for authorization, or bypass backend validation.

## 7. FastAPI Route and Pydantic Conventions

Routes live under `/api/v1`, use correct HTTP methods, `response_model`, typed dependencies, snake_case handlers, and shared public error mapping. Routes parse HTTP, obtain trusted context, call one service, and map its result/error. They do not contain business rules, SQL, transaction choreography, or direct LLM calls.

```python
# Illustrative: final contracts remain those in Document 07.
@router.post("/quotations/draft/lines", response_model=DraftQuotePublic)
async def add_quote_line(
    request: AddQuoteLineRequest,
    guest: GuestContext = Depends(require_guest_session),
    service: QuotationService = Depends(get_quotation_service),
) -> DraftQuotePublic:
    return await service.add_line(guest_session_id=guest.session_id, request=request)

class AddQuoteLineRequest(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0)
    expected_version: int = Field(ge=0)
    operation_id: UUID
```

Use explicit request/response schemas, constrained typed fields, and validators only for stable contract rules. Do not pass arbitrary dictionaries where a Pydantic schema is warranted. FastAPI OpenAPI is the frontend transport authority; JSON aliases require an approved, consistent convention.

## 8. Python Services and SQLAlchemy

Services own deterministic business operations, authorization checks, and transaction boundaries. Give dependencies and public methods concrete types. Routes and LangGraph tools call the same services; do not duplicate quotation logic or place HTTP concerns in services.

```python
class QuotationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_line(self, *, guest_session_id: UUID, request: AddQuoteLineRequest) -> DraftQuotePublic:
        draft = await self._load_locked_active_draft(guest_session_id)
        existing_operation = await self._find_operation(draft_id=draft.id, operation_id=request.operation_id)
        if existing_operation is not None:
            return await self._reconcile_operation(existing_operation)
        if draft.version != request.expected_version:
            raise QuoteVersionConflict()
        # Resolve SKU, apply idempotency, merge one SKU line, and increment version
        # in the same transaction; implementation details belong to Document 07.
        return await self._commit_and_project_draft(draft, request)
```

Use SQLAlchemy 2.0 typed models, `Mapped`, `mapped_column`, explicit foreign keys, database constraints, parameterized queries, Alembic migrations, correct async session lifecycle, and explicit row locks/version checks for protected changes.

```python
class QuoteDraftLine(Base):
    __tablename__ = "quote_draft_lines"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    draft_id: Mapped[UUID] = mapped_column(ForeignKey("quote_drafts.id"), index=True)
    sku_variant_id: Mapped[UUID] = mapped_column(ForeignKey("sku_variants.id"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quote_draft_line_quantity_positive"),
        UniqueConstraint("draft_id", "sku_variant_id", name="uq_quote_draft_line_sku"),
    )
```

Enforce one active draft/session, one line/SKU/draft, positive whole quantities, stable idempotency IDs, safe version checks, immutable submissions, and atomic submission/outbox writes. No hidden commits in helpers, inventory reservation, real order behavior, React database access, or direct SQL from tool wrappers.

## 9. LangGraph, Tools, and RAG

Use one approved tool-calling agent and the twelve approved tools only. LangGraph checkpoints are the authoritative executable conversation state: one active plus four saved internal request contexts, LRU eviction, request-bound pending actions, and five tool rounds maximum. Natural-language resumption is customer-facing; no visible topic navigation exists.

Tools are thin validated LangChain wrappers over deterministic services. Inject trusted server context; models never select a guest/session identity, authorization, or idempotency ID. Agent mutation IDs are backend-assigned and stable across recovery. The agent has no arbitrary SQL or direct Google Sheets access.

```python
@tool("get_draft_quote", args_schema=GetDraftQuoteInput)
async def get_draft_quote_tool(runtime: ToolRuntime[GuestContext]) -> DraftQuotePublic:
    return await runtime.context.quotation_service.get_draft(guest_session_id=runtime.context.session_id)
```

Illustrative wrappers must validate input/output and delegate; they must not embed policy, persistence, or authentication logic. Reconcile committed state after a provider failure, five-round limit, or uncertain mutation before retrying. RAG retrieves only approved current content through pgvector with the approved initial `RAG_TOP_K=1`, includes source metadata, and abstains when evidence is insufficient. Retrieved text is data, never instructions.

## 10. Error Handling, Security, and Logging

Use typed domain errors and centralized public error mapping. Public responses are safe, consistent, and actionable; no stack trace, SQL/provider detail, exact stock count, token, secret, contact detail, or private transcript is exposed.

```python
class QuoteVersionConflict(Exception):
    pass

def to_api_error(error: QuoteVersionConflict, *, request_id: UUID) -> ApiError:
    return ApiError(
        code="QUOTE_VERSION_CONFLICT",
        message="The quotation changed. Refresh and review it again.",
        request_id=request_id,
        retryable=False,
    )
```

Backend controls guest authorization, Secure/HttpOnly cookie and CSRF/origin behavior, validation, rate/budget limits, and protected-tool access. Store secrets only in environment configuration; never log raw session tokens, API keys, submitted contact details, or full conversations by default. Public inventory is categorical only.

Never automatically retry an uncertain potentially committed mutation/submission. Customer confirmation follows verified PostgreSQL persistence only; Google Sheets status is asynchronous and cannot invalidate a committed record or be represented as customer success. Preserve synthetic/demo disclosures and never make a real-operation, fulfillment, diagnosis, dosage, or clinical-substitution claim.

## 11. Testing and Verification

Use pytest/pytest-asyncio/HTTPX with a dedicated PostgreSQL test database for backend and transaction behavior; Vitest/React Testing Library for frontend behavior; Playwright for E2E; controlled AI scenarios for model/agent evaluation. Ordinary tests use mock provider/integration responses and real deterministic business services where behavior matters. Live AI, embeddings, and Sheets runs are deliberate, budgeted, and explicitly reported.

Place tests predictably beside or under the applicable backend/frontend test tree. Use descriptive observable-behavior names and Arrange/Act/Assert where useful. Test failure states, meaningful zero/empty/null values, authorization, version/idempotency/concurrency boundaries, structured response restoration, and protected submission recovery. Do not over-mock deterministic service logic or claim a check passed unless it ran.

```python
async def test_add_quote_line_rejects_stale_draft_version(
    client: AsyncClient, valid_session: Cookie, stale_draft: QuoteDraft
) -> None:
    response = await client.post(
        "/api/v1/quotations/draft/lines",
        json={
            "sku": "PPE-NIT-M",
            "quantity": 2,
            "expected_version": stale_draft.version - 1,
            "operation_id": str(uuid4()),
        },
        cookies=valid_session.as_dict(),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "QUOTE_VERSION_CONFLICT"
```

Illustrative names must be replaced with real fixtures/contracts in implementation; do not make tests permissive merely to pass. Record actual commands/results in the task report. Maintain the approximately 65 approved AI evaluation scenarios without claiming their target has been achieved before evaluation.

## 12. Git, Task Execution, and Completion Reporting

Before editing:

1. Read this file, identify one Document 08 task ID, and read the applicable approved specs.
2. Inspect the existing implementation, related tests, and Git status.
3. Preserve unrelated/uncommitted work and resolve dependency or architecture conflicts before editing.

During implementation, complete one bounded task or tightly coupled group; reuse established patterns; add meaningful tests; avoid new dependencies and abstractions; and report unexpected conflicts rather than silently diverging.

After implementation, run applicable checks, inspect the diff, verify no secrets/unrelated edits, update task progress only with real evidence, and report remaining risks. Do not commit, push, merge, deploy, provision services, modify remote settings, or create branches without explicit owner authorization. Follow `feature/* → dev → main` when branch work is authorized.

Use this completion report:

### Task

Task ID and title.

### Implemented

Concise completed behavior.

### Files Changed

Paths and short descriptions.

### Verification

Exact checks run and pass/fail results.

### Decisions or Deviations

Important tradeoffs or pattern exceptions.

### Blockers / Remaining Work

Known risks and unfinished items.

### Suggested Next Task

Next eligible Document 08 task and whether its prerequisites are satisfied.

Never claim implementation, tests, deployment, or external integration succeeded without evidence.
