package com.novatech.monitoring.dto;

import java.time.LocalDateTime;
import java.util.List;

/**
 * Salida de /api/reports. Todos los reportes tienen la misma forma:
 * indicadores de resumen y una tabla (columnas + filas), que tambien se exporta a CSV.
 */
public final class ReportDtos {

    private ReportDtos() {
    }

    public record SummaryItem(String label, String value) {
    }

    public record ReportResult(
            String type,
            String title,
            LocalDateTime from,
            LocalDateTime to,
            LocalDateTime generatedAt,
            List<SummaryItem> summary,
            List<String> columns,
            List<List<Object>> rows) {
    }
}
