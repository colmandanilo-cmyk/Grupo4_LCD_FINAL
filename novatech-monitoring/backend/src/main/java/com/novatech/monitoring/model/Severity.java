package com.novatech.monitoring.model;

/**
 * Severidad de eventos y alertas, y prioridad de incidencias.
 * El valor "rank" permite comparar: mayor rank = mas grave.
 */
public enum Severity {
    INFO("INFO", 0),
    BAJA("BAJA", 1),
    MEDIA("MEDIA", 2),
    ALTA("ALTA", 3),
    CRITICA("CRÍTICA", 4);

    private final String label;
    private final int rank;

    Severity(String label, int rank) {
        this.label = label;
        this.rank = rank;
    }

    public String label() {
        return label;
    }

    public int rank() {
        return rank;
    }
}
