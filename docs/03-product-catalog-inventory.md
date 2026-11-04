# Product Catalog & Inventory Specification — Medical Supply AI Assistant

| Field | Value |
| --- | --- |
| Organization | Queens Tech Bros (QTB) |
| Version | 1.0 |
| Status | Approved — Product Catalog & Inventory Baseline |
| Owner | QTB Product and Engineering |
| Date | 2026-11-03 |
| References | [PRD v1.1](01-product-requirements.md); [Conversation Flow Specification v0.2](02-conversation-flows.md) |
| Approval | Approved for the synthetic catalog specification baseline only. This does not approve image rights, real product claims, supplier authorization, implementation, regulatory-compliance certification, deployment, or public release. |

## 1. Purpose and scope

This document proposes a practical synthetic catalog for the portfolio-first Medical Supply AI Assistant. All names, prices, inventory counts, images, relationships, and availability shown here are fictional demonstration data. They are not supplier data, live retailer prices, clinical advice, or a commitment to fulfill an order.

The catalog covers common distributor-style products in nine categories. It excludes prescription medications, controlled medications, standalone injection needles, needle-equipped syringes, insulin medication, and products requiring restricted public-demo transactions. Approved glucose-testing lancets remain included. Until a separate compliance decision exists, syringe products are needle-free measuring, enteral, storage, or disposal supplies only.

## 2. Assortment summary

The proposal has **80 unique parent product listings** and **100 independently sellable variant SKUs**. Variants exist only where a selection changes the stocked item; the catalog does not use artificial SKU padding.

| # | Category | Parent listings | Sellable SKUs |
| --- | --- | ---: | ---: |
| 1 | Mobility & Walking Aids | 10 | 13 |
| 2 | Bathroom Safety & Patient Care | 9 | 10 |
| 3 | Diabetes Testing Supplies | 9 | 12 |
| 4 | Diagnostics & Monitoring | 8 | 10 |
| 5 | Personal Protective Equipment | 9 | 13 |
| 6 | Wound Care & First Aid | 9 | 11 |
| 7 | Medical Consumables & Sanitation | 10 | 11 |
| 8 | OTC & General Health | 9 | 10 |
| 9 | Syringes & Injection Supplies | 7 | 10 |
| **Total** | **Nine categories** | **80** | **100** |

## 3. Product and variant model

A parent listing is a discoverable product family with a stable `product_id`; it is not necessarily a sellable item. A sellable `sku` identifies one independently priced and stocked selection. A product family cannot be treated as an unambiguous quote item until the customer selects the required variant.

| Concept | Requirement |
| --- | --- |
| Parent product | Stable `product_id`, name, category, short description, active/discontinued lifecycle, primary image reference/fallback, and shared searchable attributes. |
| Sellable variant | Unique `sku`, parent reference, selector values, package/sales unit, indicative USD price, numeric stock, availability, and active/discontinued status. |
| Required fields | Product ID, SKU, name, category, description, sales unit, price, stock, lifecycle status, image reference/fallback, and searchable attributes. |
| Category-specific attributes | JSONB-style attributes such as `size`, `material`, `capacity_ml`, `seat_width_in`, `absorbency`, `strip_system`, `cuff_size`, `package_count`, and `form`. Exact schema is deferred to Document 06. |
| Selectors | Size, model, capacity, packaging count, or form must be shown when needed to resolve a SKU. |
| Images | One primary image may be shared by variants when visually appropriate. PostgreSQL stores a URL/object reference and fallback key, never binary image data. |

| Category | Required searchable JSONB-style attributes |
| --- | --- |
| Mobility & Walking Aids | `mobility_type`, `height_range`, `weight_capacity`, `wheel_size`, `seat_width_in`, `foldable`, `color` where selected. |
| Bathroom Safety & Patient Care | `product_type`, `height_adjustable`, `seat_width_in`, `backrest`, `mounting_type`, `transfer_support`. |
| Diabetes Testing Supplies | `product_type`, `strip_system`, `meter_model`, `lancet_system`, `gauge`, `capacity`, `package_count`. |
| Diagnostics & Monitoring | `device_type`, `measurement_type`, `cuff_size`, `form`, `battery_type`, `cover_compatibility` when verified. |
| Personal Protective Equipment | `ppe_type`, `material`, `size`, `powder_free`, `sterile`, `package_count`, `disposable`. |
| Wound Care & First Aid | `product_type`, `sterile`, `dimensions`, `material`, `adhesive`, `package_count`. |
| Medical Consumables & Sanitation | `product_type`, `dimensions`, `absorbency`, `capacity`, `disposable`, `package_count`, `form`. |
| OTC & General Health | `product_type`, `form`, `active_ingredient` only from approved label source, `strength` only from approved label source, `package_count`. |
| Syringes & Injection Supplies | `product_type`, `needle_included` (must be false in this MVP), `capacity_ml`, `tip_type`, `use_route`, `package_count`. |

