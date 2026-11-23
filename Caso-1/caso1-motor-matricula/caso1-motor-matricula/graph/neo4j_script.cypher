// Script para Neo4j AuraDB Free (console.neo4j.io)
CREATE
(e1:Estudiante {id:'EST_001', nombre:'Andres Diaz', estado:'ACTIVO'}),
(e2:Estudiante {id:'EST_002', nombre:'Juan Gutierrez', estado:'ACTIVO'}),
(mat1:Asignatura {id:'ASIG_MAT1', codigo:'MAT101', nombre:'Calculo Diferencial', creditos:4}),
(mat2:Asignatura {id:'ASIG_MAT2', codigo:'MAT102', nombre:'Calculo Integral', creditos:4}),
(mat3:Asignatura {id:'ASIG_MAT3', codigo:'MAT201', nombre:'Ecuaciones Diferenciales', creditos:4}),
(bd1:Asignatura {id:'ASIG_BD1', codigo:'INF201', nombre:'Bases de Datos I', creditos:3}),
(bd2:Asignatura {id:'ASIG_BD2', codigo:'INF202', nombre:'Bases de Datos Avanzadas', creditos:3}),
(ia:Asignatura {id:'ASIG_IA1', codigo:'INF301', nombre:'Inteligencia Artificial', creditos:3}),
(mat1)-[:ES_PRERREQUISITO_DE]->(mat2), (mat2)-[:ES_PRERREQUISITO_DE]->(mat3),
(bd1)-[:ES_PRERREQUISITO_DE]->(bd2),   (bd2)-[:ES_PRERREQUISITO_DE]->(ia),
(mat2)-[:ES_PRERREQUISITO_DE]->(ia),
(e1)-[:APROBO {nota:4.5}]->(mat1), (e1)-[:APROBO {nota:4.2}]->(bd1),
(e1)-[:INSCRITO_EN {seccion:'SEC_MAT2_01'}]->(mat2), (e2)-[:INSCRITO_EN {seccion:'SEC_MAT1_01'}]->(mat1);

// G1: grafo completo
MATCH (n) RETURN n;

// G2: impacto en cascada si se reprueba MAT101
MATCH ruta = (inicio:Asignatura {codigo:'MAT101'})-[:ES_PRERREQUISITO_DE*1..5]->(bloqueada:Asignatura)
RETURN inicio.nombre AS Materia_Reprobada, bloqueada.codigo AS Codigo_Bloqueado,
       bloqueada.nombre AS Materia_Bloqueada, length(ruta) AS Nivel_Dependencia;

// G3: materias habilitadas para EST_001
MATCH (e:Estudiante {id:'EST_001'})-[:APROBO]->(aprobada:Asignatura)-[:ES_PRERREQUISITO_DE]->(siguiente:Asignatura)
WHERE NOT (e)-[:APROBO]->(siguiente)
RETURN DISTINCT e.nombre AS Estudiante, siguiente.codigo AS Codigo_Disponible,
       siguiente.nombre AS Materia_Habilitada, collect(aprobada.nombre) AS Prerrequisito_Cumplido;
