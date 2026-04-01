# service/app/queries/definitions/sales.py
"""Sales-related pre-defined SQL queries."""

SALES_QUERIES = {
    "top_customers_by_revenue": {
        "description": "Find the top N customers ranked by total revenue within a date range. Use when user asks about best customers, highest revenue, or top buyers.",
        "sql": """
            SELECT bp.Name, bp.TaxID, SUM(ol.LineNetAmt) as Revenue,
                   COUNT(DISTINCT o.C_Order_ID) as OrderCount
            FROM C_OrderLine ol
            JOIN C_Order o ON o.C_Order_ID = ol.C_Order_ID
            JOIN C_BPartner bp ON bp.C_BPartner_ID = o.C_BPartner_ID
            WHERE o.DateOrdered BETWEEN %(date_from)s AND %(date_to)s
              AND o.DocStatus IN ('CO','CL')
              AND o.AD_Client_ID = %(ad_client_id)s
              AND o.AD_Org_ID = ANY(%(org_ids)s)
            GROUP BY bp.Name, bp.TaxID
            ORDER BY Revenue DESC
            LIMIT %(limit)s
        """,
        "params": ["date_from", "date_to", "ad_client_id", "org_ids", "limit"],
        "pii_columns": ["name", "taxid"],
    },
    "order_status_by_documentno": {
        "description": "Look up a specific order by its document number. Use when user asks about order status, order details, or references a document number.",
        "sql": """
            SELECT o.DocumentNo, o.DateOrdered, o.DocStatus,
                   o.GrandTotal, bp.Name, o.Description
            FROM C_Order o
            JOIN C_BPartner bp ON bp.C_BPartner_ID = o.C_BPartner_ID
            WHERE o.DocumentNo = %(document_no)s
              AND o.AD_Client_ID = %(ad_client_id)s
              AND o.AD_Org_ID = ANY(%(org_ids)s)
        """,
        "params": ["document_no", "ad_client_id", "org_ids"],
        "pii_columns": ["name"],
    },
    "monthly_revenue_summary": {
        "description": "Get monthly revenue summary for a given year. Use when user asks about monthly trends, revenue over time, or yearly performance.",
        "sql": """
            SELECT TO_CHAR(o.DateOrdered, 'YYYY-MM') as Month,
                   SUM(o.GrandTotal) as Revenue,
                   COUNT(*) as OrderCount
            FROM C_Order o
            WHERE EXTRACT(YEAR FROM o.DateOrdered) = %(year)s
              AND o.DocStatus IN ('CO','CL')
              AND o.AD_Client_ID = %(ad_client_id)s
              AND o.AD_Org_ID = ANY(%(org_ids)s)
            GROUP BY TO_CHAR(o.DateOrdered, 'YYYY-MM')
            ORDER BY Month
        """,
        "params": ["year", "ad_client_id", "org_ids"],
        "pii_columns": [],
    },
}