In catalog tables, every parent is active unless a variant is explicitly marked Discontinued. Variant notation is `SKU — selector; sales unit; $price; stock; availability`. Stock is exact synthetic PostgreSQL inventory and must never be displayed to public customers.

Image plan codes: **PG** = permitted supplier/manufacturer image if rights are documented; **LG** = properly licensed generic product photograph; **AI** = optional generated generic image after rights review; **PH** = category placeholder fallback. Each entry below specifies the recommended initial plan and its fallback.

## 4. Complete proposed catalog

### 4.1 Mobility & Walking Aids — 10 listings, 13 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| MOB-001 | Adjustable folding walker — basic aluminum walking frame. | Adult, two-button fold, height-adjustable. | `MOB-WLK-ADJ-SLV`; 1 each; $54.00; 18; In Stock. `MOB-WLK-ADJ-BLU`; 1 each; $54.00; 3; Limited Stock. | LG walker; PH Mobility. |
| MOB-002 | Four-wheel rollator — folding rolling walker with seat. | 8-inch wheels, hand brakes, storage pouch. | `MOB-RLT-STD`; 1 each; $149.00; 7; In Stock. `MOB-RLT-WIDE`; 1 each; $169.00; 2; Limited Stock. | LG rollator; PH Mobility. |
| MOB-003 | Transport chair — attendant-propelled folding chair. | 19-inch seat, swing-away footrests. | `MOB-TCH-19`; 1 each; $229.00; 4; In Stock. | LG transport chair; PH Mobility. |
| MOB-004 | Manual wheelchair — folding self-propelled chair. | 18-inch seat, removable leg rests. | `MOB-WCH-18`; 1 each; $389.00; 5; In Stock. `MOB-WCH-20`; 1 each; $419.00; 2; Limited Stock. | LG generic wheelchair; PH Mobility. |
| MOB-005 | Forearm crutches — adjustable pair. | Adult pair, cuff support, height-adjustable. | `MOB-FCR-PAIR`; 1 pair; $72.00; 8; In Stock. | LG crutches; PH Mobility. |
| MOB-006 | Underarm crutches — adjustable pair. | Adult pair, padded underarm/hand grips. | `MOB-UCR-ADULT`; 1 pair; $49.00; 14; In Stock. | LG crutches; PH Mobility. |
| MOB-007 | Offset-handle cane — height-adjustable walking cane. | Aluminum, wrist strap, rubber tip. | `MOB-CAN-OFFSET`; 1 each; $29.00; 22; In Stock. | LG cane; PH Mobility. |
| MOB-008 | Quad-base cane — four-point stability cane. | Small base, height-adjustable. | `MOB-CAN-QUAD`; 1 each; $42.00; 9; In Stock. | LG cane; PH Mobility. |
| MOB-009 | Knee walker — non-motorized lower-leg mobility aid. | Four wheels, padded knee platform, hand brake; no suitability recommendation. | `MOB-KNEE-STD`; 1 each; $179.00; 4; In Stock. | LG generic knee walker; PH Mobility. |
| MOB-010 | Gait belt — basic assisted-transfer belt. | 60-inch washable web belt, quick-release buckle; no hand loops. | `MOB-GAIT-60`; 1 each; $19.00; 16; In Stock. | LG generic belt; PH Patient Care. |

