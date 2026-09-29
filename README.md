# Meridian Tech Helpdesk

Meridian is a FastAPI helpdesk with employee chat, knowledge retrieval, Jira/Confluence integration, and remote remediation. The production runtime is split into a Python backend and an Nginx frontend while keeping the existing application package names intact.

## Layout

```text
backend/
  app/                 FastAPI app, routes, auth, configuration
  agents/              Self-help and code-analysis agents
  database/            SQLAlchemy models and database setup
  knowledge_base/      Retrieval and ingestion
  services/            Jira, MeshCentral, and conversation services
  tests/               Python tests and integration scripts
  Dockerfile
  requirements.txt
frontend/
  templates/           Browser pages
  static/              Browser assets
  Dockerfile
  nginx.conf
.github/workflows/ci-cd.yml
Dockerfile-less root configuration: docker-compose.yml, .env.example
```

## Local Development

Use Python 3.11. Copy `.env.example` to `.env`, replace `JWT_SECRET` with a random value, and configure optional integrations. Install backend dependencies and run from the backend directory:

```powershell
Copy-Item .env.example .env
Set-Location backend
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

Open `http://localhost:8001/`. The API health endpoint is `/health`; API documentation is available at `/docs` during local development.

## Docker Compose

Docker Compose builds both images and persists database, uploads, and escalation state in named volumes. Provide a root `.env` file first:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
```

The frontend is exposed on port 80 by default (`HTTP_PORT` can change it). Nginx serves the frontend and reverse-proxies API requests to the backend. The backend is not published directly to the host.

For production, set `ENVIRONMENT=production` and provide `JWT_SECRET` with at least 32 characters. The backend rejects production startup without it. Do not put AWS access keys in `.env`; on EC2, use an instance role. Keep the application secret JSON in AWS Secrets Manager.

## CI/CD Setup

`.github/workflows/ci-cd.yml` runs Python syntax, Ruff, Vulture, MyPy, tests, Bandit, Gitleaks, pip-audit, Docker builds, Trivy scans, and CycloneDX SBOM generation. Main-branch pushes build and publish `latest` images to ECR, deploy them through SSM, verify the services, and attempt a digest-based rollback if deployment or verification fails. The SSM deploy, verification, and rollback commands are defined directly in the workflow. The `docker-build-approval` GitHub Environment can require reviewers before images are built.

Configure these GitHub repository variables:

- `AWS_ACCOUNT_ID`: AWS account hosting the ECR repositories.
- `AWS_REGION`: AWS region (defaults to `us-east-1`).
- `AWS_ROLE_ARN`: OIDC role assumed by GitHub Actions.
- `EC2_INSTANCE_ID`: SSM-managed deployment instance.
- `EC2_APP_DIR`: application checkout directory on EC2 (defaults to `/home/ssm-user/Meridian-Tech-Integrated`).
- `APP_SECRET_NAME`: Secrets Manager secret name (defaults to `Meridian-Secret-For-EC2`).
- `ECR_BACKEND_REPOSITORY` and `ECR_FRONTEND_REPOSITORY`: repository names (defaults to `github-cicd-demo-backend` and `github-cicd-demo-frontend`).

The GitHub OIDC role needs ECR authentication and push permissions plus `ssm:SendCommand` and `ssm:GetCommandInvocation` for the deployment instance. The EC2 instance must be registered with Systems Manager, have Docker Compose installed, be able to pull from ECR, and have permission to read the application secret from Secrets Manager. The application checkout at `EC2_APP_DIR` must contain this repository's `docker-compose.yml`. The secret should be a JSON object containing `JWT_SECRET` and the configured integration settings (for example `JIRA_API_TOKEN`, `CONFLUENCE_API_KEY`, and MeshCentral credentials).

## Validation

Run the focused CI unit tests from the repository root:

```powershell
python -m pip install pytest fastapi sqlalchemy python-dotenv bcrypt 'python-jose[cryptography]'
pytest -q backend/tests/test_auth_security.py
python -m compileall -q backend
```

The longer scripts in `backend/tests/` exercise live services and require a running application plus valid integration credentials; they are not run by the default CI unit-test job.
