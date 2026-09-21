\# SmartBancs Transaction Service



MVP desarrollado para el reto técnico de SmartBancs.



La solución implementa un servicio de transacciones financieras con persistencia en PostgreSQL, control de concurrencia e idempotencia, procesamiento asíncrono mediante RabbitMQ y un servicio independiente de análisis de riesgo basado en Machine Learning.



\## Arquitectura



```text

Client

&#x20; |

&#x20; | REST

&#x20; v

Transaction Service (Spring Boot)

&#x20; |

&#x20; +------> PostgreSQL

&#x20; |         Accounts

&#x20; |         Transactions

&#x20; |

&#x20; +------> RabbitMQ

&#x20;             |

&#x20;             v

&#x20;       AI Risk Service

&#x20;         (FastAPI +

&#x20;      Isolation Forest)



Legacy Bancs

&#x20;    |

&#x20;    | ETL / sincronización desacoplada

&#x20;    v

Analytics / AI

```



La arquitectura separa el flujo transaccional crítico del procesamiento de IA. Una transferencia no espera la respuesta del modelo para finalizar.



\## Tecnologías



\### Backend

\- Java 21

\- Spring Boot

\- Spring Web

\- Spring Data JPA

\- Spring AMQP

\- Spring Boot Actuator

\- Micrometer / Prometheus



\### Datos y mensajería

\- PostgreSQL 17

\- RabbitMQ



\### AI Service

\- Python 3

\- FastAPI

\- scikit-learn

\- Isolation Forest

\- Pika



\### Infraestructura

\- Docker

\- Docker Compose



\## Ejecución



\### Requisitos



\- Docker

\- Docker Compose



No es necesario instalar PostgreSQL, RabbitMQ, Java o Python localmente para ejecutar el MVP mediante Docker.



\### Levantar la solución



Desde la raíz del proyecto:



```bash

docker compose up -d --build

```



Verificar los servicios:



```bash

docker compose ps

```



Servicios disponibles:



| Servicio | URL / Puerto |

|---|---|

| Transaction Service | http://localhost:8080 |

| Spring Actuator | http://localhost:8080/actuator |

| Prometheus Metrics | http://localhost:8080/actuator/prometheus |

| AI Service | http://localhost:8001 |

| RabbitMQ Management | http://localhost:15672 |

| PostgreSQL | localhost:55432 |



\### Health check



Backend:



```bash

curl http://localhost:8080/actuator/health

```



AI Service:



```bash

curl http://localhost:8001/health

```



\## API



\### Crear cuenta



`POST /api/accounts`



Ejemplo:



```json

{

&#x20; "ownerName": "Dennis Tovar",

&#x20; "initialBalance": 1000.00

}

```



\### Consultar cuentas



`GET /api/accounts`



\### Realizar transferencia



`POST /api/transactions`



Header obligatorio:



```text

Idempotency-Key: unique-request-id

```



Body:



```json

{

&#x20; "sourceAccountId": "UUID",

&#x20; "destinationAccountId": "UUID",

&#x20; "amount": 100.00

}

```



Una transacción exitosa retorna estado:



```text

COMPLETED

```



\## Concurrencia e idempotencia



El servicio implementa protección frente a condiciones de carrera mediante bloqueo pesimista de las cuentas involucradas.



Las cuentas se bloquean utilizando un orden determinista basado en UUID para reducir el riesgo de deadlocks cuando existen transferencias simultáneas A → B y B → A.



Cada solicitud requiere un `Idempotency-Key`.



Si una solicitud se repite con la misma clave, el servicio recupera la transacción existente en lugar de ejecutar nuevamente el movimiento financiero.



\## Procesamiento asíncrono de IA



Después del commit de una transferencia se publica un evento `transaction.completed` en RabbitMQ.



El AI Service consume el evento independientemente y realiza una evaluación de riesgo utilizando un modelo Isolation Forest.



El flujo principal no espera el resultado de IA:



```text

Transfer

&#x20;  |

&#x20;  v

Database Commit

&#x20;  |

&#x20;  +---- Response to client

&#x20;  |

&#x20;  +---- RabbitMQ ----> AI Service

```



Esto evita que una degradación del servicio de IA incremente directamente la latencia de las transferencias.