### 4.2 Bathroom Safety & Patient Care — 9 listings, 10 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| BTH-001 | Shower chair — height-adjustable bathing seat. | Backrest, non-slip feet, drainage holes. | `BTH-SHC-BACK`; 1 each; $69.00; 10; In Stock. `BTH-SHC-NOBACK`; 1 each; $54.00; 6; In Stock. | LG shower chair; PH Bathroom. |
| BTH-002 | Transfer bench — bathtub entry bench. | Reversible backrest, adjustable legs. | `BTH-TBENCH`; 1 each; $119.00; 4; In Stock. | LG transfer bench; PH Bathroom. |
| BTH-003 | Raised toilet seat — elevated seat attachment. | 4-inch rise, tool-free clamp. | `BTH-RTS-4`; 1 each; $48.00; 11; In Stock. | LG raised seat; PH Bathroom. |
| BTH-004 | Bedside commode — portable commode chair. | Pail, lid, splash guard, adjustable height. | `BTH-COM-STD`; 1 each; $94.00; 3; Limited Stock. | LG commode; PH Bathroom. |
| BTH-005 | Toilet safety frame — stand-assist rails. | Adjustable width, non-slip feet. | `BTH-TSF-ADJ`; 1 each; $58.00; 8; In Stock. | LG safety frame; PH Bathroom. |
| BTH-006 | Grab bar kit — wall-mount safety bar. | 18-inch bar with mounting hardware; installation suitability not assessed by assistant. | `BTH-GRAB-18`; 1 kit; $36.00; 12; In Stock. | LG grab bar; PH Bathroom. |
| BTH-007 | Bath step stool — non-slip entry step. | 4-inch step, textured surface. | `BTH-STEP-4`; 1 each; $31.00; 7; In Stock. | LG bath step; PH Bathroom. |
| BTH-008 | Bed assist rail — bedside support rail. | Adjustable handle, strap attachment. | `BTH-BEDRAIL`; 1 each; $79.00; 5; In Stock. | LG bed rail; PH Patient Care. |
| BTH-009 | Transfer belt with hand loops — caregiver assist belt. | 60-inch, multiple hand loops for repositioning assistance; distinct from basic `MOB-GAIT-60`. | `BTH-XFER-60`; 1 each; $28.00; 13; In Stock. | LG generic belt; PH Patient Care. |

### 4.3 Diabetes Testing Supplies — 9 listings, 12 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| DIA-001 | GlowCheck glucose test strips — fictional system-specific strips. | Compatible only with GlowCheck G1 meter. | `DIA-GC-STR-50`; 50 strips/vial; $24.00; 42; In Stock. `DIA-GC-STR-100`; 100 strips/vial; $44.00; 18; Limited Stock. | AI generic strip vial or LG; PH Diabetes. |
| DIA-002 | GlowCheck G1 glucose meter kit — fictional meter system. | Meter, case, lancing device; no clinical interpretation. | `DIA-GC-MTR-G1`; 1 kit; $29.00; 9; In Stock. | AI generic meter or LG; PH Diabetes. |
| DIA-003 | ClickSure lancets — single-use lancets. | Compatible with ClickSure lancing device only. | `DIA-CS-LAN-30G`; 100 count; $10.00; 55; In Stock. `DIA-CS-LAN-33G`; 100 count; $11.00; 24; In Stock. | LG generic lancet box; PH Diabetes. |
| DIA-004 | ClickSure lancing device — fictional reusable device. | Accepts ClickSure lancets; no lancets included. | `DIA-CS-LDEV`; 1 each; $14.00; 17; In Stock. | AI generic device or LG; PH Diabetes. |
| DIA-005 | GlowCheck control solution — meter quality-control liquid. | For GlowCheck G1 system only. | `DIA-GC-CTRL`; 1 bottle; $9.00; 8; Limited Stock. | AI generic bottle or LG; PH Diabetes. |
| DIA-006 | NovaTrace N2 glucose meter kit — second fictional meter system. | Meter, case, lancing device; compatible only with NovaTrace N2 strips. | `DIA-NT-MTR-N2`; 1 kit; $32.00; 6; In Stock. | AI generic meter or LG; PH Diabetes. |
| DIA-007 | Home sharps container — disposal container. | 1-quart container, household disposal aid; local disposal rules deferred. | `DIA-SHARP-1QT`; 1 each; $7.00; 20; Limited Stock. | LG container; PH Disposal. |
| DIA-008 | NovaTrace N2 glucose test strips — second fictional system-specific strips. | Compatible only with NovaTrace N2 meter. | `DIA-NT-STR-50`; 50 strips/vial; $26.00; 14; Limited Stock. | AI generic strip vial or LG; PH Diabetes. |
| DIA-009 | Alcohol prep pads — skin-prep consumable. | Individually wrapped pads. | `DIA-ALC-100`; 100 count; $5.00; 65; In Stock. `DIA-ALC-200`; 200 count; $9.00; 28; In Stock. | LG generic box; PH Consumables. |

