package com.novatech.monitoring.model;

/** Estado general de una obra o de la plataforma (secciones 17 y 18). */
public enum GeneralState {
    NORMAL("OPERACIÓN NORMAL", 0),
    ADVERTENCIA("ADVERTENCIA", 1),
    CRITICO("ESTADO CRÍTICO", 2);

    private final String label;
    private final int rank;

    GeneralState(String label, int rank) {
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