> El modelo incluido es un modelo demostrativo entrenado con datos sintéticos. Un `riskScore` no representa una probabilidad de fraude y una anomalía no implica fraude confirmado.



\## ETL



La carpeta `etl/` contiene un proceso ETL práctico para preparar información histórica para analítica e IA.



El proceso:



\- elimina registros inválidos o incompletos;

\- normaliza formatos;

\- estandariza monedas y estados;

\- transforma fechas;

\- genera variables como hora de transacción;

\- identifica transacciones realizadas en horario nocturno;

\- genera un dataset limpio para análisis.



Consultar `etl/README.md` para su ejecución.



\## Observabilidad



Spring Boot Actuator y Micrometer exponen métricas compatibles con Prometheus.



Endpoint:



```text

GET /actuator/prometheus

```



Se incluyen métricas relacionadas con:



\- solicitudes HTTP;

\- latencia;

\- conexiones HikariCP;

\- acceso a repositorios;

\- publicación y consumo RabbitMQ;

\- transacciones completadas;

\- transacciones fallidas;

\- solicitudes idempotentes;

\- duración del procesamiento transaccional.



También se generan logs para operaciones críticas y se utiliza `transactionId` como identificador para seguir el flujo de una transacción entre componentes.



\## Integración con Bancs



El sistema legado Bancs no debe ser consultado directamente por cada solicitud del nuevo servicio.



La estrategia propuesta utiliza integración desacoplada mediante procesamiento asíncrono, batching, rate limiting, reintentos controlados y reconciliación.



Para una implementación productiva se propone utilizar Transactional Outbox y, cuando las capacidades del sistema legado lo permitan, CDC o sincronización incremental.



Esto protege Bancs frente a picos de tráfico provenientes de los nuevos servicios.



\## Escalabilidad



La arquitectura está diseñada para permitir escalamiento horizontal de los servicios stateless y consumidores RabbitMQ.



Para un escenario productivo de alto volumen se requerirían pruebas de carga, dimensionamiento de infraestructura, optimización del pool de conexiones, particionamiento cuando corresponda y monitoreo continuo.



El MVP no afirma haber validado experimentalmente una capacidad de 10.000 TPS.



\## Manejo de incidentes



Ante un incremento severo de latencia o timeouts de base de datos se revisarían inicialmente:



\- latencia y tasa de errores HTTP;

\- métricas HikariCP;

\- conexiones activas;

\- queries activas en PostgreSQL;

\- bloqueos y sesiones;

\- backlog de RabbitMQ;

\- recursos CPU/memoria.



Posteriormente se identificaría la consulta o proceso responsable, se reduciría presión sobre el componente afectado y se aplicaría escalamiento o mitigación según la causa.



Después del incidente se realizaría un postmortem incluyendo timeline, impacto, causa raíz, acciones de recuperación y acciones preventivas.



\## Decisiones y limitaciones



\### Decisiones



\- PostgreSQL para consistencia transaccional.

\- Bloqueo pesimista para proteger saldos.

\- Idempotencia para evitar movimientos duplicados.

\- RabbitMQ para desacoplar el flujo transaccional de IA.

\- FastAPI para mantener el servicio de IA independiente.

\- Docker Compose para reproducibilidad.

\- Actuator/Micrometer para observabilidad.



\### Limitaciones del MVP



\- El modelo de IA utiliza datos sintéticos y no está validado para producción.

\- No se realizaron pruebas que demuestren 10.000 TPS.

\- La publicación DB → RabbitMQ no implementa todavía Transactional Outbox.

\- Bancs se presenta como estrategia de integración debido a que no existe acceso real al sistema legado.

\- Las pruebas automatizadas actuales son limitadas y deben ampliarse con pruebas unitarias, integración, concurrencia y carga.



\## Pruebas



Ejecutar:



```bash

./mvnw test

```



En Windows:



```powershell

.\\mvnw.cmd test

```



\## Detener infraestructura



```bash

docker compose down

```



Para eliminar también los volúmenes:



```bash

docker compose down -v

```



> El segundo comando elimina los datos persistidos localmente.



\## Uso de Inteligencia Artificial



El uso de herramientas de IA durante el desarrollo se declara explícitamente en:



`AI\_USAGE.md`