### 4.4 Diagnostics & Monitoring — 8 listings, 10 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| DGN-001 | Digital thermometer — basic oral/axillary temperature device. | Water-resistant body; no diagnosis or interpretation. | `DGN-THERM-DIG`; 1 each; $13.00; 26; In Stock. | LG generic thermometer; PH Diagnostics. |
| DGN-002 | Non-contact infrared thermometer — forehead temperature device. | Non-contact form factor; no diagnosis or interpretation. | `DGN-THERM-IR`; 1 each; $39.00; 0; Out of Stock. | LG generic infrared thermometer; PH Diagnostics. |
| DGN-003 | Blood pressure monitor — complete home monitoring product. | Automatic inflation; each SKU includes the specified cuff configuration and is not a replacement cuff; no clinical interpretation. | `DGN-BPM-ARM`; complete monitor with standard upper-arm cuff; $46.00; 12; In Stock. `DGN-BPM-ARM-LG`; complete monitor with large upper-arm cuff; $52.00; 6; In Stock. `DGN-BPM-WRIST`; complete monitor with wrist cuff; $34.00; 7; In Stock. | LG generic monitor; PH Diagnostics. |
| DGN-004 | Fingertip pulse oximeter — oxygen saturation display device. | Adult fingertip size; no diagnostic claims. | `DGN-OXI-FING`; 1 each; $28.00; 14; In Stock. | LG generic device; PH Diagnostics. |
| DGN-005 | Basic stethoscope — non-electronic listening device. | Adult-size tubing, spare eartips. | `DGN-STETH-BASIC`; 1 each; $31.00; 10; In Stock. | LG generic stethoscope; PH Diagnostics. |
| DGN-006 | Digital bathroom scale — weight-monitoring scale. | Large display, 400 lb maximum display rating. | `DGN-SCALE-DIG`; 1 each; $32.00; 6; In Stock. | LG generic scale; PH Diagnostics. |
| DGN-007 | Diagnostic penlight — inspection light. | Reusable LED, pupil gauge marking; no diagnosis. | `DGN-PENLIGHT`; 1 each; $8.00; 19; In Stock. | LG generic penlight; PH Diagnostics. |
| DGN-008 | Peak flow meter — respiratory monitoring accessory. | Adult-scale meter; no treatment recommendation. | `DGN-PEAK-ADULT`; 1 each; $25.00; 5; In Stock. | LG generic meter; PH Diagnostics. |

### 4.5 Personal Protective Equipment — 9 listings, 13 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| PPE-001 | Nitrile exam gloves — powder-free disposable gloves. | Single-use, blue, non-sterile. | `PPE-NIT-S`; 100/box; $11.00; 65; In Stock. `PPE-NIT-M`; 100/box; $11.00; 15; Limited Stock. `PPE-NIT-L`; 100/box; $11.00; 48; In Stock. | LG generic glove box; PH PPE. |
| PPE-002 | Vinyl exam gloves — powder-free disposable gloves. | Single-use, clear, non-sterile. | `PPE-VIN-M`; 100/box; $8.00; 40; In Stock. `PPE-VIN-L`; 100/box; $8.00; 21; In Stock. | LG generic glove box; PH PPE. |
| PPE-003 | Procedure face masks — disposable ear-loop masks. | Non-sterile; no filtration certification claim. | `PPE-MASK-10`; 10/box; $2.00; 40; In Stock. `PPE-MASK-50`; 50/box; $7.00; 75; In Stock. | LG generic mask box; PH PPE. |
| PPE-004 | Reusable face shield — splash-barrier face covering. | Adjustable headband; no respirator claim. | `PPE-FSHIELD`; 1 each; $6.00; 23; In Stock. | LG generic shield; PH PPE. |
| PPE-005 | Isolation gown — disposable protective gown. | Non-sterile, tie back, universal size. | `PPE-GOWN-10`; 10/pack; $19.00; 11; Limited Stock. | LG generic gown; PH PPE. |
| PPE-006 | Shoe covers — disposable covers. | Non-slip textured material, universal size. | `PPE-SHOE-100`; 100/pack; $15.00; 29; In Stock. | LG generic covers; PH PPE. |
| PPE-007 | Bouffant caps — disposable hair covers. | Universal size, non-sterile. | `PPE-CAP-100`; 100/pack; $9.00; 32; In Stock. | LG generic cap pack; PH PPE. |
| PPE-008 | Alcohol hand rub — portable hand sanitizer. | Ethyl alcohol hand rub; label facts must be approved before display. | `PPE-HRUB-8OZ`; 8 oz bottle; $4.00; 37; In Stock. | LG generic bottle; PH Sanitation. |
| PPE-009 | Barrier apron — disposable protective apron. | Non-sterile, fluid-resistant description pending source approval. | `PPE-APRON-100`; 100/box; $18.00; 18; Limited Stock. | LG generic apron; PH PPE. |

