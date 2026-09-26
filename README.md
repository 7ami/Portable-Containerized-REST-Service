# Portable Containerized REST Service

**Course**: Introduction to Cloud Computing (CS 554 - Graduate Extension)  
**Project**: Project 1 — Portable Containerized REST Service  
**Author**: Containerization & Cloud Computing Project Submission  

---

## 1. Project Overview

This project implements a portable, multi-container REST service packaged as an OCI-compliant container image and orchestrated using Docker Compose. The service provides unit conversions from pounds (`lbs`) to kilograms (`kg`), persists the cumulative count of successful conversions using Redis, and demonstrates container isolation, networking, persistent named volumes, non-root security, and fault-tolerant operational lifecycles.

### System Architecture Diagram
```
                     +---------------------------------------+
                     |             Host Machine              |
                     |  curl / browser / test scripts (5000) |
                     +-------------------+-------------------+
                                         | Published Port 5000:5000
                                         v
+-------------------------------------------------------------------------+
| Docker Network: app_network (Private Bridge)                            |
|                                                                         |
|  +------------------------------+     +-------------------------------+ |
|  |     Service: app             |     |       Service: redis          | |
|  |  - Python 3.12-slim          |     |  - redis:7.2-alpine           | |
|  |  - Non-root user (appuser)   |     |  - Port 6379 (internal only)  | |
|  |  - Flask REST API            |===> |  - Append-Only File (AOF)     | |
|  |  - Healthcheck (/health)     |     |  - Named Volume: redis_data   | |
|  +------------------------------+     +---------------+---------------+ |
|                                                       |                 |
+-------------------------------------------------------|-----------------+
                                                        v
                                          +---------------------------+
                                          | Named Volume: redis_data  |
                                          | (Survives container cycle)|
                                          +---------------------------+
```

---

## 2. Prerequisites

Ensure the following are installed on your host system:
- **Docker Desktop** (version 24.0+ / Compose v2.20+) with Linux container support enabled.
  - Windows users: Ensure Docker Desktop is running and WSL 2 backend is enabled.
- **Python 3.10+** (optional, for running the host-side test script `test_api.py`).
- **PowerShell** or **curl** (for executing test commands).

---

## 3. How to Build and Start the Application

Start the entire multi-container environment with a single command from the project root directory:

```bash
docker compose up --build -d
```

### Explanation of flags:
- `--build`: Instructs Docker Compose to build the application image from `Dockerfile` before starting containers.
- `-d`: Runs containers detached in the background, returning control to your terminal.

To check running container status and health:
```bash
docker compose ps
```

Both `icc-app` and `icc-redis` should report `Up` with `(healthy)` status.

---

## 4. API Endpoints & Testing

The REST service listens on host port `5000` (`http://localhost:5000`).

### 4.1 Automated Testing

We provide two automated test scripts that verify all 8 rubric test cases:

#### Option A: Python Test Script (Cross-Platform)
```bash
python test_api.py
```

#### Option B: Native PowerShell Test Script (Windows)
```powershell
.\test_api.ps1
```

---

### 4.2 Manual Curl / HTTP Commands

#### 1. Liveness Health Check
```bash
curl -i http://localhost:5000/health
```
**Expected Response (200 OK):**
```json
{
  "status": "ok"
}
```

#### 2. Convert Pounds to Kilograms (`lbs=150`)
```bash
curl -i "http://localhost:5000/convert?lbs=150"
```
**Expected Response (200 OK):**
```json
{
  "formula": "kg = lbs * 0.45359237",
  "kg": 68.039,
  "lbs": 150
}
```

#### 3. Convert Zero (`lbs=0`)
```bash
curl -i "http://localhost:5000/convert?lbs=0"
```
**Expected Response (200 OK):**
```json
{
  "formula": "kg = lbs * 0.45359237",
  "kg": 0,
  "lbs": 0
}
```

#### 4. Convert Decimal (`lbs=0.1`)
```bash
curl -i "http://localhost:5000/convert?lbs=0.1"
```
**Expected Response (200 OK):**
```json
{
  "formula": "kg = lbs * 0.45359237",
  "kg": 0.045,
  "lbs": 0.1
}
```

