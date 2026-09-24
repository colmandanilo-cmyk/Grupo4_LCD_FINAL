package com.novatech.monitoring.dto;

import java.util.List;

/** Respuesta paginada: items de la pagina, numero de pagina (desde 0), tamano y total. */
public record PageResponse<T>(List<T> items, int page, int size, long total) {
}