### 4.6 Wound Care & First Aid — 9 listings, 11 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| WND-001 | Sterile gauze pads — absorbent wound-cover pads. | Sterile individual pads; no treatment advice. | `WND-GAUZE-2X2`; 25/box; $6.00; 46; In Stock. `WND-GAUZE-4X4`; 25/box; $9.00; 12; Limited Stock. | LG generic gauze box; PH Wound Care. |
| WND-002 | Rolled gauze — conforming wrap. | 4-inch width, stretch wrap. | `WND-ROLL-4`; 12/pack; $13.00; 24; In Stock. | LG generic roll; PH Wound Care. |
| WND-003 | Non-adherent pads — low-adherence wound-cover pads. | 3-inch by 4-inch pads. | `WND-NONAD-3X4`; 10/box; $7.00; 19; Limited Stock. | LG generic pad box; PH Wound Care. |
| WND-004 | Adhesive bandages — assorted everyday bandages. | Assorted sizes, sterile pads. | `WND-BAND-100`; 100/box; $8.00; 34; In Stock. | LG generic bandage box; PH First Aid. |
| WND-005 | Medical tape — securing tape. | Paper or cloth selection required. | `WND-TAPE-PAPER`; 1-inch roll; $3.00; 40; In Stock. `WND-TAPE-CLOTH`; 1-inch roll; $4.00; 26; In Stock. | LG generic tape; PH Wound Care. |
| WND-006 | Wound cleansing spray — saline wound wash. | Sterile saline spray; factual label only. | `WND-WASH-7OZ`; 7 oz can; $10.00; 15; Limited Stock. | LG generic spray; PH Wound Care. |
| WND-007 | Instant cold pack — single-use cold pack. | Activates on use; non-medicinal. | `WND-COLD-6`; 6/box; $9.00; 21; In Stock. | LG generic cold pack; PH First Aid. |
| WND-008 | Triangular bandage — multipurpose cloth bandage. | Cotton, 40-inch folded triangle. | `WND-TRI-1`; 1 each; $4.00; 17; Limited Stock. | LG generic bandage; PH First Aid. |
| WND-009 | Compact first-aid kit — general supplies kit. | Assorted basic supplies; contents listed in product details. | `WND-FAKIT-50`; 1 kit; $22.00; 8; Limited Stock. | LG generic kit; PH First Aid. |

### 4.7 Medical Consumables & Sanitation — 10 listings, 11 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| CON-001 | Disposable underpads — absorbent bed/chair pads. | 30-inch by 36-inch, disposable. | `CON-UNDER-10`; 10/pack; $12.00; 0; Out of Stock. `CON-UNDER-25`; 25/pack; $26.00; 31; In Stock. | LG generic underpad pack; PH Consumables. |
| CON-002 | Adult protective briefs — disposable absorbent briefs. | Unisex, medium only; size selection required. | `CON-BRIEF-M`; 20/pack; $24.00; 14; Limited Stock. | LG generic brief pack; PH Consumables. |
| CON-003 | Disposable washcloths — pre-moistened cloths. | Fragrance-free generic description pending source approval. | `CON-WASH-48`; 48/pack; $7.00; 38; In Stock. | LG generic pack; PH Consumables. |
| CON-004 | Personal cleansing wipes — adult body wipes. | Large disposable wipes; no antimicrobial claim. | `CON-WIPE-60`; 60/pack; $8.00; 44; In Stock. | LG generic wipe pack; PH Consumables. |
| CON-005 | Emesis bags — disposable receptacle bags. | Graduated, single-use bags. | `CON-EMESIS-25`; 25/pack; $13.00; 20; Limited Stock. | LG generic bag pack; PH Consumables. |
| CON-006 | Bedpan — reusable bedside pan. | Durable plastic, standard adult size. | `CON-BEDPAN`; 1 each; $14.00; 9; Limited Stock. | LG generic bedpan; PH Patient Care. |
| CON-007 | Male urinal — reusable bedside urinal. | Spill-resistant cap, 1-liter capacity. | `CON-URINAL-1L`; 1 each; $11.00; 12; Limited Stock. | LG generic urinal; PH Patient Care. |
| CON-008 | Surface disinfectant spray — cleaning product. | Label claims must come from approved source; no efficacy claims in assistant output without source. | `CON-DSINF-32OZ`; 32 oz bottle; $8.00; 25; In Stock. | LG generic spray; PH Sanitation. |
| CON-009 | Disposable exam drapes — single-use drapes. | 40-inch by 60-inch. | `CON-DRAPE-25`; 25/pack; $18.00; 16; Limited Stock. | LG generic drape pack; PH Consumables. |
| CON-010 | Absorbent spill kit — general cleanup kit. | Previously offered cleanup kit; absorbent pads, gloves, disposal bags; no biohazard claim. | `CON-SPILL-1`; 1 kit; $16.00; 0; Discontinued. | LG generic kit; PH Sanitation. |

