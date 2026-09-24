/**
 * Textos en espanol, tono de color e icono de cada codigo que envia el backend.
 * El color nunca va solo: siempre se muestra con icono y texto (seccion 28).
 */
import {
  AlertTriangle, Ban, Battery, BatteryCharging, BatteryLow, BatteryWarning, Camera, CameraOff, CheckCircle2,
  Circle, CircleX, Clock, Cloud, Footprints, Info, PlugZap, Radio, RefreshCw, Satellite,
  ShieldAlert, Siren, Sun, Wifi, WifiOff, Wrench, Activity, Hourglass, CheckCheck,
} from 'lucide-react'

export const SEVERITY = {
  INFO: { label: 'INFO', tone: 'info', icon: Info },
  BAJA: { label: 'BAJA', tone: 'neutral', icon: Circle },
  MEDIA: { label: 'MEDIA', tone: 'warn', icon: AlertTriangle },
  ALTA: { label: 'ALTA', tone: 'serious', icon: ShieldAlert },
  CRITICA: { label: 'CRÍTICA', tone: 'critical', icon: Siren },
}

export const ALERT_STATUS = {
  NUEVA: { label: 'NUEVA', tone: 'critical', icon: AlertTriangle },
  RECONOCIDA: { label: 'RECONOCIDA', tone: 'warn', icon: CheckCircle2 },
  EN_ATENCION: { label: 'EN ATENCIÓN', tone: 'info', icon: Wrench },
  RESUELTA: { label: 'RESUELTA', tone: 'ok', icon: CheckCheck },
}

export const INCIDENT_STATUS = {
  ABIERTA: { label: 'ABIERTA', tone: 'critical', icon: AlertTriangle },
  EN_PROCESO: { label: 'EN PROCESO', tone: 'info', icon: Wrench },
  RESUELTA: { label: 'RESUELTA', tone: 'ok', icon: CheckCircle2 },
  CERRADA: { label: 'CERRADA', tone: 'neutral', icon: CheckCheck },
}

export const DEVICE_STATUS = {
  ONLINE: { label: 'ONLINE', tone: 'ok', icon: CheckCircle2 },
  OFFLINE: { label: 'OFFLINE', tone: 'critical', icon: CircleX },
  MANTENIMIENTO: { label: 'MANTENIMIENTO', tone: 'neutral', icon: Wrench },
  FALLA: { label: 'FALLA', tone: 'critical', icon: AlertTriangle },
}

export const SITE_STATUS = {
  ACTIVA: { label: 'ACTIVA', tone: 'ok', icon: CheckCircle2 },
  MANTENIMIENTO: { label: 'MANTENIMIENTO', tone: 'neutral', icon: Wrench },
  SIN_CONEXION: { label: 'SIN CONEXIÓN', tone: 'critical', icon: WifiOff },
}

export const GENERAL_STATE = {
  NORMAL: { label: 'OPERACIÓN NORMAL', tone: 'ok', icon: CheckCircle2 },
  ADVERTENCIA: { label: 'ADVERTENCIA', tone: 'warn', icon: AlertTriangle },
  CRITICO: { label: 'ESTADO CRÍTICO', tone: 'critical', icon: Siren },
}

export const CONNECTION = {
  STARLINK: { label: 'STARLINK', long: 'CONEXIÓN ACTIVA: STARLINK', tone: 'ok', icon: Satellite },
  CELLULAR_4G: { label: '4G DE RESPALDO', long: 'CONEXIÓN ACTIVA: 4G DE RESPALDO', tone: 'warn', icon: Radio },
  NONE: { label: 'SIN CONEXIÓN', long: 'SIN CONEXIÓN', tone: 'critical', icon: WifiOff },
}

export const BATTERY_LEVEL = {
  NORMAL: { label: 'NORMAL', tone: 'ok', icon: Battery },
  BAJA: { label: 'BAJA', tone: 'warn', icon: BatteryLow },
  CRITICA: { label: 'CRÍTICA', tone: 'critical', icon: BatteryWarning },
}

export const BATTERY_TREND = {
  CARGANDO: { label: 'CARGANDO', tone: 'ok', icon: BatteryCharging },
  'CARGA COMPLETA': { label: 'CARGA COMPLETA', tone: 'ok', icon: BatteryCharging },
  DESCARGANDO: { label: 'DESCARGANDO', tone: 'neutral', icon: Battery },
  ESTABLE: { label: 'ESTABLE', tone: 'neutral', icon: Battery },
}

