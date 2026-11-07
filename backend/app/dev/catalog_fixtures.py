"""Approved synthetic catalog fixtures from Document 03, section 4."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from app.models.catalog import CatalogLifecycleStatus, CompatibilityState


@dataclass(frozen=True)
class VariantFixture:
    sku: str
    selector_attributes: dict[str, object]
    searchable_attributes: dict[str, object]
    sales_unit: str
    indicative_price: Decimal
    quantity_on_hand: int
    lifecycle_status: CatalogLifecycleStatus
    expected_availability: str


@dataclass(frozen=True)
class ProductFixture:
    category_code: str
    product_id: str
    name: str
    description: str
    searchable_attributes: dict[str, object]
    image_fallback_key: str
    variants: tuple[VariantFixture, ...]


@dataclass(frozen=True)
class CategoryFixture:
    code: str
    name: str


@dataclass(frozen=True)
class CompatibilityFixture:
    source_sku: str
    target_sku: str
    state: CompatibilityState


@dataclass(frozen=True)
class CatalogFixture:
    categories: tuple[CategoryFixture, ...]
    products: tuple[ProductFixture, ...]
    compatibilities: tuple[CompatibilityFixture, ...]


CATEGORY_ATTRIBUTE_KEY: Final[dict[str, str]] = {
    "MOB": "mobility_type",
    "BTH": "product_type",
    "DIA": "product_type",
    "DGN": "device_type",
    "PPE": "ppe_type",
    "WND": "product_type",
    "CON": "product_type",
    "OTC": "product_type",
    "SYR": "product_type",
}


def variant(
    sku: str,
    sales_unit: str,
    price: str,
    stock: int,
    availability: str,
    *,
    lifecycle_status: CatalogLifecycleStatus = CatalogLifecycleStatus.ACTIVE,
    **selectors: object,
) -> VariantFixture:
    return VariantFixture(
        sku=sku,
        selector_attributes=selectors,
        searchable_attributes=selectors,
        sales_unit=sales_unit,
        indicative_price=Decimal(price),
        quantity_on_hand=stock,
        lifecycle_status=lifecycle_status,
        expected_availability=availability,
    )


def product(
    category_code: str,
    product_id: str,
    name: str,
    description: str,
    specifications: str,
    fallback_key: str,
    variants: tuple[VariantFixture, ...],
) -> ProductFixture:
    return ProductFixture(
        category_code=category_code,
        product_id=product_id,
        name=name,
        description=description,
        searchable_attributes={
            CATEGORY_ATTRIBUTE_KEY[category_code]: name.lower(),
            "specifications": specifications,
        },
        image_fallback_key=fallback_key,
        variants=variants,
    )


CATEGORIES: Final[tuple[CategoryFixture, ...]] = (
    CategoryFixture("MOB", "Mobility & Walking Aids"),
    CategoryFixture("BTH", "Bathroom Safety & Patient Care"),
    CategoryFixture("DIA", "Diabetes Testing Supplies"),
    CategoryFixture("DGN", "Diagnostics & Monitoring"),
    CategoryFixture("PPE", "Personal Protective Equipment"),
    CategoryFixture("WND", "Wound Care & First Aid"),
    CategoryFixture("CON", "Medical Consumables & Sanitation"),
    CategoryFixture("OTC", "OTC & General Health"),
    CategoryFixture("SYR", "Syringes & Injection Supplies"),
)


PRODUCTS: Final[tuple[ProductFixture, ...]] = (
    # Mobility & Walking Aids — 10 listings, 13 SKUs.
    product(
        "MOB",
        "MOB-001",
        "Adjustable folding walker",
        "Basic aluminum walking frame.",
        "Adult, two-button fold, height-adjustable.",
        "PH Mobility",
        (
            variant("MOB-WLK-ADJ-SLV", "1 each", "54.00", 18, "In Stock", color="silver"),
            variant("MOB-WLK-ADJ-BLU", "1 each", "54.00", 3, "Limited Stock", color="blue"),
        ),
    ),
    product(
        "MOB",
        "MOB-002",
        "Four-wheel rollator",
        "Folding rolling walker with seat.",
        "8-inch wheels, hand brakes, storage pouch.",
        "PH Mobility",
        (
            variant("MOB-RLT-STD", "1 each", "149.00", 7, "In Stock", seat_width_in=18),
            variant("MOB-RLT-WIDE", "1 each", "169.00", 2, "Limited Stock", seat_width_in=20),
        ),
    ),
    product(
        "MOB",
        "MOB-003",
        "Transport chair",
        "Attendant-propelled folding chair.",
        "19-inch seat, swing-away footrests.",
        "PH Mobility",
        (variant("MOB-TCH-19", "1 each", "229.00", 4, "In Stock", seat_width_in=19),),
    ),
    product(
        "MOB",
        "MOB-004",
        "Manual wheelchair",
        "Folding self-propelled chair.",
        "Removable leg rests.",
        "PH Mobility",
        (
            variant("MOB-WCH-18", "1 each", "389.00", 5, "In Stock", seat_width_in=18),
            variant("MOB-WCH-20", "1 each", "419.00", 2, "Limited Stock", seat_width_in=20),
        ),
    ),
    product(
        "MOB",
        "MOB-005",
        "Forearm crutches",
        "Adjustable pair.",
        "Adult pair, cuff support, height-adjustable.",
        "PH Mobility",
        (variant("MOB-FCR-PAIR", "1 pair", "72.00", 8, "In Stock", support="forearm"),),
    ),
    product(
        "MOB",
        "MOB-006",
        "Underarm crutches",
        "Adjustable pair.",
        "Adult pair, padded underarm and hand grips.",
        "PH Mobility",
        (variant("MOB-UCR-ADULT", "1 pair", "49.00", 14, "In Stock", size="adult"),),
    ),
    product(
        "MOB",
        "MOB-007",
        "Offset-handle cane",
        "Height-adjustable walking cane.",
        "Aluminum, wrist strap, rubber tip.",
        "PH Mobility",
        (variant("MOB-CAN-OFFSET", "1 each", "29.00", 22, "In Stock", handle="offset"),),
    ),
    product(
        "MOB",
        "MOB-008",
        "Quad-base cane",
        "Four-point stability cane.",
        "Small base, height-adjustable.",
        "PH Mobility",
        (variant("MOB-CAN-QUAD", "1 each", "42.00", 9, "In Stock", base="quad"),),
    ),
    product(
        "MOB",
        "MOB-009",
        "Knee walker",
        "Non-motorized lower-leg mobility aid.",
        "Four wheels, padded knee platform, hand brake; no suitability recommendation.",
        "PH Mobility",
        (variant("MOB-KNEE-STD", "1 each", "179.00", 4, "In Stock", model="standard"),),
    ),
    product(
        "MOB",
        "MOB-010",
        "Gait belt",
        "Basic assisted-transfer belt.",
        "60-inch washable web belt, quick-release buckle; no hand loops.",
        "PH Patient Care",
        (variant("MOB-GAIT-60", "1 each", "19.00", 16, "In Stock", length_in=60),),
    ),
    # Bathroom Safety & Patient Care — 9 listings, 10 SKUs.
    product(
        "BTH",
        "BTH-001",
        "Shower chair",
        "Height-adjustable bathing seat.",
        "Non-slip feet, drainage holes.",
        "PH Bathroom",
        (
            variant("BTH-SHC-BACK", "1 each", "69.00", 10, "In Stock", backrest=True),
            variant("BTH-SHC-NOBACK", "1 each", "54.00", 6, "In Stock", backrest=False),
        ),
    ),
    product(
        "BTH",
        "BTH-002",
        "Transfer bench",
        "Bathtub entry bench.",
        "Reversible backrest, adjustable legs.",
        "PH Bathroom",
        (variant("BTH-TBENCH", "1 each", "119.00", 4, "In Stock", backrest="reversible"),),
    ),
    product(
        "BTH",
        "BTH-003",
        "Raised toilet seat",
        "Elevated seat attachment.",
        "4-inch rise, tool-free clamp.",
        "PH Bathroom",
        (variant("BTH-RTS-4", "1 each", "48.00", 11, "In Stock", rise_in=4),),
    ),
    product(
        "BTH",
        "BTH-004",
        "Bedside commode",
        "Portable commode chair.",
        "Pail, lid, splash guard, adjustable height.",
        "PH Bathroom",
        (variant("BTH-COM-STD", "1 each", "94.00", 3, "Limited Stock", model="standard"),),
    ),
    product(
        "BTH",
        "BTH-005",
        "Toilet safety frame",
        "Stand-assist rails.",
        "Adjustable width, non-slip feet.",
        "PH Bathroom",
        (variant("BTH-TSF-ADJ", "1 each", "58.00", 8, "In Stock", width="adjustable"),),
    ),
    product(
        "BTH",
        "BTH-006",
        "Grab bar kit",
        "Wall-mount safety bar.",
        "18-inch bar with mounting hardware; installation suitability not assessed by assistant.",
        "PH Bathroom",
        (variant("BTH-GRAB-18", "1 kit", "36.00", 12, "In Stock", length_in=18),),
    ),
    product(
        "BTH",
        "BTH-007",
        "Bath step stool",
        "Non-slip entry step.",
        "4-inch step, textured surface.",
        "PH Bathroom",
        (variant("BTH-STEP-4", "1 each", "31.00", 7, "In Stock", height_in=4),),
    ),
    product(
        "BTH",
        "BTH-008",
        "Bed assist rail",
        "Bedside support rail.",
        "Adjustable handle, strap attachment.",
        "PH Patient Care",
        (variant("BTH-BEDRAIL", "1 each", "79.00", 5, "In Stock", mounting_type="strap"),),
    ),
    product(
        "BTH",
        "BTH-009",
        "Transfer belt with hand loops",
        "Caregiver assist belt.",
        "60-inch, multiple hand loops for repositioning assistance.",
        "PH Patient Care",
        (variant("BTH-XFER-60", "1 each", "28.00", 13, "In Stock", length_in=60),),
    ),
    # Diabetes Testing Supplies — 9 listings, 12 SKUs.
    product(
        "DIA",
        "DIA-001",
        "GlowCheck glucose test strips",
        "Fictional system-specific strips.",
        "Compatible only with GlowCheck G1 meter.",
        "PH Diabetes",
        (
            variant(
                "DIA-GC-STR-50",
                "50 strips/vial",
                "24.00",
                42,
                "In Stock",
                strip_system="GlowCheck G1",
                package_count=50,
            ),
            variant(
                "DIA-GC-STR-100",
                "100 strips/vial",
                "44.00",
                18,
                "Limited Stock",
                strip_system="GlowCheck G1",
                package_count=100,
            ),
        ),
    ),
    product(
        "DIA",
        "DIA-002",
        "GlowCheck G1 glucose meter kit",
        "Fictional meter system.",
        "Meter, case, lancing device; no clinical interpretation.",
        "PH Diabetes",
        (variant("DIA-GC-MTR-G1", "1 kit", "29.00", 9, "In Stock", meter_model="GlowCheck G1"),),
    ),
    product(
        "DIA",
        "DIA-003",
        "ClickSure lancets",
        "Single-use lancets.",
        "Compatible with ClickSure lancing device only.",
        "PH Diabetes",
        (
            variant(
                "DIA-CS-LAN-30G",
                "100 count",
                "10.00",
                55,
                "In Stock",
                lancet_system="ClickSure",
                gauge=30,
            ),
            variant(
                "DIA-CS-LAN-33G",
                "100 count",
                "11.00",
                24,
                "In Stock",
                lancet_system="ClickSure",
                gauge=33,
            ),
        ),
    ),
    product(
        "DIA",
        "DIA-004",
        "ClickSure lancing device",
        "Fictional reusable device.",
        "Accepts ClickSure lancets; no lancets included.",
        "PH Diabetes",
        (variant("DIA-CS-LDEV", "1 each", "14.00", 17, "In Stock", lancet_system="ClickSure"),),
    ),
    product(
        "DIA",
        "DIA-005",
        "GlowCheck control solution",
        "Meter quality-control liquid.",
        "For GlowCheck G1 system only.",
        "PH Diabetes",
        (
            variant(
                "DIA-GC-CTRL", "1 bottle", "9.00", 8, "Limited Stock", strip_system="GlowCheck G1"
            ),
        ),
    ),
    product(
        "DIA",
        "DIA-006",
        "NovaTrace N2 glucose meter kit",
        "Second fictional meter system.",
        "Meter, case, lancing device; compatible only with NovaTrace N2 strips.",
        "PH Diabetes",
        (variant("DIA-NT-MTR-N2", "1 kit", "32.00", 6, "In Stock", meter_model="NovaTrace N2"),),
    ),
    product(
        "DIA",
        "DIA-007",
        "Home sharps container",
        "Disposal container.",
        "1-quart container, household disposal aid; local disposal rules deferred.",
        "PH Disposal",
        (variant("DIA-SHARP-1QT", "1 each", "7.00", 20, "Limited Stock", capacity="1 quart"),),
    ),
    product(
        "DIA",
        "DIA-008",
        "NovaTrace N2 glucose test strips",
        "Second fictional system-specific strips.",
        "Compatible only with NovaTrace N2 meter.",
        "PH Diabetes",
        (
            variant(
                "DIA-NT-STR-50",
                "50 strips/vial",
                "26.00",
                14,
                "Limited Stock",
                strip_system="NovaTrace N2",
                package_count=50,
            ),
        ),
    ),
    product(
        "DIA",
        "DIA-009",
        "Alcohol prep pads",
        "Skin-prep consumable.",
        "Individually wrapped pads.",
        "PH Consumables",
        (
            variant("DIA-ALC-100", "100 count", "5.00", 65, "In Stock", package_count=100),
            variant("DIA-ALC-200", "200 count", "9.00", 28, "In Stock", package_count=200),
        ),
    ),
    # Diagnostics & Monitoring — 8 listings, 10 SKUs.
    product(
        "DGN",
        "DGN-001",
        "Digital thermometer",
        "Basic oral/axillary temperature device.",
        "Water-resistant body; no diagnosis or interpretation.",
        "PH Diagnostics",
        (
            variant(
                "DGN-THERM-DIG", "1 each", "13.00", 26, "In Stock", measurement_type="oral_axillary"
            ),
        ),
    ),
    product(
        "DGN",
        "DGN-002",
        "Non-contact infrared thermometer",
        "Forehead temperature device.",
        "Non-contact form factor; no diagnosis or interpretation.",
        "PH Diagnostics",
        (
            variant(
                "DGN-THERM-IR", "1 each", "39.00", 0, "Out of Stock", measurement_type="forehead"
            ),
        ),
    ),
    product(
        "DGN",
        "DGN-003",
        "Blood pressure monitor",
        "Complete home monitoring product.",
        "Automatic inflation; each SKU includes specified cuff configuration and is not "
        "a replacement cuff; no clinical interpretation.",
        "PH Diagnostics",
        (
            variant(
                "DGN-BPM-ARM",
                "complete monitor with standard upper-arm cuff",
                "46.00",
                12,
                "In Stock",
                cuff_size="standard_upper_arm",
            ),
            variant(
                "DGN-BPM-ARM-LG",
                "complete monitor with large upper-arm cuff",
                "52.00",
                6,
                "In Stock",
                cuff_size="large_upper_arm",
            ),
            variant(
                "DGN-BPM-WRIST",
                "complete monitor with wrist cuff",
                "34.00",
                7,
                "In Stock",
                cuff_size="wrist",
            ),
        ),
    ),
    product(
        "DGN",
        "DGN-004",
        "Fingertip pulse oximeter",
        "Oxygen saturation display device.",
        "Adult fingertip size; no diagnostic claims.",
        "PH Diagnostics",
        (variant("DGN-OXI-FING", "1 each", "28.00", 14, "In Stock", form="fingertip"),),
    ),
    product(
        "DGN",
        "DGN-005",
        "Basic stethoscope",
        "Non-electronic listening device.",
        "Adult-size tubing, spare eartips.",
        "PH Diagnostics",
        (variant("DGN-STETH-BASIC", "1 each", "31.00", 10, "In Stock", model="basic"),),
    ),
    product(
        "DGN",
        "DGN-006",
        "Digital bathroom scale",
        "Weight-monitoring scale.",
        "Large display, 400 lb maximum display rating.",
        "PH Diagnostics",
        (variant("DGN-SCALE-DIG", "1 each", "32.00", 6, "In Stock", display="digital"),),
    ),
    product(
        "DGN",
        "DGN-007",
        "Diagnostic penlight",
        "Inspection light.",
        "Reusable LED, pupil gauge marking; no diagnosis.",
        "PH Diagnostics",
        (variant("DGN-PENLIGHT", "1 each", "8.00", 19, "In Stock", battery_type="reusable_led"),),
    ),
    product(
        "DGN",
        "DGN-008",
        "Peak flow meter",
        "Respiratory monitoring accessory.",
        "Adult-scale meter; no treatment recommendation.",
        "PH Diagnostics",
        (variant("DGN-PEAK-ADULT", "1 each", "25.00", 5, "In Stock", form="adult"),),
    ),
    # PPE — 9 listings, 13 SKUs.
    product(
        "PPE",
        "PPE-001",
        "Nitrile exam gloves",
        "Powder-free disposable gloves.",
        "Single-use, blue, non-sterile.",
        "PH PPE",
        (
            variant(
                "PPE-NIT-S",
                "100/box",
                "11.00",
                65,
                "In Stock",
                material="nitrile",
                size="small",
                powder_free=True,
                sterile=False,
                package_count=100,
            ),
            variant(
                "PPE-NIT-M",
                "100/box",
                "11.00",
                15,
                "Limited Stock",
                material="nitrile",
                size="medium",
                powder_free=True,
                sterile=False,
                package_count=100,
            ),
            variant(
                "PPE-NIT-L",
                "100/box",
                "11.00",
                48,
                "In Stock",
                material="nitrile",
                size="large",
                powder_free=True,
                sterile=False,
                package_count=100,
            ),
        ),
    ),
    product(
        "PPE",
        "PPE-002",
        "Vinyl exam gloves",
        "Powder-free disposable gloves.",
        "Single-use, clear, non-sterile.",
        "PH PPE",
        (
            variant(
                "PPE-VIN-M",
                "100/box",
                "8.00",
                40,
                "In Stock",
                material="vinyl",
                size="medium",
                powder_free=True,
                sterile=False,
                package_count=100,
            ),
            variant(
                "PPE-VIN-L",
                "100/box",
                "8.00",
                21,
                "In Stock",
                material="vinyl",
                size="large",
                powder_free=True,
                sterile=False,
                package_count=100,
            ),
        ),
    ),
    product(
        "PPE",
        "PPE-003",
        "Procedure face masks",
        "Disposable ear-loop masks.",
        "Non-sterile; no filtration certification claim.",
        "PH PPE",
        (
            variant(
                "PPE-MASK-10", "10/box", "2.00", 40, "In Stock", package_count=10, sterile=False
            ),
            variant(
                "PPE-MASK-50", "50/box", "7.00", 75, "In Stock", package_count=50, sterile=False
            ),
        ),
    ),
    product(
        "PPE",
        "PPE-004",
        "Reusable face shield",
        "Splash-barrier face covering.",
        "Adjustable headband; no respirator claim.",
        "PH PPE",
        (variant("PPE-FSHIELD", "1 each", "6.00", 23, "In Stock", disposable=False),),
    ),
    product(
        "PPE",
        "PPE-005",
        "Isolation gown",
        "Disposable protective gown.",
        "Non-sterile, tie back, universal size.",
        "PH PPE",
        (
            variant(
                "PPE-GOWN-10",
                "10/pack",
                "19.00",
                11,
                "Limited Stock",
                size="universal",
                sterile=False,
                package_count=10,
            ),
        ),
    ),
    product(
        "PPE",
        "PPE-006",
        "Shoe covers",
        "Disposable covers.",
        "Non-slip textured material, universal size.",
        "PH PPE",
        (
            variant(
                "PPE-SHOE-100",
                "100/pack",
                "15.00",
                29,
                "In Stock",
                size="universal",
                package_count=100,
                disposable=True,
            ),
        ),
    ),
    product(
        "PPE",
        "PPE-007",
        "Bouffant caps",
        "Disposable hair covers.",
        "Universal size, non-sterile.",
        "PH PPE",
        (
            variant(
                "PPE-CAP-100",
                "100/pack",
                "9.00",
                32,
                "In Stock",
                size="universal",
                package_count=100,
                sterile=False,
            ),
        ),
    ),
    product(
        "PPE",
        "PPE-008",
        "Alcohol hand rub",
        "Portable hand sanitizer.",
        "Ethyl alcohol hand rub; label facts must be approved before display.",
        "PH Sanitation",
        (variant("PPE-HRUB-8OZ", "8 oz bottle", "4.00", 37, "In Stock", capacity="8 oz"),),
    ),
    product(
        "PPE",
        "PPE-009",
        "Barrier apron",
        "Disposable protective apron.",
        "Non-sterile, fluid-resistant description pending source approval.",
        "PH PPE",
        (
            variant(
                "PPE-APRON-100",
                "100/box",
                "18.00",
                18,
                "Limited Stock",
                package_count=100,
                sterile=False,
            ),
        ),
    ),
    # Wound Care & First Aid — 9 listings, 11 SKUs.
    product(
        "WND",
        "WND-001",
        "Sterile gauze pads",
        "Absorbent wound-cover pads.",
        "Sterile individual pads; no treatment advice.",
        "PH Wound Care",
        (
            variant(
                "WND-GAUZE-2X2",
                "25/box",
                "6.00",
                46,
                "In Stock",
                dimensions="2x2",
                sterile=True,
                package_count=25,
            ),
            variant(
                "WND-GAUZE-4X4",
                "25/box",
                "9.00",
                12,
                "Limited Stock",
                dimensions="4x4",
                sterile=True,
                package_count=25,
            ),
        ),
    ),
    product(
        "WND",
        "WND-002",
        "Rolled gauze",
        "Conforming wrap.",
        "4-inch width, stretch wrap.",
        "PH Wound Care",
        (
            variant(
                "WND-ROLL-4",
                "12/pack",
                "13.00",
                24,
                "In Stock",
                dimensions="4 inch",
                package_count=12,
            ),
        ),
    ),
    product(
        "WND",
        "WND-003",
        "Non-adherent pads",
        "Low-adherence wound-cover pads.",
        "3-inch by 4-inch pads.",
        "PH Wound Care",
        (
            variant(
                "WND-NONAD-3X4",
                "10/box",
                "7.00",
                19,
                "Limited Stock",
                dimensions="3x4",
                package_count=10,
            ),
        ),
    ),
    product(
        "WND",
        "WND-004",
        "Adhesive bandages",
        "Assorted everyday bandages.",
        "Assorted sizes, sterile pads.",
        "PH First Aid",
        (
            variant(
                "WND-BAND-100", "100/box", "8.00", 34, "In Stock", package_count=100, sterile=True
            ),
        ),
    ),
    product(
        "WND",
        "WND-005",
        "Medical tape",
        "Securing tape.",
        "Paper or cloth selection required.",
        "PH Wound Care",
        (
            variant("WND-TAPE-PAPER", "1-inch roll", "3.00", 40, "In Stock", material="paper"),
            variant("WND-TAPE-CLOTH", "1-inch roll", "4.00", 26, "In Stock", material="cloth"),
        ),
    ),
    product(
        "WND",
        "WND-006",
        "Wound cleansing spray",
        "Saline wound wash.",
        "Sterile saline spray; factual label only.",
        "PH Wound Care",
        (
            variant(
                "WND-WASH-7OZ",
                "7 oz can",
                "10.00",
                15,
                "Limited Stock",
                capacity="7 oz",
                sterile=True,
            ),
        ),
    ),
    product(
        "WND",
        "WND-007",
        "Instant cold pack",
        "Single-use cold pack.",
        "Activates on use; non-medicinal.",
        "PH First Aid",
        (variant("WND-COLD-6", "6/box", "9.00", 21, "In Stock", package_count=6, disposable=True),),
    ),
    product(
        "WND",
        "WND-008",
        "Triangular bandage",
        "Multipurpose cloth bandage.",
        "Cotton, 40-inch folded triangle.",
        "PH First Aid",
        (
            variant(
                "WND-TRI-1",
                "1 each",
                "4.00",
                17,
                "Limited Stock",
                dimensions="40 inch",
                material="cotton",
            ),
        ),
    ),
    product(
        "WND",
        "WND-009",
        "Compact first-aid kit",
        "General supplies kit.",
        "Assorted basic supplies; contents listed in product details.",
        "PH First Aid",
        (variant("WND-FAKIT-50", "1 kit", "22.00", 8, "Limited Stock", package_count=50),),
    ),
    # Medical Consumables & Sanitation — 10 listings, 11 SKUs.
    product(
        "CON",
        "CON-001",
        "Disposable underpads",
        "Absorbent bed/chair pads.",
        "30-inch by 36-inch, disposable.",
        "PH Consumables",
        (
            variant(
                "CON-UNDER-10",
                "10/pack",
                "12.00",
                0,
                "Out of Stock",
                dimensions="30x36",
                package_count=10,
                disposable=True,
            ),
            variant(
                "CON-UNDER-25",
                "25/pack",
                "26.00",
                31,
                "In Stock",
                dimensions="30x36",
                package_count=25,
                disposable=True,
            ),
        ),
    ),
    product(
        "CON",
        "CON-002",
        "Adult protective briefs",
        "Disposable absorbent briefs.",
        "Unisex, medium only; size selection required.",
        "PH Consumables",
        (
            variant(
                "CON-BRIEF-M",
                "20/pack",
                "24.00",
                14,
                "Limited Stock",
                size="medium",
                package_count=20,
                disposable=True,
            ),
        ),
    ),
    product(
        "CON",
        "CON-003",
        "Disposable washcloths",
        "Pre-moistened cloths.",
        "Fragrance-free generic description pending source approval.",
        "PH Consumables",
        (
            variant(
                "CON-WASH-48", "48/pack", "7.00", 38, "In Stock", package_count=48, disposable=True
            ),
        ),
    ),
    product(
        "CON",
        "CON-004",
        "Personal cleansing wipes",
        "Adult body wipes.",
        "Large disposable wipes; no antimicrobial claim.",
        "PH Consumables",
        (
            variant(
                "CON-WIPE-60", "60/pack", "8.00", 44, "In Stock", package_count=60, disposable=True
            ),
        ),
    ),
    product(
        "CON",
        "CON-005",
        "Emesis bags",
        "Disposable receptacle bags.",
        "Graduated, single-use bags.",
        "PH Consumables",
        (
            variant(
                "CON-EMESIS-25",
                "25/pack",
                "13.00",
                20,
                "Limited Stock",
                package_count=25,
                disposable=True,
            ),
        ),
    ),
    product(
        "CON",
        "CON-006",
        "Bedpan",
        "Reusable bedside pan.",
        "Durable plastic, standard adult size.",
        "PH Patient Care",
        (
            variant(
                "CON-BEDPAN",
                "1 each",
                "14.00",
                9,
                "Limited Stock",
                form="standard",
                disposable=False,
            ),
        ),
    ),
    product(
        "CON",
        "CON-007",
        "Male urinal",
        "Reusable bedside urinal.",
        "Spill-resistant cap, 1-liter capacity.",
        "PH Patient Care",
        (
            variant(
                "CON-URINAL-1L",
                "1 each",
                "11.00",
                12,
                "Limited Stock",
                capacity="1 liter",
                disposable=False,
            ),
        ),
    ),
    product(
        "CON",
        "CON-008",
        "Surface disinfectant spray",
        "Cleaning product.",
        "Label claims must come from approved source; "
        "no efficacy claims in assistant output without source.",
        "PH Sanitation",
        (variant("CON-DSINF-32OZ", "32 oz bottle", "8.00", 25, "In Stock", capacity="32 oz"),),
    ),
    product(
        "CON",
        "CON-009",
        "Disposable exam drapes",
        "Single-use drapes.",
        "40-inch by 60-inch.",
        "PH Consumables",
        (
            variant(
                "CON-DRAPE-25",
                "25/pack",
                "18.00",
                16,
                "Limited Stock",
                dimensions="40x60",
                package_count=25,
                disposable=True,
            ),
        ),
    ),
    product(
        "CON",
        "CON-010",
        "Absorbent spill kit",
        "General cleanup kit.",
        "Previously offered cleanup kit; absorbent pads, gloves, disposal bags; "
        "no biohazard claim.",
        "PH Sanitation",
        (
            variant(
                "CON-SPILL-1",
                "1 kit",
                "16.00",
                0,
                "Discontinued",
                lifecycle_status=CatalogLifecycleStatus.DISCONTINUED,
                package_count=1,
            ),
        ),
    ),
    # OTC & General Health — 9 listings, 10 SKUs.
    product(
        "OTC",
        "OTC-001",
        "Generic acetaminophen caplets",
        "OTC label-information product.",
        "500 mg caplets; factual label content only, no dosage recommendation.",
        "PH OTC",
        (
            variant(
                "OTC-ACET-100",
                "100 count",
                "8.00",
                27,
                "In Stock",
                form="caplet",
                strength="500 mg",
                package_count=100,
            ),
        ),
    ),
    product(
        "OTC",
        "OTC-002",
        "Generic ibuprofen tablets",
        "OTC label-information product.",
        "200 mg tablets; factual label content only, no dosage recommendation.",
        "PH OTC",
        (
            variant(
                "OTC-IBU-100",
                "100 count",
                "7.00",
                24,
                "In Stock",
                form="tablet",
                strength="200 mg",
                package_count=100,
            ),
        ),
    ),
    product(
        "OTC",
        "OTC-003",
        "Antacid chewables",
        "OTC label-information product.",
        "Assorted flavor chewables; ingredients require approved label source.",
        "PH OTC",
        (
            variant(
                "OTC-ANT-72", "72 count", "9.00", 19, "In Stock", form="chewable", package_count=72
            ),
        ),
    ),
    product(
        "OTC",
        "OTC-004",
        "Saline nasal spray",
        "Non-medicated saline product.",
        "1.5 oz spray; factual label information only.",
        "PH OTC",
        (
            variant(
                "OTC-SALINE-15",
                "1.5 oz bottle",
                "5.00",
                22,
                "In Stock",
                form="spray",
                capacity="1.5 oz",
            ),
        ),
    ),
    product(
        "OTC",
        "OTC-005",
        "Oral rehydration powder",
        "Electrolyte drink mix.",
        "8 packets; no treatment claim.",
        "PH OTC",
        (
            variant(
                "OTC-ORAL-8",
                "8 packets",
                "11.00",
                13,
                "Limited Stock",
                form="powder",
                package_count=8,
            ),
        ),
    ),
    product(
        "OTC",
        "OTC-006",
        "Cough drops",
        "Menthol lozenges.",
        "30 count; factual label information only.",
        "PH OTC",
        (
            variant(
                "OTC-COUGH-30", "30 count", "4.00", 36, "In Stock", form="lozenge", package_count=30
            ),
        ),
    ),
    product(
        "OTC",
        "OTC-007",
        "Weekly pill organizer",
        "Seven-day organizer.",
        "Seven daily compartments; no medicine included.",
        "PH OTC",
        (variant("OTC-PILL-7", "1 each", "6.00", 21, "In Stock", form="seven_day"),),
    ),
    product(
        "OTC",
        "OTC-008",
        "Reusable hot/cold compress",
        "Flexible compress.",
        "Non-medicated; size selection required.",
        "PH OTC",
        (
            variant("OTC-COMP-S", "1 each", "7.00", 18, "In Stock", size="small"),
            variant("OTC-COMP-L", "1 each", "11.00", 10, "Limited Stock", size="large"),
        ),
    ),
    product(
        "OTC",
        "OTC-009",
        "Skin moisturizer",
        "Fragrance-free lotion.",
        "12 oz bottle; cosmetic/general-care description only.",
        "PH OTC",
        (
            variant(
                "OTC-LOTION-12",
                "12 oz bottle",
                "6.00",
                23,
                "In Stock",
                form="lotion",
                capacity="12 oz",
            ),
        ),
    ),
    # Syringes & Injection Supplies — 7 listings, 10 SKUs.
    product(
        "SYR",
        "SYR-001",
        "Oral dosing syringe",
        "Needle-free measuring syringe.",
        "Oral-use only; capacity selection required.",
        "PH Syringes",
        (
            variant(
                "SYR-ORAL-1ML",
                "10/pack",
                "6.00",
                31,
                "In Stock",
                capacity_ml=1,
                use_route="oral",
                needle_included=False,
                package_count=10,
            ),
            variant(
                "SYR-ORAL-10ML",
                "10/pack",
                "9.00",
                18,
                "Limited Stock",
                capacity_ml=10,
                use_route="oral",
                needle_included=False,
                package_count=10,
            ),
        ),
    ),
    product(
        "SYR",
        "SYR-002",
        "Enteral syringe",
        "Needle-free enteral feeding syringe.",
        "Enteral-use only; capacity selection required.",
        "PH Syringes",
        (
            variant(
                "SYR-ENT-20ML",
                "10/pack",
                "14.00",
                16,
                "Limited Stock",
                capacity_ml=20,
                use_route="enteral",
                needle_included=False,
                package_count=10,
            ),
            variant(
                "SYR-ENT-60ML",
                "10/pack",
                "22.00",
                9,
                "Limited Stock",
                capacity_ml=60,
                use_route="enteral",
                needle_included=False,
                package_count=10,
            ),
        ),
    ),
    product(
        "SYR",
        "SYR-003",
        "Luer-slip syringe",
        "Needle-free syringe body.",
        "No needle included; capacity selection required.",
        "PH Syringes",
        (
            variant(
                "SYR-LS-10ML",
                "25/box",
                "18.00",
                20,
                "Limited Stock",
                capacity_ml=10,
                tip_type="luer_slip",
                needle_included=False,
                package_count=25,
            ),
            variant(
                "SYR-LS-30ML",
                "25/box",
                "29.00",
                11,
                "Limited Stock",
                capacity_ml=30,
                tip_type="luer_slip",
                needle_included=False,
                package_count=25,
            ),
        ),
    ),
    product(
        "SYR",
        "SYR-004",
        "Syringe caps",
        "Protective caps.",
        "Fits catalog-listed luer-slip syringe body only.",
        "PH Syringes",
        (
            variant(
                "SYR-CAP-LS",
                "100/pack",
                "8.00",
                33,
                "In Stock",
                tip_type="luer_slip",
                package_count=100,
            ),
        ),
    ),
    product(
        "SYR",
        "SYR-005",
        "Irrigation syringe",
        "Needle-free catheter-tip syringe.",
        "60 mL capacity, no needle included; no clinical-use recommendation.",
        "PH Syringes",
        (
            variant(
                "SYR-IRR-60ML",
                "10/pack",
                "24.00",
                14,
                "Limited Stock",
                capacity_ml=60,
                tip_type="catheter_tip",
                needle_included=False,
                package_count=10,
            ),
        ),
    ),
    product(
        "SYR",
        "SYR-006",
        "Medication measuring cup",
        "Oral liquid measure.",
        "30 mL reusable cup; no medicine included.",
        "PH Syringes",
        (
            variant(
                "SYR-CUP-30ML",
                "25/pack",
                "5.00",
                28,
                "In Stock",
                capacity_ml=30,
                use_route="oral",
                package_count=25,
            ),
        ),
    ),
    product(
        "SYR",
        "SYR-007",
        "Oral syringe adapter caps",
        "Bottle-adapter caps.",
        "For oral dosing workflow; exact bottle compatibility unknown unless verified.",
        "PH Syringes",
        (
            variant(
                "SYR-ADAPT-25",
                "25/pack",
                "12.00",
                15,
                "Limited Stock",
                use_route="oral",
                package_count=25,
            ),
        ),
    ),
)


COMPATIBILITIES: Final[tuple[CompatibilityFixture, ...]] = (
    CompatibilityFixture("DIA-GC-MTR-G1", "DIA-GC-STR-50", CompatibilityState.COMPATIBLE),
    CompatibilityFixture("DIA-GC-MTR-G1", "DIA-GC-STR-100", CompatibilityState.COMPATIBLE),
    CompatibilityFixture("DIA-GC-MTR-G1", "DIA-GC-CTRL", CompatibilityState.COMPATIBLE),
    CompatibilityFixture("DIA-NT-MTR-N2", "DIA-NT-STR-50", CompatibilityState.COMPATIBLE),
    CompatibilityFixture("DIA-CS-LDEV", "DIA-CS-LAN-30G", CompatibilityState.COMPATIBLE),
    CompatibilityFixture("DIA-CS-LDEV", "DIA-CS-LAN-33G", CompatibilityState.COMPATIBLE),
    CompatibilityFixture("DIA-GC-MTR-G1", "DIA-NT-STR-50", CompatibilityState.INCOMPATIBLE),
)

CATALOG_FIXTURE: Final[CatalogFixture] = CatalogFixture(
    categories=CATEGORIES,
    products=PRODUCTS,
    compatibilities=COMPATIBILITIES,
)
