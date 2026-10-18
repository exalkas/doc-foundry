"""Seed script for template library.

This script creates all initial template library entries.
Run with: python scripts/seed_template_library.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.template_library import TemplateLibrary, TemplateCategoryEnum, ExportFormatEnum


async def seed_template_library(session: AsyncSession) -> None:
    """Seed the template library with initial templates."""
    
    templates = []

    # ===== ACCOUNTING & FINANCE =====
    
    # 1. Generic Invoice Template
    templates.append(TemplateLibrary(
        name="Generic Invoice Template",
        description="Extract key information from standard invoices including invoice number, date, amounts, and line items",
        category=TemplateCategoryEnum.ACCOUNTING_FINANCE,
        document_type="invoice",
        field_schema={
            "fields": [
                {
                    "name": "Invoice Number",
                    "json_key": "invoice_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Invoice\s*#?|Invoice\s*Number|INV\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Invoice Date",
                    "json_key": "invoice_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Date|Invoice\s*Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Due Date",
                    "json_key": "due_date",
                    "data_type": "date",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Due\s*Date|Payment\s*Due)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Bill To",
                    "json_key": "bill_to",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Bill To",
                },
                {
                    "name": "Subtotal",
                    "json_key": "subtotal",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Subtotal|Sub-total)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Tax Amount",
                    "json_key": "tax_amount",
                    "data_type": "number",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Tax|VAT|GST)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Total Amount",
                    "json_key": "total_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Amount\s*Due|Grand\s*Total)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["invoice", "billing", "accounting"],
    ))

    # 2. Generic Receipt Template
    templates.append(TemplateLibrary(
        name="Generic Receipt Template",
        description="Extract information from receipts including merchant, date, items, and total",
        category=TemplateCategoryEnum.ACCOUNTING_FINANCE,
        document_type="receipt",
        field_schema={
            "fields": [
                {
                    "name": "Merchant Name",
                    "json_key": "merchant_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Receipt Date",
                    "json_key": "receipt_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Receipt Number",
                    "json_key": "receipt_number",
                    "data_type": "string",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Receipt\s*#?|Receipt\s*Number|REF\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Total Amount",
                    "json_key": "total_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Amount)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Payment Method",
                    "json_key": "payment_method",
                    "data_type": "string",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Payment\s*Method|Paid\s*with)[:\s]*([A-Za-z\s]+)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["receipt", "expense", "accounting"],
    ))

    # 3. Expense Claim
    templates.append(TemplateLibrary(
        name="Expense Claim",
        description="Extract expense claim information including employee details, expenses, and approvals",
        category=TemplateCategoryEnum.ACCOUNTING_FINANCE,
        document_type="expense_claim",
        field_schema={
            "fields": [
                {
                    "name": "Employee Name",
                    "json_key": "employee_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Employee Name",
                },
                {
                    "name": "Employee ID",
                    "json_key": "employee_id",
                    "data_type": "string",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Employee\s*ID|Emp\s*#)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Claim Date",
                    "json_key": "claim_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Claim\s*Date|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Total Amount",
                    "json_key": "total_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Total\s*Amount)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Approver Name",
                    "json_key": "approver_name",
                    "data_type": "string",
                    "required": False,
                    "strategy": "anchor",
                    "anchor": "Approved By",
                },
            ]
        },
        default_export_format=ExportFormatEnum.EXCEL,
        tags=["expense", "claim", "accounting", "hr"],
    ))

    # 4. Supplier Invoice (with VAT)
    templates.append(TemplateLibrary(
        name="Supplier Invoice (with VAT)",
        description="Extract supplier invoice details including VAT/GST information",
        category=TemplateCategoryEnum.ACCOUNTING_FINANCE,
        document_type="supplier_invoice",
        field_schema={
            "fields": [
                {
                    "name": "Invoice Number",
                    "json_key": "invoice_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Invoice\s*#?|Invoice\s*Number)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Supplier Name",
                    "json_key": "supplier_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Invoice Date",
                    "json_key": "invoice_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Invoice\s*Date|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "VAT Number",
                    "json_key": "vat_number",
                    "data_type": "string",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:VAT\s*#?|VAT\s*Number|GST\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Subtotal (ex VAT)",
                    "json_key": "subtotal_ex_vat",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Subtotal|Sub-total)\s*(?:ex\s*VAT)?[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "VAT Amount",
                    "json_key": "vat_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:VAT|GST)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Total (inc VAT)",
                    "json_key": "total_inc_vat",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Total\s*inc\s*VAT)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["invoice", "supplier", "vat", "gst", "accounting"],
    ))

    # 5. Purchase Order
    templates.append(TemplateLibrary(
        name="Purchase Order",
        description="Extract purchase order details including PO number, items, and delivery information",
        category=TemplateCategoryEnum.ACCOUNTING_FINANCE,
        document_type="purchase_order",
        field_schema={
            "fields": [
                {
                    "name": "PO Number",
                    "json_key": "po_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:PO\s*#?|Purchase\s*Order\s*#?|P\.O\.\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "PO Date",
                    "json_key": "po_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:PO\s*Date|Date|Order\s*Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Supplier Name",
                    "json_key": "supplier_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Supplier",
                },
                {
                    "name": "Delivery Address",
                    "json_key": "delivery_address",
                    "data_type": "string",
                    "required": False,
                    "strategy": "anchor",
                    "anchor": "Delivery Address",
                },
                {
                    "name": "Total Amount",
                    "json_key": "total_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Total\s*Amount)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.EXCEL,
        tags=["purchase_order", "po", "procurement", "accounting"],
    ))

    # 6. Credit Note
    templates.append(TemplateLibrary(
        name="Credit Note",
        description="Extract credit note information including reference invoice and credit amount",
        category=TemplateCategoryEnum.ACCOUNTING_FINANCE,
        document_type="credit_note",
        field_schema={
            "fields": [
                {
                    "name": "Credit Note Number",
                    "json_key": "credit_note_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Credit\s*Note\s*#?|CN\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Credit Note Date",
                    "json_key": "credit_note_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Credit\s*Note\s*Date|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Reference Invoice",
                    "json_key": "reference_invoice",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Reference\s*Invoice|Original\s*Invoice)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Credit Amount",
                    "json_key": "credit_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Credit\s*Amount|Amount)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Reason",
                    "json_key": "reason",
                    "data_type": "string",
                    "required": False,
                    "strategy": "anchor",
                    "anchor": "Reason",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["credit_note", "refund", "accounting"],
    ))

    # ===== LOGISTICS =====

    # 7. Packing List
    templates.append(TemplateLibrary(
        name="Packing List",
        description="Extract packing list details including items, quantities, and weights",
        category=TemplateCategoryEnum.LOGISTICS,
        document_type="packing_list",
        field_schema={
            "fields": [
                {
                    "name": "Packing List Number",
                    "json_key": "packing_list_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Packing\s*List\s*#?|PL\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Date",
                    "json_key": "date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Shipper",
                    "json_key": "shipper",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Shipper",
                },
                {
                    "name": "Consignee",
                    "json_key": "consignee",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Consignee",
                },
                {
                    "name": "Total Weight",
                    "json_key": "total_weight",
                    "data_type": "number",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Total\s*Weight|Weight)[:\s]*([\d,]+\.?\d*)\s*(?:kg|lbs)?",
                },
                {
                    "name": "Total Packages",
                    "json_key": "total_packages",
                    "data_type": "integer",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Total\s*Packages|Packages)[:\s]*(\d+)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["packing_list", "shipping", "logistics"],
    ))

    # 8. CMR (Consignment Note)
    templates.append(TemplateLibrary(
        name="CMR",
        description="Extract CMR (International Road Transport) consignment note information",
        category=TemplateCategoryEnum.LOGISTICS,
        document_type="cmr",
        field_schema={
            "fields": [
                {
                    "name": "CMR Number",
                    "json_key": "cmr_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:CMR\s*#?|CMR\s*Number)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Date",
                    "json_key": "date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Sender",
                    "json_key": "sender",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Sender",
                },
                {
                    "name": "Consignee",
                    "json_key": "consignee",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Consignee",
                },
                {
                    "name": "Place of Loading",
                    "json_key": "place_of_loading",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Place of Loading",
                },
                {
                    "name": "Place of Delivery",
                    "json_key": "place_of_delivery",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Place of Delivery",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["cmr", "consignment", "road_transport", "logistics"],
    ))

    # 9. Bill of Lading
    templates.append(TemplateLibrary(
        name="Bill of Lading",
        description="Extract bill of lading details for sea freight shipments",
        category=TemplateCategoryEnum.LOGISTICS,
        document_type="bill_of_lading",
        field_schema={
            "fields": [
                {
                    "name": "B/L Number",
                    "json_key": "bl_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:B/L\s*#?|Bill\s*of\s*Lading\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Shipper",
                    "json_key": "shipper",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Shipper",
                },
                {
                    "name": "Consignee",
                    "json_key": "consignee",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Consignee",
                },
                {
                    "name": "Port of Loading",
                    "json_key": "port_of_loading",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Port of Loading",
                },
                {
                    "name": "Port of Discharge",
                    "json_key": "port_of_discharge",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Port of Discharge",
                },
                {
                    "name": "Vessel Name",
                    "json_key": "vessel_name",
                    "data_type": "string",
                    "required": False,
                    "strategy": "anchor",
                    "anchor": "Vessel",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["bill_of_lading", "bl", "sea_freight", "logistics"],
    ))

    # 10. Proforma Invoice
    templates.append(TemplateLibrary(
        name="Proforma Invoice",
        description="Extract proforma invoice details used for customs and preliminary billing",
        category=TemplateCategoryEnum.LOGISTICS,
        document_type="proforma_invoice",
        field_schema={
            "fields": [
                {
                    "name": "Proforma Invoice Number",
                    "json_key": "proforma_invoice_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Proforma\s*Invoice\s*#?|Pro\s*Forma\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Date",
                    "json_key": "date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Seller",
                    "json_key": "seller",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Seller",
                },
                {
                    "name": "Buyer",
                    "json_key": "buyer",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Buyer",
                },
                {
                    "name": "Total Amount",
                    "json_key": "total_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Total\s*Amount)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["proforma_invoice", "customs", "logistics"],
    ))

    # 11. Commercial Invoice
    templates.append(TemplateLibrary(
        name="Commercial Invoice",
        description="Extract commercial invoice details for international trade",
        category=TemplateCategoryEnum.LOGISTICS,
        document_type="commercial_invoice",
        field_schema={
            "fields": [
                {
                    "name": "Invoice Number",
                    "json_key": "invoice_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Invoice\s*#?|Commercial\s*Invoice\s*#?)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Invoice Date",
                    "json_key": "invoice_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Invoice\s*Date|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Exporter",
                    "json_key": "exporter",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Exporter",
                },
                {
                    "name": "Importer",
                    "json_key": "importer",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Importer",
                },
                {
                    "name": "Country of Origin",
                    "json_key": "country_of_origin",
                    "data_type": "string",
                    "required": False,
                    "strategy": "anchor",
                    "anchor": "Country of Origin",
                },
                {
                    "name": "Total Amount",
                    "json_key": "total_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Total\s*Amount)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["commercial_invoice", "international_trade", "logistics"],
    ))

    # ===== E-COMMERCE =====

    # 12. Amazon Seller Invoice
    templates.append(TemplateLibrary(
        name="Amazon Seller Invoice",
        description="Extract Amazon seller invoice details including order ID and marketplace fees",
        category=TemplateCategoryEnum.ECOMMERCE,
        document_type="amazon_invoice",
        field_schema={
            "fields": [
                {
                    "name": "Order ID",
                    "json_key": "order_id",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Order\s*ID|Order\s*#)[:\s]*([0-9\-]+)",
                },
                {
                    "name": "Order Date",
                    "json_key": "order_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Order\s*Date|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Buyer Name",
                    "json_key": "buyer_name",
                    "data_type": "string",
                    "required": False,
                    "strategy": "anchor",
                    "anchor": "Buyer",
                },
                {
                    "name": "Item Total",
                    "json_key": "item_total",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Item\s*Total|Subtotal)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Amazon Fees",
                    "json_key": "amazon_fees",
                    "data_type": "number",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Amazon\s*Fees|Fees)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Net Amount",
                    "json_key": "net_amount",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Net\s*Amount|Total)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.CSV,
        tags=["amazon", "marketplace", "ecommerce"],
    ))

    # 13. Shopify Order Invoice
    templates.append(TemplateLibrary(
        name="Shopify Order Invoice",
        description="Extract Shopify order invoice details including order number and line items",
        category=TemplateCategoryEnum.ECOMMERCE,
        document_type="shopify_invoice",
        field_schema={
            "fields": [
                {
                    "name": "Order Number",
                    "json_key": "order_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Order\s*#?|Order\s*Number)[:\s]*([0-9]+)",
                },
                {
                    "name": "Order Date",
                    "json_key": "order_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Order\s*Date|Date)[:\s]*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
                },
                {
                    "name": "Customer Name",
                    "json_key": "customer_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Customer",
                },
                {
                    "name": "Subtotal",
                    "json_key": "subtotal",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Subtotal)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Shipping",
                    "json_key": "shipping",
                    "data_type": "number",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Shipping|Shipping\s*Cost)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Tax",
                    "json_key": "tax",
                    "data_type": "number",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Tax)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Total",
                    "json_key": "total",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Total|Total\s*Amount)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.CSV,
        tags=["shopify", "ecommerce", "order"],
    ))

    # 14. Shipping Label (UPS/DHL/FedEx formats)
    templates.append(TemplateLibrary(
        name="Shipping Label (UPS/DHL/FedEx formats)",
        description="Extract shipping label information from major carriers including tracking numbers and addresses",
        category=TemplateCategoryEnum.ECOMMERCE,
        document_type="shipping_label",
        field_schema={
            "fields": [
                {
                    "name": "Tracking Number",
                    "json_key": "tracking_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Tracking\s*#?|Tracking\s*Number)[:\s]*([A-Z0-9]+)",
                },
                {
                    "name": "Carrier",
                    "json_key": "carrier",
                    "data_type": "string",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(UPS|DHL|FedEx|USPS)",
                },
                {
                    "name": "Ship To Address",
                    "json_key": "ship_to_address",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Ship To",
                },
                {
                    "name": "Ship From Address",
                    "json_key": "ship_from_address",
                    "data_type": "string",
                    "required": False,
                    "strategy": "anchor",
                    "anchor": "Ship From",
                },
                {
                    "name": "Weight",
                    "json_key": "weight",
                    "data_type": "number",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Weight)[:\s]*([\d,]+\.?\d*)\s*(?:kg|lbs|lb)?",
                },
                {
                    "name": "Service Type",
                    "json_key": "service_type",
                    "data_type": "string",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Service|Service\s*Type)[:\s]*([A-Za-z\s]+)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["shipping_label", "tracking", "ups", "dhl", "fedex", "ecommerce"],
    ))

    # ===== HR & LEGAL =====

    # 15. Payslip
    templates.append(TemplateLibrary(
        name="Payslip",
        description="Extract payslip information including employee details, earnings, and deductions",
        category=TemplateCategoryEnum.HR_LEGAL,
        document_type="payslip",
        field_schema={
            "fields": [
                {
                    "name": "Employee Name",
                    "json_key": "employee_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Employee Name",
                },
                {
                    "name": "Employee ID",
                    "json_key": "employee_id",
                    "data_type": "string",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Employee\s*ID|Emp\s*#)[:\s]*([A-Z0-9\-]+)",
                },
                {
                    "name": "Pay Period",
                    "json_key": "pay_period",
                    "data_type": "string",
                    "required": True,
                    "strategy": "anchor",
                    "anchor": "Pay Period",
                },
                {
                    "name": "Gross Pay",
                    "json_key": "gross_pay",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Gross\s*Pay|Gross)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Net Pay",
                    "json_key": "net_pay",
                    "data_type": "number",
                    "required": True,
                    "strategy": "regex",
                    "pattern": r"(?:Net\s*Pay|Net)[:\s]*\$?([\d,]+\.?\d*)",
                },
                {
                    "name": "Tax Deductions",
                    "json_key": "tax_deductions",
                    "data_type": "number",
                    "required": False,
                    "strategy": "regex",
                    "pattern": r"(?:Tax|Tax\s*Deductions)[:\s]*\$?([\d,]+\.?\d*)",
                },
            ]
        },
        default_export_format=ExportFormatEnum.EXCEL,
        tags=["payslip", "payroll", "hr"],
    ))

    # 16. Employment Contract (AI-based)
    templates.append(TemplateLibrary(
        name="Employment Contract (AI-based)",
        description="Extract key information from employment contracts using AI extraction",
        category=TemplateCategoryEnum.HR_LEGAL,
        document_type="employment_contract",
        field_schema={
            "fields": [
                {
                    "name": "Employee Name",
                    "json_key": "employee_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Employer Name",
                    "json_key": "employer_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Start Date",
                    "json_key": "start_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Position/Title",
                    "json_key": "position",
                    "data_type": "string",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Salary",
                    "json_key": "salary",
                    "data_type": "number",
                    "required": False,
                    "strategy": "ml",
                },
                {
                    "name": "Contract Date",
                    "json_key": "contract_date",
                    "data_type": "date",
                    "required": True,
                    "strategy": "ml",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["employment_contract", "contract", "hr", "legal", "ai"],
    ))

    # 17. ID card (OCR-only for fields)
    templates.append(TemplateLibrary(
        name="ID card (OCR-only for fields)",
        description="Extract information from ID cards including name, ID number, and dates",
        category=TemplateCategoryEnum.HR_LEGAL,
        document_type="id_card",
        field_schema={
            "fields": [
                {
                    "name": "Full Name",
                    "json_key": "full_name",
                    "data_type": "string",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "ID Number",
                    "json_key": "id_number",
                    "data_type": "string",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Date of Birth",
                    "json_key": "date_of_birth",
                    "data_type": "date",
                    "required": True,
                    "strategy": "ml",
                },
                {
                    "name": "Issue Date",
                    "json_key": "issue_date",
                    "data_type": "date",
                    "required": False,
                    "strategy": "ml",
                },
                {
                    "name": "Expiry Date",
                    "json_key": "expiry_date",
                    "data_type": "date",
                    "required": False,
                    "strategy": "ml",
                },
                {
                    "name": "Address",
                    "json_key": "address",
                    "data_type": "string",
                    "required": False,
                    "strategy": "ml",
                },
            ]
        },
        default_export_format=ExportFormatEnum.JSON,
        tags=["id_card", "identification", "ocr", "hr", "legal"],
    ))

    # Add all templates to session
    for template in templates:
        session.add(template)

    await session.flush()
    await session.commit()

    print(f"Successfully seeded {len(templates)} template library entries")


async def main():
    """Main entry point."""
    # Create async engine
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
    )

    # Create session factory
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        try:
            await seed_template_library(session)
        except Exception as e:
            print(f"Error seeding template library: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