export const COMMAND_STATUS = {
  PENDIENTE: { label: 'PENDIENTE', tone: 'warn', icon: Hourglass },
  ENVIADO: { label: 'ENVIADO', tone: 'info', icon: Activity },
  EJECUTADO: { label: 'EJECUTADO', tone: 'ok', icon: CheckCircle2 },
  ERROR: { label: 'ERROR', tone: 'critical', icon: CircleX },
  EXPIRADO: { label: 'EXPIRADO', tone: 'neutral', icon: Clock },
}

export const ROLE = {
  ADMINISTRADOR: { label: 'Administrador', tone: 'info', icon: ShieldAlert },
  SUPERVISOR: { label: 'Supervisor', tone: 'ok', icon: CheckCircle2 },
  OPERADOR: { label: 'Operador', tone: 'neutral', icon: Circle },
}

export const DEVICE_TYPE = {
  CAMERA: { label: 'Cámara', icon: Camera },
  SOLAR_PANEL: { label: 'Panel solar', icon: Sun },
  BATTERY: { label: 'Batería', icon: Battery },
  STARLINK: { label: 'Starlink', icon: Satellite },
  CELLULAR_4G: { label: 'Módem 4G', icon: Radio },
}

export const EVENT_TYPE = {
  MOTION_DETECTED: { label: 'Movimiento detectado', icon: Footprints },
  INTRUSION_DETECTED: { label: 'Intrusión detectada', icon: Siren },
  CAMERA_OFFLINE: { label: 'Cámara desconectada', icon: CameraOff },
  CAMERA_RESTORED: { label: 'Cámara recuperada', icon: Camera },
  BATTERY_LOW: { label: 'Batería baja', icon: BatteryLow },
  BATTERY_CRITICAL: { label: 'Batería crítica', icon: BatteryWarning },
  STARLINK_DOWN: { label: 'Starlink desconectado', icon: WifiOff },
  STARLINK_RESTORED: { label: 'Starlink recuperado', icon: Satellite },
  CELLULAR_ACTIVATED: { label: '4G activado', icon: Radio },
  CELLULAR_DOWN: { label: '4G desconectado', icon: WifiOff },
  CELLULAR_RESTORED: { label: '4G recuperado', icon: Wifi },
  CONNECTIVITY_LOST: { label: 'Obra sin conectividad', icon: Ban },
  LOW_SOLAR_GENERATION: { label: 'Baja generación solar', icon: Cloud },
  SOLAR_PANEL_FAILURE: { label: 'Falla panel solar', icon: PlugZap },
  DEVICE_MAINTENANCE: { label: 'Dispositivo en mantenimiento', icon: Wrench },
  SYSTEM_RESTORED: { label: 'Sistema restaurado', icon: RefreshCw },
}

export const ALERT_TYPE = {
  INTRUSION: 'Intrusión',
  CAMERA_OFFLINE: 'Cámara desconectada',
  BATTERY_LOW: 'Batería baja',
  BATTERY_CRITICAL: 'Batería crítica',
  STARLINK: 'Starlink caído',
  CONNECTIVITY: 'Sin conectividad',
  SOLAR_PANEL: 'Falla panel solar',
}

export const METRIC = {
  battery_percent: 'Batería (%)',
  battery_voltage: 'Voltaje (V)',
  consumption: 'Consumo (W)',
  solar_generation: 'Generación solar (W)',
  online: 'En línea (1 = sí, 0 = no)',
  latency: 'Latencia (ms)',
  signal: 'Señal (%)',
}

export const SCENE_OPTIONS = [
  { value: 'acceso', label: 'Acceso / portón' },
  { value: 'perimetro', label: 'Perímetro / cerco' },
  { value: 'materiales', label: 'Zona de materiales' },
  { value: 'vehicular', label: 'Acceso vehicular' },
  { value: 'grua', label: 'Grúa torre' },
  { value: 'maquinaria', label: 'Maquinaria' },
]

/** Busca la etiqueta de un codigo en un mapa; si no existe devuelve el codigo. */
export function labelOf(map, code) {
  return map[code]?.label ?? code ?? '—'
}

