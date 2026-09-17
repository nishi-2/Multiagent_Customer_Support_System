from __future__ import annotations

from supportcommander.db.mongo import (
    get_database,
)
from supportcommander.graph.state import (
    SupportGraphState,
)


def verify_tool_results(
    state: SupportGraphState,
) -> bool:

    db = get_database()

    results = state.get(
        "tool_results",
        [],
    )

    for result in results:

        if not result.success:
            return False

        if result.action_type == "refund":

            refund_id = (
                result.data
                or {}
            ).get(
                "refund_id"
            )

            if not refund_id:
                return False

            exists = (
                db.refunds.find_one(
                    {
                        "refund_id":
                            refund_id
                    }
                )
            )

            if exists is None:
                return False

        elif (
            result.action_type
            == "replacement"
        ):

            replacement_id = (
                result.data
                or {}
            ).get(
                "replacement_id"
            )

            if not replacement_id:
                return False

            exists = (
                db.replacements.find_one(
                    {
                        "replacement_id":
                            replacement_id
                    }
                )
            )

            if exists is None:
                return False

        elif (
            result.action_type
            == "cancel_order"
        ):

            order_id = (
                result.data
                or {}
            ).get(
                "order_id"
            )

            order = (
                db.orders.find_one(
                    {
                        "order_id":
                            order_id
                    }
                )
            )

            if (
                order is None
                or str(
                    order.get(
                        "order_status",
                        ""
                    )
                ).lower()
                != "cancelled"
            ):
                return False

    return True
