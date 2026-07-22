"""Read-only Phase 1 CSV export page."""

import streamlit as st

from app.database.session import session_scope
from app.services.analytics_service import AnalyticsService
from app.services.export_service import EXPORT_MODELS, export_csv
from app.ui.formatting import page_header


def render(business_id: int, currency_code: str) -> None:
    del currency_code
    page_header(
        "Data Export",
        "Download portable CSV copies of Phase 1 operating records and the current analytics summary.",
        "Data portability",
    )
    with session_scope() as session:
        payloads = {name: export_csv(session, name, business_id) for name in EXPORT_MODELS}
        payloads["analytics_summary"] = AnalyticsService(session).summary_csv(business_id)
    columns = st.columns(4)
    for index, (name, payload) in enumerate(payloads.items()):
        columns[index % 4].download_button(
            label=name.replace("_", " ").title(),
            data=payload,
            file_name=f"fieldops_{name}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    st.caption(
        "Exports can contain customer contact details. Store downloaded files securely. CSV import is intentionally deferred."
    )