#### 5. Missing Parameter Error Handling
```bash
curl -i http://localhost:5000/convert
```
**Expected Response (400 Bad Request):**
```json
{
  "error": "Missing required query parameter: 'lbs'"
}
```

#### 6. Non-Numeric Parameter Error Handling
```bash
curl -i "http://localhost:5000/convert?lbs=abc"
```
**Expected Response (400 Bad Request):**
```json
{
  "error": "Query parameter 'lbs' must be a valid number"
}
```

#### 7. Negative Number Error Handling
```bash
curl -i "http://localhost:5000/convert?lbs=-5"
```
**Expected Response (422 Unprocessable Entity):**
```json
{
  "error": "Value for 'lbs' must be a non-negative finite number"
}
```

#### 8. Retrieve Persistent Conversion Count
```bash
curl -i http://localhost:5000/stats
```
**Expected Response (200 OK):**
```json
{
  "conversions": 3
}
```
*(Note: Only valid conversion requests increment this counter. Invalid requests do not increment it).*

---

## 5. Inspection and Logging

### View Real-Time Logs
Follow logs across all services:
```bash
docker compose logs -f
```

View application logs only:
```bash
docker compose logs -f app
```

View Redis logs only:
```bash
docker compose logs -f redis
```

### Inspect Container Details
Inspect container health state, IP assignments, and mount configurations:
```bash
docker inspect icc-app
docker inspect icc-redis
```

Verify the non-root user running inside the container:
```bash
docker compose exec app whoami
# Output: appuser (UID 1000)
```

Verify that Redis cannot be reached directly from the host:
```bash
curl http://localhost:6379
# Fails / connection refused because 6379 is not mapped to host
```

---

## 6. Lifecycle Management & Operational Demonstration

### Step 1: Normal Stop
To pause container processes without removing them:
```bash
docker compose stop
```

### Step 2: Container Teardown (Preserving Persistent Volume)
To remove container instances and network while **preserving** the Redis persistent data volume:
```bash
docker compose down
```

### Step 3: Persistence Verification (Recreate System)
Recreate and start the containers from scratch:
```bash
docker compose up -d
```
Check `/stats`:
```bash
curl http://localhost:5000/stats
```
**Result**: The count matches the count prior to container removal, demonstrating that the named volume `redis_data` successfully survived container recreation.

### Step 4: Complete Teardown and Cleanup
To completely clean up all project resources, including the persistent named volume and images:
```bash
docker compose down -v
```
*(The `-v` flag deletes named volumes defined in the compose file).*

---

## 7. Design Decisions & Architectural Analysis

### 7.1 How the Application Locates Redis
The application resolves Redis dynamically using Docker's internal DNS resolver via the Compose service name (`redis`). At startup, the application reads the environment variable:
```bash
REDIS_HOST=redis
```
When `redis_client` initializes, Docker's embedded DNS server (at `127.0.0.11`) resolves `redis` to the private IP assigned to the `icc-redis` container within the bridge network `app_network`. This decouples application code from container networking topology and adheres to the **Twelve-Factor App** configuration principles.

### 7.2 Why Redis Is Not Exposed to the Host
Redis is an internal state store intended solely for backend services. Exposing port `6379` to the host:
1. **Violates Principle of Least Privilege**: Unnecessarily exposes a database port to external interfaces, local processes, or public networks.
2. **Eliminates Attack Vectors**: By isolating Redis exclusively inside `app_network`, only authorized containers on that specific bridge network can communicate with it.

### 7.3 Why the Redis Volume Is Separate from the Redis Container
Containers are intentionally **ephemeral** and disposable. If data were stored inside the writable container layer:
- Upgrading the Redis container image or running `docker compose down` would destroy all stored conversion counts.
- Writing to container layers incurs storage-driver overhead (overlayfs).
By mounting a named volume (`redis_data`) mapped to `/data` with `--appendonly yes`, disk operations bypass the container layer, write directly to host storage, and outlive container lifecycles.

