# Phase 13 — Code Quality with SonarQube

> **Goal:** Static analysis on every PR. Block merges that drop test coverage or introduce bugs/security smells.

---

## 13.1 SonarCloud vs Self-Hosted SonarQube

| Option | Cost | Setup |
|---|---|---|
| **SonarCloud** | Free for public repos, paid for private | 5 minutes |
| **SonarQube** (self-hosted) | Free Community Edition; you run the server | Docker run + reverse proxy |

For the tutorial, SonarCloud is the path of least resistance. Self-hosted instructions follow at the end.

---

## 13.2 SonarCloud — Quick Path

1. Sign in to https://sonarcloud.io with your GitHub account.
2. Click **"+"** → **Analyze new project** → pick your repo.
3. Choose **"With GitHub Actions"**.
4. Copy the **`SONAR_TOKEN`** and add it to **GitHub repo Settings → Secrets**.
5. Note your **organization key** and **project key** (e.g. `your-org` and `your-org_mlops-e2e`).

Edit `sonar-project.properties` and the `Sonar scan` workflow to use your keys:

```properties
# sonar-project.properties
sonar.projectKey=your-org_mlops-e2e
sonar.organization=your-org
```

Open a PR → the `Sonar scan` workflow runs → you'll get a Sonar comment on the PR with bugs, vulns, code smells, and coverage delta.

---

## 13.3 What Sonar Checks

| Category | Examples |
|---|---|
| **Bugs** | `None`-deref, wrong loop conditions, unused vars |
| **Vulnerabilities** | Hard-coded credentials, SQL injection, weak hashing |
| **Code smells** | Cyclomatic complexity, duplication, unused imports |
| **Security hotspots** | Things humans should review (e.g. `pickle.load(untrusted)`) |
| **Coverage** | What % of lines are exercised by tests |

You define a **Quality Gate** in Sonar UI (per-project). Defaults are sensible:
- 0 Bugs, 0 Vulnerabilities on new code
- ≥ 80 % coverage on new code
- ≤ 3 % duplication on new code
- A-grade maintainability rating on new code

If any check fails, the PR check goes red, and (with branch protection) you can't merge.

---

## 13.4 Branch Protection

In GitHub repo **Settings → Branches → Branch protection rules** for `main`:
- ✅ Require status checks: `Sonar`, `CI`
- ✅ Require branches to be up to date
- ✅ Require a pull request review

This is what actually gives you the gate. Without branch protection, Sonar will warn but won't block.

---

## 13.5 Self-Hosted SonarQube (Optional)

If you'd rather run it yourself:

```bash
# 1. Run SonarQube locally
docker run -d --name sonarqube \
   -p 9000:9000 \
   -e SONAR_FORCEAUTHENTICATION=false \
   sonarqube:lts-community

# 2. Wait ~1 min, then open http://localhost:9000
#    Login: admin / admin → change password

# 3. Create a project, get the token, scan locally:
docker run --rm \
   -e SONAR_HOST_URL=http://host.docker.internal:9000 \
   -e SONAR_TOKEN=<your-token> \
   -v "$(pwd):/usr/src" \
   sonarsource/sonar-scanner-cli
```

For production, deploy SonarQube to your own cluster (or a small EC2). Put it behind an ALB + Cognito or OIDC for auth.

---

## 13.6 Running Locally Before You Push

Pre-commit your way to fewer failing PRs:

```bash
pip install ruff
cd backend
ruff check app/ tests/ --fix
ruff format app/ tests/

# Coverage
pytest --cov=app --cov-report=term-missing
```

---

## ✅ Phase 13 Checklist

- [ ] SonarCloud project linked to repo
- [ ] `SONAR_TOKEN` secret set in GitHub
- [ ] `sonar-project.properties` updated with your keys
- [ ] Opening a PR shows the Sonar comment within ~2 min
- [ ] Branch protection requires the `Sonar` check

**Next:** [`14-monitoring.md`](14-monitoring.md) →
