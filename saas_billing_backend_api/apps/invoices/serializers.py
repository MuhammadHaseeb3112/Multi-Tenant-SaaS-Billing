from decimal import Decimal
from django.db import transaction
from rest_framework import serializers

from .models import Invoice, InvoiceItem, Payment



class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = (
            "id",
            "description",
            "quantity",
            "unit_price",
            "amount",
        )
        read_only_fields = (
            "id",
            "amount",
        )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Quantity must be greater than zero."
            )
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Unit price cannot be negative."
            )
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(
        many=True,
        required=False,
    )

    class Meta:
        model = Invoice
        fields = (
            "id",
            "organization",
            "invoice_number",
            "status",
            "issue_date",
            "due_date",
            "currency",
            "subtotal",
            "tax",
            "total",
            "billing_email",
            "stripe_invoice_id",
            "items",
            "created_at",
            "updated_at",
        )

        read_only_fields = (
            "id",
            "organization",
            "invoice_number",
            "subtotal",
            "total",
            "stripe_invoice_id",
            "created_at",
            "updated_at",
        )



    # Fields that may only change while an invoice is still a DRAFT.
    # Once an invoice is sent (OPEN) or closed, its money fields are
    # final; only the status may move forward.
    DRAFT_ONLY_FIELDS = (
        "issue_date",
        "due_date",
        "currency",
        "tax",
        "billing_email",
        "items",
    )

    def validate_tax(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Tax cannot be negative."
            )
        return value

    def validate(self, attrs):
        if self.instance is None:
            # New invoices always start as DRAFT. Without this a client
            # could create an invoice that is already PAID.
            requested_status = attrs.get(
                "status",
                Invoice.Status.DRAFT,
            )

            if requested_status != Invoice.Status.DRAFT:
                raise serializers.ValidationError(
                    {
                        "status": (
                            "New invoices must be created as DRAFT."
                        )
                    }
                )

            return attrs

        if self.instance.status != Invoice.Status.DRAFT:
            locked = [
                field
                for field in self.DRAFT_ONLY_FIELDS
                if field in attrs
            ]

            if locked:
                raise serializers.ValidationError(
                    {
                        field: (
                            f"Cannot be changed on a "
                            f"{self.instance.status} invoice. "
                            f"Only DRAFT invoices can be edited."
                        )
                        for field in locked
                    }
                )

        return attrs

    def validate_status(self, value):
        if not self.instance:
            return value

        current_status = self.instance.status

        # Same status is harmless/idempotent
        if current_status == value:
            return value

        allowed_transitions = {
            Invoice.Status.DRAFT: {
                Invoice.Status.OPEN,
            },
            Invoice.Status.OPEN: {
                Invoice.Status.PAID,
                Invoice.Status.VOID,
                Invoice.Status.UNCOLLECTIBLE,
            },
            Invoice.Status.PAID: set(),
            Invoice.Status.VOID: set(),
            Invoice.Status.UNCOLLECTIBLE: set(),
        }

        allowed = allowed_transitions.get(current_status, set())

        if value not in allowed:
            raise serializers.ValidationError(
                f"Cannot change invoice status from "
                f"{current_status} to {value}."
            )

        return value

    @transaction.atomic
    def create(self, validated_data):
        items_data = validated_data.pop("items", [])

        organization = validated_data.pop("organization")

        # Lock the organization so two simultaneous invoice
        # creations cannot generate the same invoice number.
        organization = (
            organization.__class__.objects
            .select_for_update()
            .get(pk=organization.pk)
        )

        last_invoice = (
            Invoice.objects
            .filter(
                organization=organization,
                invoice_number__startswith="INV-",
            )
            .order_by("-created_at")
            .first()
        )

        if last_invoice:
            try:
                last_number = int(
                    last_invoice.invoice_number.split("-")[-1]
                )
            except ValueError:
                last_number = 0
        else:
            last_number = 0

        invoice_number = f"INV-{last_number + 1:06d}"

        invoice = Invoice.objects.create(
            organization=organization,
            invoice_number=invoice_number,
            **validated_data,
        )

        subtotal = Decimal("0.00")

        for item_data in items_data:
            item = InvoiceItem.objects.create(
                invoice=invoice,
                **item_data,
            )

            subtotal += item.amount

        invoice.subtotal = subtotal
        invoice.total = subtotal + invoice.tax

        invoice.save(
            update_fields=[
                "subtotal",
                "total",
                "updated_at",
            ]
        )

        return invoice
    @transaction.atomic
    def update(self, instance, validated_data):
        """
        Update an invoice.

        For DRAFT invoices, items may be replaced and subtotal/total are
        always recalculated (previously changing ``tax`` left ``total``
        stale). Non-draft invoices only reach here with a status change
        (see ``validate``), so their amounts are never touched.
        """

        was_draft = instance.status == Invoice.Status.DRAFT

        items_data = validated_data.pop("items", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        if items_data is not None:
            instance.items.all().delete()

            for item_data in items_data:
                InvoiceItem.objects.create(
                    invoice=instance,
                    **item_data,
                )

        if was_draft:
            subtotal = sum(
                (item.amount for item in instance.items.all()),
                Decimal("0.00"),
            )

            instance.subtotal = subtotal
            instance.total = subtotal + instance.tax

            instance.save(
                update_fields=[
                    "subtotal",
                    "total",
                    "updated_at",
                ]
            )

        return instance


class PaymentSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(
        source="invoice.invoice_number",
        read_only=True,
        default=None,
    )

    recorded_by_email = serializers.EmailField(
        source="recorded_by.email",
        read_only=True,
        default=None,
    )

    class Meta:
        model = Payment
        fields = (
            "id",
            "invoice",
            "invoice_number",
            "amount",
            "currency",
            "method",
            "status",
            "description",
            "recorded_by_email",
            "paid_at",
            "created_at",
        )
        read_only_fields = fields
