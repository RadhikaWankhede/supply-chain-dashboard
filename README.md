# Supply Chain & Shipment Analytics

![Dashboard](screenshots/dashboard.png)

**42.7% of DataCo's 65,752 shipments arrive on time.** That rate is flat across three years, identical across all five global markets, and unmoved by a 15% rise in volume. The only thing that separates good performance from bad is shipping mode — and the pattern runs backwards from what you'd expect.

An end-to-end analytics project: Python ETL → dimensional model → Power BI.

---

## The finding

| Shipping Mode | Promised | Actual Avg | On-Time % | Shipments |
|---|---|---|---|---|
| Standard Class | 4 days | 4.00 | **60.2%** | 39,324 |
| Same Day | 0 days | 0.48 | 52.1% | 3,571 |
| Second Class | 2 days | 3.99 | 20.2% | 12,778 |
| First Class | 1 day | 2.00 | **—** | 10,079 |

**The faster the promised service, the worse they hit it.** Standard Class gets four days of slack and clears it three times out of five. Second Class promises two days and takes four.

First Class returns *blank*, not zero — meaning the measure found no matching rows at all. Across 10,079 shipments, not one is flagged on-time. Nothing operational is that consistent, which points at the scheduled window rather than the shipping itself.

**Three explanations ruled out along the way:**

- **Seasonality** — the rate is flat across 37 months
- **Geography** — all five markets sit within one point of each other (42–43%)
- **Capacity** — volume rose ~15% in late 2017 and the rate didn't move

What's left is systemic: the delivery promises are unrealistic, and they get more unrealistic the faster the service tier.

---

## Architecture

```
DataCoSupplyChainDataset.csv     180,519 rows × 53 cols, latin-1
        │
        ▼
etl_supply_chain.py              extract → transform → validate → load
        │
        ├──► shipments_clean.csv          flat analysis table
        └──► star_schema/                 6 modelled tables
                    │
                    ▼
        supply_chain_dashboard.pbix       DAX measures + visuals
```

### Data model

![Star schema](screenshots/model.png)

A Kimball star. One fact table, five dimensions, all relationships one-to-many with single-direction filtering.

| Table | Rows | Role |
|---|---|---|
| `fact_shipments` | 180,519 | Grain: one product line item per order |
| `dim_customer` | 20,652 | Segment, city, state, country |
| `dim_product` | 118 | Name, category, department, list price |
| `dim_geography` | 3,772 | Destination market → region → country → state |
| `dim_shipping` | 12 | Mode, delivery status |
| `dim_date` | 1,127 | Contiguous calendar, marked as date table |

**Why not one flat table?** Three reasons that matter in practice:

1. **Compression.** VertiPaq stores column-wise. `"Western Europe"` lives once in a dimension with an integer key in the fact table, rather than repeating across tens of thousands of rows.
2. **Time intelligence needs it.** `DATEADD` and `TOTALYTD` walk a calendar day by day. Sourcing dates from the fact table leaves gaps on days with no orders — and those functions then return wrong answers *without erroring*. `dim_date` is contiguous across all 1,127 days for exactly this reason.
3. **Predictable filter context.** One-to-many, single-direction relationships mean filters flow one way only: dimension → fact. That makes DAX behave predictably.

---

## The ETL

```bash
pip install pandas numpy
python etl_supply_chain.py --input DataCoSupplyChainDataset.csv --outdir data/processed
```

Structured as extract / transform / load, with the transform stage built from small single-purpose functions chained via `.pipe()` — each independently testable.

**Missing-value policy** — deliberate per column, not a blanket `dropna()`:

| Situation | Choice | Why |
|---|---|---|
| Missing business key | Drop row | Unjoinable |
| Missing `ship_date` | Keep as `NaT` | The null *is* information — never shipped |
| Missing quantity | Fill `1` | A line item implies ≥1 unit |
| Missing monetary value | Fill `0` | Absent revenue is genuinely zero for aggregation |
| Missing category text | Fill `"Unknown"` | Stays visible in slicers rather than vanishing |

Dropping rows with null ship dates would have silently inflated the on-time rate by removing the worst outcomes from the denominator.

**Engineered fields:** delivery duration, schedule variance, on-time / late / delivered flags, gross and net revenue, line cost, cost per unit, margin, discount rate, date parts, and binned speed/value bands.

**Validation** — the pipeline asserts grain uniqueness, binary flag domains, and positive quantities, and fails loudly rather than passing bad data downstream. On the real file it reported 0 duplicates and 0 rows dropped: the dataset is cleaner than expected, and the checks are what establish that rather than assume it.

---

## Key DAX

```dax
Total Shipments = DISTINCTCOUNT(fact_shipments[order_id])
```
Grain matters. The fact table holds one row per *line item*, so a three-product order is three rows but one shipment. `COUNTROWS` would report 180,519; the truth is 65,752.

```dax
On-Time Delivery % =
VAR DeliveredOrders =
    CALCULATE(COUNTROWS(fact_shipments), fact_shipments[is_delivered] = 1)
VAR OnTimeOrders =
    CALCULATE(
        COUNTROWS(fact_shipments),
        fact_shipments[is_delivered] = 1,
        fact_shipments[is_on_time] = 1
    )
RETURN
    DIVIDE(OnTimeOrders, DeliveredOrders, 0)
```
Cancelled orders are excluded from **both** numerator and denominator — a cancelled shipment was never late, it never happened, and leaving it in the denominator would understate real performance. `DIVIDE` over `/` handles division by zero without erroring.

The on-time flag is derived independently from actual vs. scheduled days rather than read from the source `Delivery Status` column. Both agree, which is the point of computing it twice.

```dax
Avg Cost Per Unit =
DIVIDE(SUM(fact_shipments[line_cost]), SUM(fact_shipments[quantity]), 0)
```
A weighted average — total cost over total units — not `AVERAGE(cost_per_unit)`, which would average the averages and treat a 1-unit line as equal in weight to a 500-unit line.

---

## Dashboard

- **KPI cards** — total shipments, avg delivery time, on-time %, total cost, total profit
- **Trend** — monthly volume as columns against on-time % as a line, secondary axis fixed to 0–100% so the flatness reads honestly
- **Breakdowns** — on-time by market, revenue by category (Top 10)
- **Slicers** — shipping mode, segment, department, date range
- **Drill-down** — market → region → country

---

## Repo

```
├── etl_supply_chain.py          # the pipeline
├── screenshots/                 # dashboard, model, findings
├── supply_chain_dashboard.pbix  # Power BI file
└── data/                        # gitignored — regenerate with the ETL
```

Data isn't committed. Download `DataCoSupplyChainDataset.csv` from [Kaggle](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis), drop it in the project root, and run the ETL.

---

## What I'd do next

- **Incremental refresh** rather than a full 180k-row reload
- **Row-level security** so regional managers see only their own market
- **A returns fact table** sharing the same date and product dimensions — the case for conformed dimensions
- **Unit tests** on the transform functions
- **Confirm the First Class hypothesis** — check whether `days_shipping_scheduled` is genuinely always 1 for that tier, or a data-entry default

---

**Dataset:** [DataCo Smart Supply Chain](https://www.kaggle.com/datasets/shashwatwork/dataco-smart-supply-chain-for-big-data-analysis) · **Stack:** Python (Pandas, NumPy), Power BI, DAX