### 4.8 OTC & General Health — 9 listings, 10 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| OTC-001 | Generic acetaminophen caplets — OTC label-information product. | 500 mg caplets; factual label content only, no dosage recommendation. | `OTC-ACET-100`; 100 count; $8.00; 27; In Stock. | LG generic bottle; PH OTC. |
| OTC-002 | Generic ibuprofen tablets — OTC label-information product. | 200 mg tablets; factual label content only, no dosage recommendation. | `OTC-IBU-100`; 100 count; $7.00; 24; In Stock. | LG generic bottle; PH OTC. |
| OTC-003 | Antacid chewables — OTC label-information product. | Assorted flavor chewables; ingredients require approved label source. | `OTC-ANT-72`; 72 count; $9.00; 19; In Stock. | LG generic bottle; PH OTC. |
| OTC-004 | Saline nasal spray — non-medicated saline product. | 1.5 oz spray; factual label information only. | `OTC-SALINE-15`; 1.5 oz bottle; $5.00; 22; In Stock. | LG generic spray; PH OTC. |
| OTC-005 | Oral rehydration powder — electrolyte drink mix. | 8 packets; no treatment claim. | `OTC-ORAL-8`; 8 packets; $11.00; 13; Limited Stock. | LG generic box; PH OTC. |
| OTC-006 | Cough drops — menthol lozenges. | 30 count; factual label information only. | `OTC-COUGH-30`; 30 count; $4.00; 36; In Stock. | LG generic bag; PH OTC. |
| OTC-007 | Weekly pill organizer — seven-day organizer. | Seven daily compartments; no medicine included. | `OTC-PILL-7`; 1 each; $6.00; 21; In Stock. | LG generic organizer; PH OTC. |
| OTC-008 | Reusable hot/cold compress — flexible compress. | Non-medicated; size selection required. | `OTC-COMP-S`; 1 each; $7.00; 18; In Stock. `OTC-COMP-L`; 1 each; $11.00; 10; Limited Stock. | LG generic compress; PH OTC. |
| OTC-009 | Skin moisturizer — fragrance-free lotion. | 12 oz bottle; cosmetic/general-care description only. | `OTC-LOTION-12`; 12 oz bottle; $6.00; 23; In Stock. | LG generic bottle; PH OTC. |

### 4.9 Syringes & Injection Supplies — 7 listings, 10 SKUs

| Product ID | Product and short description | Important specifications | Variants: SKU; sales unit; price; stock; availability | Image plan |
| --- | --- | --- | --- | --- |
| SYR-001 | Oral dosing syringe — needle-free measuring syringe. | Oral-use only; capacity selection required. | `SYR-ORAL-1ML`; 10/pack; $6.00; 31; In Stock. `SYR-ORAL-10ML`; 10/pack; $9.00; 18; Limited Stock. | LG generic oral syringe; PH Syringes. |
| SYR-002 | Enteral syringe — needle-free enteral feeding syringe. | Enteral-use only; capacity selection required. | `SYR-ENT-20ML`; 10/pack; $14.00; 16; Limited Stock. `SYR-ENT-60ML`; 10/pack; $22.00; 9; Limited Stock. | LG generic enteral syringe; PH Syringes. |
| SYR-003 | Luer-slip syringe — needle-free syringe body. | No needle included; capacity selection required. | `SYR-LS-10ML`; 25/box; $18.00; 20; Limited Stock. `SYR-LS-30ML`; 25/box; $29.00; 11; Limited Stock. | LG generic syringe body; PH Syringes. |
| SYR-004 | Syringe caps — protective caps. | Fits catalog-listed luer-slip syringe body only. | `SYR-CAP-LS`; 100/pack; $8.00; 33; In Stock. | LG generic cap pack; PH Syringes. |
| SYR-005 | Irrigation syringe — needle-free catheter-tip syringe. | 60 mL capacity, no needle included; no clinical-use recommendation. | `SYR-IRR-60ML`; 10/pack; $24.00; 14; Limited Stock. | LG generic irrigation syringe; PH Syringes. |
| SYR-006 | Medication measuring cup — oral liquid measure. | 30 mL reusable cup; no medicine included. | `SYR-CUP-30ML`; 25/pack; $5.00; 28; In Stock. | LG generic cup pack; PH Syringes. |
| SYR-007 | Oral syringe adapter caps — bottle-adapter caps. | For oral dosing workflow; exact bottle compatibility unknown unless verified. | `SYR-ADAPT-25`; 25/pack; $12.00; 15; Limited Stock. | LG generic adapter; PH Syringes. |

## 5. Inventory and availability rules

All inventory is exact synthetic numeric quantity maintained per active SKU in PostgreSQL. Customer-facing output uses only categorical status. Requested-quantity sufficiency is always calculated from current PostgreSQL inventory, never inferred by the LLM. Quotes do not reserve or decrement inventory; a customer may keep unavailable or insufficient-quantity items in an inquiry with an appropriate warning and no fulfillment guarantee.

