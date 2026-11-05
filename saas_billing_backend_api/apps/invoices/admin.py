from django.contrib import admin
from .models import Invoice, InvoiceItem, Payment


class InvoiceItemInline(admin.TabularInline):
    """Allows viewing and editing invoice items directly inside the Invoice page."""
    model = InvoiceItem
    extra = 1  # Number of empty rows to display by default
    fields = ["description", "quantity", "unit_price", "amount"]
    readonly_fields = ["amount"]  # Since amount is automatically calculated on save


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    # Columns displayed in the list view page
    list_display = [
        "invoice_number", 
        "organization", 
        "status", 
        "issue_date", 
        "total", 
        "currency"
    ]
    
    # Clickable filters on the right sidebar
    list_filter = ["status", "currency", "issue_date", "created_at"]
    
    # Search bar configurations
    search_fields = ["invoice_number", "organization__name", "billing_email", "stripe_invoice_id"]
    
    # Makes the auto-calculated fields view-only in the form layout
    readonly_fields = ["id", "created_at", "updated_at"]
    
    # Attaches invoice items to the bottom of the invoice form view
    inlines = [InvoiceItemInline]
    
    # Organizes the detail form layout into clean sections
    fieldsets = [
        ("Invoice Metadata", {
            "fields": ["id", "invoice_number", "organization", "status"]
        }),
        ("Dates & Billing", {
            "fields": ["issue_date", "due_date", "billing_email", "stripe_invoice_id"]
        }),
        ("Financials", {
            "fields": ["currency", "subtotal", "tax", "total"]
        }),
        ("Timestamps", {
            "fields": ["created_at", "updated_at"],
            "classes": ["collapse"]  # Hides this section by default under a dropdown click
        }),
    ]


@admin.register(InvoiceItem)
class InvoiceItemAdmin(admin.ModelAdmin):
    list_display = ["description", "invoice", "quantity", "unit_price", "amount"]
    search_fields = ["description", "invoice__invoice_number"]
    readonly_fields = ["amount"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "paid_at",
        "organization",
        "amount",
        "currency",
        "method",
        "status",
        "invoice",
    ]
    list_filter = ["method", "status", "currency", "paid_at"]
    search_fields = [
        "organization__name",
        "invoice__invoice_number",
        "stripe_invoice_id",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
    ]
    readonly_fields = [
        "id",
        "organization",
        "invoice",
        "amount",
        "currency",
        "method",
        "stripe_invoice_id",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "recorded_by",
        "paid_at",
        "created_at",
    ]
