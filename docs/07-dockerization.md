# Phase 7 — Dockerization

> **Goal:** Build container images for the backend and frontend, run them locally with `docker compose`, then push them to Amazon ECR for EKS to pull.

---

## 7.1 Why Multi-Stage Dockerfiles

A single-stage Dockerfile that does `pip install` in the final image leaves behind:
- Build toolchain (`gcc`, `build-essential`)
- pip cache
- Source artifacts

Multi-stage splits this into:
1. **Builder stage** — installs everything into a venv.
2. **Runtime stage** — copies *only* the venv + app code. No compiler. No pip cache.

Result: ~150 MB instead of ~600 MB, and a smaller attack surface.

The backend `Dockerfile` already does this. Take a look at `backend/Dockerfile`.

---

## 7.2 Build & Run Locally

```bash
# Backend
cd backend
docker build -t churn-backend:dev .
docker run --rm -p 8000:8000 \
   -e MOCK_MODEL=true \
   -e LOG_ENV=dev \
   churn-backend:dev

# In another terminal:
curl http://localhost:8000/health
curl http://localhost:8000/model-info
```

```bash
# Frontend
cd frontend
docker build -t churn-frontend:dev .
docker run --rm -p 8080:8080 \
   -e BACKEND_URL=http://host.docker.internal:8000 \
   churn-frontend:dev

# Open http://localhost:8080
```

---

## 7.3 docker-compose for Convenience

Create `docker-compose.yml` at the repo root:

```yaml
services:
  backend:
    build: ./backend
    environment:
      - MOCK_MODEL=true
      - LOG_ENV=dev
      - CORS_ORIGINS=*
    ports:
      - "8000:8000"

  frontend:
    build: ./frontend
    environment:
      - BACKEND_URL=http://backend:8000
    ports:
      - "8080:8080"
    depends_on:
      - backend
```

```bash
docker compose up --build
# Open http://localhost:8080
```

---

## 7.4 Push to Amazon ECR

ECR (Elastic Container Registry) is AWS's private Docker registry. EKS pulls images from it.

### Step 1: Create the repositories

```bash
source .env
REGION=${AWS_REGION}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws ecr create-repository --repository-name churn-backend  --region "$REGION"
aws ecr create-repository --repository-name churn-frontend --region "$REGION"
```

### Step 2: Authenticate Docker to ECR

```bash
aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin \
      "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
```

### Step 3: Tag + push

```bash
TAG=$(git rev-parse --short HEAD)         # e.g. 9a8f7e6

# Backend
docker build -t churn-backend:$TAG backend/
docker tag  churn-backend:$TAG \
    "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/churn-backend:$TAG"
docker push "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/churn-backend:$TAG"

# Frontend
docker build -t churn-frontend:$TAG frontend/
docker tag  churn-frontend:$TAG \
    "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/churn-frontend:$TAG"
docker push "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/churn-frontend:$TAG"
```

> 💡 In the CI workflow (Phase 11), GitHub Actions does this automatically on every merge to `main` and bumps the `k8s/` image tags.

---

## 7.5 Production Image Hygiene Checklist

- [x] Multi-stage build (no compilers in runtime image)
- [x] Non-root user (`USER app` in backend, `USER nginx` in frontend)
- [x] Pinned base image with explicit tag (`python:3.11-slim`, not `python:latest`)
- [x] `.dockerignore` excludes `__pycache__`, `.git`, tests
- [x] HEALTHCHECK directive so Docker/K8s knows when container is ready
- [x] Specific port `EXPOSE`d
- [ ] Image scanned for vulns (we'll add Trivy in CI, Phase 11)
- [ ] SBOM generated (Syft, optional)

---

## ✅ Phase 7 Checklist

- [ ] `docker build` succeeds for backend and frontend
- [ ] `docker compose up` shows the working UI at `localhost:8080`
- [ ] Both ECR repos created
- [ ] You can push an image to ECR with a manual `docker push`

**Next:** [`08-vpc-terraform.md`](08-vpc-terraform.md) →
