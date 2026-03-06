from __future__ import annotations

import streamlit as st

from kartencrop.ui_actions import run_build, run_preview
from kartencrop.ui_bbox_picker import render_interactive_bbox_selector
from kartencrop.ui_persistence import persist_ui_state
from kartencrop.ui_render import prepare_output_name, render_source_configuration, render_summary
from kartencrop.ui_shared import (
    SOURCE_GEOPF,
    SOURCE_HINTS,
    SOURCE_LABELS,
    SOURCE_OFM,
    SOURCE_OPENAIP,
    SOURCE_SWISS,
    ensure_source_state,
    ensure_output_filename,
    init_state,
    render_output_sidebar,
    resolve_output_path,
    section_header,
)


st.set_page_config(page_title="Kartencrop", layout="wide")


def main() -> None:
    init_state()

    st.title("Kartencrop")
    st.write(
        "Waehle die Kartenquelle und den Bereich. Die Seite zeigt nur die dazu passenden Einstellungen."
    )

    with st.sidebar:
        available_sources = [SOURCE_OFM, SOURCE_GEOPF, SOURCE_SWISS, SOURCE_OPENAIP]
        if st.session_state.get("ui_source") not in available_sources:
            st.session_state["ui_source"] = SOURCE_OFM
        source = st.selectbox(
            "Kartenquelle",
            available_sources,
            format_func=lambda value: SOURCE_LABELS[value],
            key="ui_source",
            help="Jede Quelle verwendet eigene Karten, Zoomstufen und Bereichslogik.",
        )
        st.checkbox(
            "Expertenmodus",
            key="ui_expert_mode",
            help="Zeigt technische Tile-Modi und Zusatzoptionen.",
        )
    ensure_source_state(st.session_state, source)
    render_output_sidebar()

    st.subheader(SOURCE_LABELS[source])
    st.info(SOURCE_HINTS[source])
    render_interactive_bbox_selector(source)

    config = render_source_configuration(source)

    section_header("Speicherziel", "Dateiname hier, Ausgabeordner links.")
    suggested_name = prepare_output_name(config)
    output_filename = ensure_output_filename(source, suggested_name)
    output_path = resolve_output_path(st.session_state.output_directory, output_filename or suggested_name)

    render_summary(config, output_path)

    preview_col, build_col = st.columns(2)
    preview_clicked = preview_col.button(
        "Vorschau laden",
        use_container_width=True,
        help="Laedt den aktuellen Bereich und zeigt ihn direkt an.",
    )
    build_clicked = build_col.button(
        "Karte speichern",
        use_container_width=True,
        help="Speichert die Karte im gewaehlten Ausgabeordner.",
    )

    try:
        if preview_clicked:
            with st.spinner("Erzeuge Vorschau..."):
                run_preview(config)
        if build_clicked:
            with st.spinner("Erzeuge Karte..."):
                run_build(config, output_path)
    except ValueError as exc:
        st.error(str(exc))
        if source == SOURCE_OFM:
            st.info("OFM hat eine unregelmaessige Abdeckung mit internen Luecken.")
        elif source == SOURCE_GEOPF:
            st.info("GeoPF benoetigt gueltige Werte innerhalb der Frankreich-Abdeckung.")
        elif source == SOURCE_SWISS:
            st.info("GeoAdmin WMS benoetigt eine gueltige Bounding-Box und mindestens einen Layer.")
        else:
            st.info("OpenAIP benoetigt einen API-Schluessel und gueltige Tiles fuer die aktuelle Zoomstufe.")

    st.markdown("---")
    st.write(
        "OFM hat regionale Abdeckung mit Luecken. GeoPF ist auf Frankreich begrenzt. Schweizer Karten werden direkt per Bounding-Box gerendert. OpenAIP berechnet den Bereich je Zoomstufe neu."
    )
    persist_ui_state(st.session_state)


if __name__ == "__main__":
    main()
