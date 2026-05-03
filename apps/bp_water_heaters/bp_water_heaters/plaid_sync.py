from __future__ import annotations

from decimal import Decimal
from typing import Any


def plaid_transaction_to_bank_transaction(
	transaction: dict[str, Any],
	bank_account: str,
	company: str,
) -> dict[str, Any]:
	amount = Decimal(str(transaction.get("amount") or 0))
	withdrawal = amount if amount > 0 else Decimal("0")
	deposit = abs(amount) if amount < 0 else Decimal("0")
	transaction_id = transaction.get("transaction_id")
	description = transaction.get("merchant_name") or transaction.get("name") or transaction_id

	return {
		"doctype": "Bank Transaction",
		"date": transaction.get("date") or transaction.get("authorized_date"),
		"bank_account": bank_account,
		"company": company,
		"deposit": float(deposit),
		"withdrawal": float(withdrawal),
		"currency": transaction.get("iso_currency_code") or "USD",
		"description": description,
		"reference_number": transaction_id,
		"transaction_id": transaction_id,
		"transaction_type": transaction.get("payment_channel") or "Plaid",
	}


def plaid_removed_transaction_id(removed: dict[str, Any] | str) -> str | None:
	if isinstance(removed, str):
		return removed
	return removed.get("transaction_id")
