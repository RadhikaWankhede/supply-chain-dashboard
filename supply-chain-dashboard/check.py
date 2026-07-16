import pandas as pd

df = pd.read_csv("DataCoSupplyChainDataset.csv", encoding="latin-1", nrows=0)
real = df.columns.tolist()

# the columns my script says it needs
wanted = [
    "Order Id", "Order Item Id", "Customer Id", "Product Card Id",
    "Order date (DateOrders)", "shipping date (DateOrders)",
    "Days for shipping (real)", "Days for shipment (scheduled)",
    "Delivery Status", "Late_delivery_risk", "Shipping Mode",
    "Customer Segment", "Customer City", "Customer State", "Customer Country",
    "Order City", "Order State", "Order Country", "Order Region", "Market",
    "Category Name", "Department Name", "Product Name", "Product Price",
    "Order Item Quantity", "Order Item Discount", "Order Item Product Price",
    "Order Item Total", "Order Profit Per Order", "Sales", "Type",
]

missing = [c for c in wanted if c not in real]

print("Columns my script wants but the file doesn't have:")
for c in missing:
    print("  -", repr(c))