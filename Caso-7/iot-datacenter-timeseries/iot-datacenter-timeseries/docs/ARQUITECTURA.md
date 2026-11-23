# Arquitectura del proyecto

## Visión general

SQLite es la **fuente de verdad** (series temporales, reglas de negocio y reportes). A partir de ella se
construyen dos vistas derivadas: un **almacén de documentos** (NoSQL) y un **grafo** de la topología. Las aplicaciones
externas (colectores IoT, tablero del NOC) acceden a todo mediante una **API REST**, que no duplica lógica: las reglas
de negocio viven en la base y la API solo traduce sus errores a códigos HTTP.

```mermaid
flowchart LR
    S[Sensores IoT<br/>colectores] -->|HTTP JSON| API[API REST<br/>FastAPI]
    NOC[Tablero NOC<br/>scripts y apps] -->|HTTP JSON| API
    API -->|conexion| DB[(SQLite<br/>serie temporal)]
    DB -->|triggers RN1-RN6| AL[Alarmas e incidencias]
    DB -->|downsampling| RS[Resumen horario]
    DB -->|desnormaliza| DOC[(Documentos JSON<br/>estilo MongoDB)]
    DB -->|nodos y relaciones| GR[(Grafo<br/>networkx / GraphML)]
    AL --> API
    DOC --> API
    GR --> API
```

## Modelo relacional

```mermaid
erDiagram
    sensor_iot ||--o{ lectura_telemetria : registra
    lectura_telemetria ||--o| alarma : origina
    alarma ||--o| incidencia_noc : abre
    sensor_iot ||--o{ resumen_horario : resume
    rack_pasillo |o..o{ sensor_iot : "ubica (relacion logica por rack)"

    sensor_iot {
        TEXT id_sensor PK
        TEXT rack_ubicacion
        TEXT tipo_metrica
        REAL umbral_limite
        TEXT estado_operativo
    }
    lectura_telemetria {
        TEXT id_sensor PK
        INTEGER timestamp_lectura PK
        REAL valor_metrica
        TEXT nivel_alerta
    }
    alarma {
        INTEGER id_alarma PK
        TEXT id_sensor FK
        INTEGER timestamp_lectura FK
        TEXT severidad
        REAL valor_metrica
    }
    incidencia_noc {
        INTEGER id_incidencia PK
        INTEGER id_alarma FK
        TEXT estado
        TEXT responsable
    }
    resumen_horario {
        TEXT id_sensor PK
        INTEGER hora_epoch PK
        REAL promedio
        REAL minimo
        REAL maximo
        INTEGER n_lecturas
    }
    rack_pasillo {
        TEXT rack_ubicacion PK
        TEXT pasillo
    }
```

`rack_pasillo` se relaciona con `sensor_iot` solo de forma **lógica** (sin llave foránea). Es deliberado: así los
ejemplos de RIGHT y FULL JOIN pueden mostrar racks sin sensores y sensores sin pasillo.

## Topología del grafo

```mermaid
flowchart TD
    DC[DC_Principal<br/>Datacenter] -->|CONTIENE| P1[Pasillo_Frio_1]
    DC -->|CONTIENE| P2[Pasillo_Caliente_2]
    DC -->|CONTIENE| P3[SIN_PASILLO]
    P1 -->|CONTIENE| R1[Rack_A1]
    P1 -->|CONTIENE| R2[Rack_A2]
    P2 -->|CONTIENE| R3[Rack_C1]
    P3 -->|CONTIENE| R4[Rack_Z9]
    R1 -->|TIENE_SENSOR| S1[SEN_01]
    S1 -->|GENERO| A1[ALM_n]
```

## Flujo de una lectura (reglas de negocio)

```mermaid
flowchart TD
    L[Nueva lectura] --> V{RN1: timestamp valido?}
    V -- no --> X1[Rechazada]
    V -- si --> A{RN2: sensor ACTIVO?}
    A -- no --> X2[Rechazada]
    A -- si --> I[Se inserta]
    I --> C[RN3: clasifica NORMAL / PRECAUCION / CRITICO]
    C --> Q{PRECAUCION o CRITICO?}
    Q -- si --> AL[RN4: crea alarma inmutable RN5]
    AL --> K{CRITICO?}
    K -- si --> IN[Abre incidencia NOC RN6]
```

## Decisiones de diseño

| Decisión | Motivo |
|---|---|
| Reglas en triggers y no en Python | Se cumplen siempre, sin importar qué aplicación inserte los datos |
| Clave primaria compuesta (sensor, tiempo) | Evita duplicados por reenvíos y crea el índice para consultas por rango |
| Timestamp como entero (epoch UTC) | Compacto, rápido de comparar y ordenar |
| Alarmas con FK hacia la lectura | Trazabilidad: toda alarma conserva el dato que la originó |
| La retención no borra lecturas con alarma | Se conserva la evidencia de las alarmas inmutables |
| API como única puerta de entrada para aplicaciones | Las aplicaciones no tocan la base directamente; las reglas siguen en los triggers |
| Documentos desnormalizados | Una pantalla del NOC se arma con un solo documento, sin JOINs |
| Grafo para impacto y trazabilidad | Recorridos como «qué se afecta si falla un pasillo» son una sola operación |
| Grafos en lugar de vectorial | La jerarquía del datacenter encaja de forma natural; lo vectorial queda como trabajo futuro |