| Customer-facing availability | Proposed determination | Customer message boundary |
| --- | --- | --- |
| In Stock | Active SKU with inventory above its category threshold. | Available status only; never disclose count. |
| Limited Stock | Active SKU with inventory greater than zero and at or below its category threshold. | State limited availability and validate requested quantity without showing count. |
| Out of Stock | Active SKU with zero inventory. | State unavailable; preserve inquiry eligibility and offer validated alternatives where appropriate. |
| Discontinued | SKU is discontinued, regardless of remaining display history; proposed catalog examples use zero stock. | State no longer offered; preserve an existing inquiry line only with warning. |

| Category group | Proposed Limited Stock threshold | Rationale |
| --- | ---: | --- |
| Durable mobility, bathroom, diagnostics, and diabetes devices | 3 units or fewer for mobility/bathroom/diagnostics; 5 units or fewer for diabetes devices | Diabetes meters/lancing devices are durable, lower-volume items, but retain a separate proposed replenishment buffer. |
| Diabetes consumables, wound care, consumables, PPE, syringes | 20 sellable units/packs or fewer | Frequently purchased consumables need higher replenishment buffer. |
| OTC/general health | 15 sellable units/packs or fewer | Moderate consumer-pack demand and compact shelf stock. |

These thresholds are **proposed** pending independent approval; the statuses in section 4 are calculated using them. Product detail and quote review recheck current inventory. A verified mismatch, such as a requested quantity above stock, must display a warning rather than silently reducing the requested quantity.

## 6. Pricing

All prices in section 4 are synthetic, indicative USD prices per sellable variant and require human confirmation. They are selected to illustrate plausible differences among durable equipment, packages, capacities, and consumer units. They are not verified against suppliers, manufacturers, or live retailers. The assistant may display the variant price from PostgreSQL but must not negotiate, guarantee, or approve pricing.

## 7. Product images and provenance

Image selection follows this order: permitted manufacturer/supplier imagery with documented rights; properly licensed generic product photos; optional AI-generated generic product images when necessary; and category placeholders. One primary image per parent listing may be reused for visually similar variants. Every record needs a fallback key even if an image reference is present.

Before public use, each reference needs provenance, license/permission evidence, attribution requirements, review date, and fallback assignment. Images are stored externally and referenced in PostgreSQL by URL/object reference and fallback key; binaries are not stored in PostgreSQL. No live image search, download, or generation occurs during customer conversations or as part of this document.

## 8. Search, retrieval, and product resolution

Discovery combines PostgreSQL structured filtering with pgvector embeddings. Ranking is, in order: exact SKU/product match; required attribute matches; keyword relevance; then semantic similarity. Hard requirements—such as glove size/material, meter/strip system, product type, capacity, or model compatibility—override semantic similarity.

Search returns up to five product cards per batch. Show More uses an opaque continuation/pagination context that retains the search filters and request context. Cards show image/fallback, parent name, resolved variant where known, package size, indicative price, and categorical availability. Search has no draft side effect. A quote mutation requires an unambiguous sellable SKU; a parent family or ambiguous phrase such as “the gloves” triggers clarification.

## 9. Compatibility and alternatives

Compatibility is deliberately narrow. Verified catalog relationships support GlowCheck G1 meter ↔ GlowCheck strips/control solution, NovaTrace N2 meter ↔ NovaTrace N2 strips, and ClickSure lancing device ↔ ClickSure lancets. A relationship has one of three states: **compatible**, **incompatible**, or **unknown**. Services consult verified relationship records during search, comparison, quote editing, and quotation review; the LLM must not guess. A verified mismatch shows a warning and does not silently remove a quote item. There is no general-purpose compatibility engine for mobility accessories or unrelated products.

| Compatibility fixture | Expected state | Required behavior |
| --- | --- | --- |
| `DIA-GC-MTR-G1` + `DIA-GC-STR-50` | Compatible | Permit the paired selection and retain system context. |
| `DIA-NT-MTR-N2` + `DIA-NT-STR-50` | Compatible | Permit the paired selection and retain system context. |
| `DIA-GC-MTR-G1` + `DIA-NT-STR-50` | Incompatible | Display a verified mismatch warning; do not silently remove an inquiry line. |
| Customer-supplied meter identifier not present in this synthetic catalog + `DIA-GC-STR-50` | Unknown | State that compatibility is not verified; do not infer a match or substitute. |

When a requested SKU or quantity is unavailable, the system may suggest no more than three alternatives. Every alternative must match essential attributes, support the requested quantity according to PostgreSQL, explain a meaningful difference, and avoid unsupported clinical, pharmaceutical, or compatibility substitution. The original SKU remains eligible for an inquiry with warnings and no fulfillment promise.