### 7.4 Differences Between Docker Operations
- `docker compose stop`: Sends `SIGTERM` (followed by `SIGKILL` if needed) to stop container processes. Preserves container filesystems, networks, and configurations in place.
- `docker compose down`: Stops container processes and deletes container instances, networks, and internal resources defined in the compose file. Named volumes are preserved.
- `docker compose down -v`: Stops and deletes containers, networks, **and** permanently removes the named volumes (`redis_data`), wiping all persistent state.

---

## 8. Graduate Extension (CS 554)

### 8.1 Restart Policy Configuration
In `compose.yaml`, both `app` and `redis` configure:
```yaml
restart: unless-stopped
```
- **When it applies**: If a container crashes (e.g. out-of-memory or uncaught runtime crash), the Docker daemon automatically restarts it. If the host machine or Docker daemon reboots, containers configured with `unless-stopped` automatically restart when Docker starts.
- **When it does not apply**: If an operator explicitly executes `docker compose stop` or `docker compose down`, Docker records that the container was manually stopped and will **not** attempt to restart it upon daemon reboot.

### 8.2 Failure Scenario Analysis: Application / Redis Dependency
**Scenario**: The Redis container stops or is temporarily unreachable during application operation.

- **System Behavior**:
  1. **Application Health & Survival**: Because the Python application connects through a managed connection pool with defined socket timeouts (`socket_connect_timeout=2.0s`) and catches `redis.exceptions.RedisError`, the Flask application process does **not** crash or trigger an unhandled termination.
  2. **Endpoint Behavior**:
     - `GET /health` continues to return `200 OK` (`{"status": "ok"}`), reporting that the web process is alive.
     - `GET /convert` and `GET /stats` gracefully catch the connection error and immediately return HTTP `503 Service Unavailable` with JSON `{ "error": "Redis service unavailable" }` rather than leaking internal Python stack traces or failing with uninformative 500 errors.
  3. **Automatic Recovery**: Once the Redis container restarts or recovers network connectivity, subsequent `/convert` and `/stats` requests immediately resume succeeding without requiring an application restart.

### 8.3 In-Depth Comparison: Docker Compose vs. Single Virtual Machine (VM)

| Dimension | Docker Compose Architecture | Single Virtual Machine (VM) Architecture |
| :--- | :--- | :--- |
| **Resource Isolation & Overhead** | Containers share the host OS Linux kernel, isolating processes via cgroups and namespaces. Memory and CPU overhead is minimal (~10MB overhead per container). | A VM requires a full guest operating system, virtualized hardware drivers, and dedicated memory allocation (gigabytes of RAM and disk overhead per VM). |
| **Startup & Deployment Velocity** | Startup is nearly instantaneous (sub-second process spawn). Environment is fully declared in code (`compose.yaml`) and portable across developer laptops and CI/CD pipelines. | Booting a VM takes tens of seconds or minutes. Configuration requires provisioning tools (Ansible, Bash scripts) which are susceptible to configuration drift. |
| **Security & Port Exposure** | Fine-grained network namespace isolation allows Redis to remain completely unreachable from the host without configuring host-level firewall rules. | Both services run on the same OS. Restricting access to Redis requires local firewall (`ufw`/`iptables`) or binding Redis to `127.0.0.1` while managing local user privileges manually. |

#### Two Key Architectural Tradeoffs:
1. **Tradeoff 1: Kernel Isolation vs. Performance**: Virtual machines provide strict hypervisor-level hardware virtualization (strong isolation against kernel exploits), whereas containers share the underlying host kernel. However, containers deliver near bare-metal I/O and CPU throughput without hypervisor emulation penalties.
2. **Tradeoff 2: Orchestration Simplicity vs. Multi-Node Scalability**: Docker Compose provides seamless single-host orchestration ideal for local development, reproducible testing, and predictable deployment. However, it cannot distribute containers across multiple physical host nodes; moving to a multi-host cluster requires transitioning to an orchestrator like Kubernetes or Nomad.