## 10. Data quality and validation

| Area | Validation requirement |
| --- | --- |
| Identity | `product_id` and `sku` are unique; every SKU references one existing parent listing. |
| Pricing and stock | Indicative price is positive; inventory is a nonnegative integer; discontinued SKU cannot present as In Stock. |
| Sales unit | Unit/count/capacity is present and valid for each sellable SKU. |
| Searchability | Category-required attributes and human-readable selectors are present for each variant. |
| Variants | Variant selectors are unique within a parent; no family becomes quote-eligible without a resolved SKU. |
| Compatibility | Relationship records name both catalog entities, use only compatible/incompatible/unknown, and are used only when verified. |
| Images | Reference, provenance status, and fallback key are present; a missing image displays fallback. |
| Lifecycle | Active/discontinued status is present at product and variant level; status changes are auditable. |
| Assortment quality | Review prevents duplicate product families, near-identical listings, fabricated certifications, and artificial SKU padding. |

## 11. Test fixtures and examples

Fixtures use the synthetic SKUs in this document. They define future tests only; no tests are claimed as executed.

| Scenario | Fixture and expected behavior | Traceability |
| --- | --- | --- |
| Product search/filter | “Medium nitrile gloves” ranks `PPE-NIT-M` ahead of semantic glove matches; returns no more than five cards. | FR-001, FR-008, FR-011; CF-01 |
| Size selection | “Add a walker” requests variant/color selection before quote mutation when multiple suitable walker SKUs remain. | FR-003, FR-011; CF-01, CF-03 |
| Exact SKU | “Add `DIA-GC-STR-50`” resolves directly to that sellable variant. | FR-008, FR-011; CF-01, CF-03 |
| Meter/strip compatibility | `DIA-GC-MTR-G1` + `DIA-GC-STR-50` and `DIA-NT-MTR-N2` + `DIA-NT-STR-50` are compatible; GlowCheck G1 + NovaTrace strips is incompatible; a customer-supplied unlisted meter + GlowCheck strips is unknown. | FR-008, FR-010, FR-013; CF-02, CF-03 |
| Quantity availability | Request 30 of `PPE-NIT-M` checks exact stock and returns insufficient categorical availability without count disclosure. | FR-009; CF-02 |
| Low stock | `MOB-WLK-ADJ-BLU` displays Limited Stock using durable threshold. | FR-009; CF-02 |
| Out of stock | `CON-UNDER-10` displays Out of Stock, remains inquiry-eligible, and can trigger validated alternatives. | FR-009, FR-010; CF-02, CF-03 |
| Discontinued | `CON-SPILL-1` displays Discontinued and cannot be represented as available. | BR-002, FR-009; CF-01, CF-02 |
| Alternatives | Quantity-unavailable `PPE-NIT-M` may offer only variants/products meeting essential glove requirements and requested quantity; differences are shown. | FR-010; CF-02 |
| Draft unavailable item | Add `CON-UNDER-10` to draft: preserve the line and display availability warning; no reservation or fulfillment promise. | FR-003, FR-005, FR-009; CF-03, CF-04 |
| Show More | Search with more than five results retains filters and request context after Show More. | FR-001, FR-002, FR-008; CF-01, CF-05 |
| Missing image | Missing `MOB-002` image reference displays PH Mobility fallback without blocking selection. | BR-003, FR-001; CF-01 |
| Invalid data | Negative stock, zero/negative price, duplicate SKU, absent sales unit, or invalid compatibility state fails catalog validation and is not published. | BR-002, FR-014, FR-015; CF-08 |

## 12. Approved, proposed, and deferred decisions

| Status | Decision |
| --- | --- |
| Approved by referenced requirements | Synthetic catalog; per-SKU price and numeric inventory; categorical public availability; no exact count disclosure; no reservation/decrement; SKU resolution before quote mutation; PostgreSQL authority; image references/fallbacks; grounded compatibility boundaries. |
| Approved in this baseline | The 80-listing/100-SKU synthetic assortment, fictional identifiers, prices, stock levels, image plans, and compatibility mappings. The documented thresholds remain proposed values pending the separate approval stated in section 5. |
| Deferred | Exact database schema, APIs, migrations, idempotency contracts, and validation implementation → Document 06. |
| Deferred | Business policy, approved company identity, supplier permissions, and final policy/label source text → Document 04. |
| Deferred | Hosting, object-storage provider, image delivery, infrastructure, and model/provider choices → Document 05. |

This document does not approve product sourcing, restricted-transaction handling, actual medical-device claims, image rights, business permissions, implementation, deployment, or release.
