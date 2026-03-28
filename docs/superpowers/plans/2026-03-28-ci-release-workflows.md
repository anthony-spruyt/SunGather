# CI & Release Workflow Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace legacy GitHub Actions workflows with modern CI (lint + build + test +
scan), an automated release workflow (SBOM, SLSA provenance, attestation), and daily
container image vulnerability scanning.

**Architecture:** Enhance the existing `ci.yaml` with a Docker build/test/scan job.
Create a new `release.yaml` workflow (modeled on `release-shutdown-orchestrator.yaml`
from spruyt-labs) that resolves version from git tags, builds multi-platform images,
pushes to GHCR with SBOM/provenance, generates attestations, and creates GitHub
releases. Upgrade `trivy-scan.yaml` to scan the published container image. Delete the
legacy `docker-image.yml` and `update-addon.yml` workflows.

**Tech Stack:** GitHub Actions, Docker Buildx, GHCR, Trivy, SLSA provenance,
`actions/attest-build-provenance`

**Reference workflows:**
- `anthony-spruyt/container-images/.github/workflows/_image-pipeline.yaml` (SBOM,
  attestation, Trivy scan pattern)
- `anthony-spruyt/spruyt-labs/.github/workflows/release-shutdown-orchestrator.yaml`
  (version resolution, release notes, provenance)

---

## Tasks

### Task 1: Delete legacy workflows

**Files:**

- Delete: `.github/workflows/docker-image.yml`
- Delete: `.github/workflows/update-addon.yml`

- [ ] **Step 1: Delete docker-image.yml**

```bash
git rm .github/workflows/docker-image.yml
```

- [ ] **Step 2: Delete update-addon.yml**

```bash
git rm .github/workflows/update-addon.yml
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: remove legacy docker-image and update-addon workflows"
```

---

### Task 2: Add Dockerfile test stage and enhance CI workflow

The CI build job needs to run pytest inside the container, but pytest isn't in the
production image. Add a multi-stage Dockerfile with a `test` stage that includes pytest.
Then enhance `ci.yaml` with a `build` job that builds the test stage to run tests,
builds the production stage for Trivy scanning, and catches issues before merge.

**Files:**

- Modify: `Dockerfile`
- Modify: `.github/workflows/ci.yaml`

- [ ] **Step 1: Add test stage to Dockerfile**

Replace the full `Dockerfile` with:

```dockerfile
FROM python:3.14 AS builder

RUN python3 -m venv /opt/virtualenv \
 && apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN /opt/virtualenv/bin/pip3 install --no-cache-dir -r requirements.txt

# Test stage: includes pytest for CI
FROM builder AS test

RUN /opt/virtualenv/bin/pip3 install --no-cache-dir pytest

# Production stage
FROM python:3.14-slim

RUN useradd -r -m sungather

COPY --from=builder /opt/virtualenv /opt/virtualenv

WORKDIR /opt/sungather

COPY SunGather/ .

VOLUME /logs
VOLUME /config
COPY SunGather/config-example.yaml /config/config.yaml

USER sungather

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD /opt/virtualenv/bin/python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" \
  || exit 1

CMD [ "/opt/virtualenv/bin/python", "sungather.py", "-c", "/config/config.yaml", "-l", "/logs/" ]
```

- [ ] **Step 2: Replace ci.yaml with enhanced version**

Replace `.github/workflows/ci.yaml` with:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/SchemaStore/schemastore/master/src/schemas/json/github-workflow.json

name: "CI"
on:
  pull_request:
    branches:
      - "main"
  push:
    branches:
      - "main"
permissions:
  actions: "write"
  contents: "write"
  pull-requests: "write"
  security-events: "write"
  statuses: "write"
jobs:
  lint:
    uses: "anthony-spruyt/repo-operator/.github/workflows/_lint.yaml@main"
    secrets: "inherit"
  build:
    name: "Build, test, and scan"
    needs: "lint"
    runs-on: "ubuntu-latest"
    steps:
      - name: "Checkout"
        uses: "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd" # v6

      - name: "Set up Docker Buildx"
        uses: "docker/setup-buildx-action@4d04d5d9486b7bd6fa91e7baf45bbb4f8b9deedd" # v4

      - name: "Build test image"
        uses: "docker/build-push-action@d08e5c354a6adb9ed34480a06d141179aa583294" # v7
        with:
          context: "."
          target: "test"
          push: false
          load: true
          tags: "sungather:test"
          cache-from: "type=gha"
          cache-to: "type=gha,mode=max"

      - name: "Run tests"
        run: |
          docker run --rm \
            -v "${{ github.workspace }}/tests:/opt/sungather/tests:ro" \
            sungather:test \
            /opt/virtualenv/bin/python -m pytest tests/ -v

      - name: "Build production image"
        uses: "docker/build-push-action@d08e5c354a6adb9ed34480a06d141179aa583294" # v7
        with:
          context: "."
          push: false
          load: true
          tags: "sungather:ci"
          cache-from: "type=gha"
          cache-to: "type=gha,mode=max"

      - name: "Scan for vulnerabilities"
        uses: "aquasecurity/trivy-action@57a97c7e7821a5776cebc9bb87c984fa69cba8f1" # v0.29
        with:
          image-ref: "sungather:ci"
          scanners: "vuln,secret,misconfig"
          format: "table"
          exit-code: "1"
          severity: "CRITICAL,HIGH"
          ignore-unfixed: true
          trivyignores: ".trivyignore.yaml"

  summary:
    needs:
      - "lint"
      - "build"
    if: "always()"
    uses: "anthony-spruyt/repo-operator/.github/workflows/_summary.yaml@main"
```

- [ ] **Step 3: Verify workflow syntax**

Run: `actionlint .github/workflows/ci.yaml` (if available), otherwise visual review.

Check:
- `lint` job unchanged (repo-operator reusable workflow)
- `build` job depends on `lint`
- Test stage builds with `target: "test"`, mounts tests dir read-only
- Production stage builds separately for Trivy scan
- `summary` job lists both `lint` and `build` in `needs`
- Trivy uses `.trivyignore.yaml` (matches existing config)

- [ ] **Step 4: Commit**

```bash
git add Dockerfile .github/workflows/ci.yaml
git commit -m "feat(ci): add Dockerfile test stage and enhance CI with build, test, and scan"
```

---

### Task 3: Create release workflow

Create `release.yaml` modeled on `release-shutdown-orchestrator.yaml`. This workflow:
- Triggers via `workflow_dispatch` with a semver bump choice (for n8n or manual use)
- Resolves the next version from existing git tags
- Builds multi-platform Docker images (amd64, arm64, armv7)
- Pushes to GHCR with SBOM and SLSA provenance
- Generates build provenance attestation
- Creates a git tag and GitHub Release with image details and verify command

**Files:**

- Create: `.github/workflows/release.yaml`

- [ ] **Step 1: Create release.yaml**

Create `.github/workflows/release.yaml`:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/SchemaStore/schemastore/master/src/schemas/json/github-workflow.json

name: "Release"
on:
  workflow_dispatch:
    inputs:
      bump:
        description: "Version bump type"
        required: true
        type: "choice"
        options:
          - "patch"
          - "minor"
          - "major"
permissions:
  contents: "write"
  packages: "write"
  id-token: "write"
  attestations: "write"
env:
  IMAGE: "ghcr.io/${{ github.repository_owner }}/sungather"
jobs:
  resolve-version:
    name: "Resolve version"
    runs-on: "ubuntu-latest"
    outputs:
      tag: "${{ steps.bump.outputs.tag }}"
      version: "${{ steps.bump.outputs.version }}"
    steps:
      - name: "Checkout"
        uses: "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd" # v6
        with:
          fetch-depth: 0
          fetch-tags: true
      - name: "Compute next version"
        id: "bump"
        env:
          BUMP: "${{ inputs.bump }}"
        run: |
          # Find latest tag matching v* prefix
          LATEST=$(git tag --list "v*" --sort=-v:refname | head -n 1)

          if [ -z "$LATEST" ]; then
            CURRENT="0.0.0"
          else
            CURRENT="${LATEST#v}"
          fi

          IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT"

          case "$BUMP" in
            major) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
            minor) MINOR=$((MINOR + 1)); PATCH=0 ;;
            patch) PATCH=$((PATCH + 1)) ;;
          esac

          VERSION="${MAJOR}.${MINOR}.${PATCH}"
          echo "version=$VERSION" >> "$GITHUB_OUTPUT"
          echo "tag=v$VERSION" >> "$GITHUB_OUTPUT"
          echo "::notice::Bumping $BUMP: ${LATEST:-v0.0.0} -> v$VERSION"
  test:
    name: "Test"
    runs-on: "ubuntu-latest"
    steps:
      - name: "Checkout"
        uses: "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd" # v6
      - name: "Set up Python"
        uses: "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405" # v6
        with:
          python-version: "3.14"
      - name: "Install dependencies"
        run: |
          pip install --upgrade -r requirements.txt
          pip install pytest
      - name: "Run tests"
        run: "python -m pytest tests/ -v"
  release:
    name: "Build, push, and release"
    needs:
      - "resolve-version"
      - "test"
    runs-on: "ubuntu-latest"
    steps:
      - name: "Checkout"
        uses: "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd" # v6

      - name: "Set up QEMU"
        uses: "docker/setup-qemu-action@ce360397dd3f832beb865e1373c09c0e9f86d70a" # v4

      - name: "Set up Docker Buildx"
        uses: "docker/setup-buildx-action@4d04d5d9486b7bd6fa91e7baf45bbb4f8b9deedd" # v4

      - name: "Login to GHCR"
        uses: "docker/login-action@b45d80f862d83dbcd57f89517bcf500b2ab88fb2" # v4
        with:
          registry: "ghcr.io"
          username: "${{ github.actor }}"
          password: "${{ secrets.GITHUB_TOKEN }}"

      - name: "Docker metadata"
        id: "meta"
        uses: "docker/metadata-action@030e881283bb7a6894de51c315a6bfe6a94e05cf" # v6
        with:
          images: "${{ env.IMAGE }}"
          tags: |
            type=semver,pattern={{version}},value=${{ needs.resolve-version.outputs.tag }}
            type=semver,pattern={{major}}.{{minor}},value=${{ needs.resolve-version.outputs.tag }}
            type=raw,value=latest

      - name: "Scan for vulnerabilities"
        uses: "aquasecurity/trivy-action@57a97c7e7821a5776cebc9bb87c984fa69cba8f1" # v0.29
        with:
          scan-type: "fs"
          scanners: "vuln,secret,misconfig"
          format: "table"
          exit-code: "1"
          severity: "CRITICAL,HIGH"
          ignore-unfixed: true
          trivyignores: ".trivyignore.yaml"

      - name: "Build and push"
        id: "push"
        uses: "docker/build-push-action@d08e5c354a6adb9ed34480a06d141179aa583294" # v7
        with:
          context: "."
          platforms: "linux/amd64,linux/arm64,linux/arm/v7"
          push: true
          tags: "${{ steps.meta.outputs.tags }}"
          labels: "${{ steps.meta.outputs.labels }}"
          cache-from: "type=gha"
          cache-to: "type=gha,mode=max"
          sbom: true
          provenance: "mode=max"

      - name: "Generate provenance attestation"
        uses: "actions/attest-build-provenance@10334b5f1e684784025c3fc0a277c88c19089275" # v4
        with:
          subject-name: "${{ env.IMAGE }}"
          subject-digest: "${{ steps.push.outputs.digest }}"
          push-to-registry: true

      - name: "Create git tag"
        env:
          TAG: "${{ needs.resolve-version.outputs.tag }}"
        run: |
          git tag "$TAG"
          git push origin "$TAG"

      - name: "Create GitHub Release"
        env:
          GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}"
          TAG: "${{ needs.resolve-version.outputs.tag }}"
          VERSION: "${{ needs.resolve-version.outputs.version }}"
          DIGEST: "${{ steps.push.outputs.digest }}"
          IMAGE: "${{ env.IMAGE }}"
          OWNER: "${{ github.repository_owner }}"
        run: |
          RELEASE_NOTES=$(cat <<NOTES_EOF
          ## Container Image

          \`\`\`
          ${IMAGE}:${VERSION}
          \`\`\`

          **Digest:** \`${DIGEST}\`

          **Platforms:** linux/amd64, linux/arm64, linux/arm/v7

          ## Verify Provenance

          \`\`\`bash
          gh attestation verify oci://${IMAGE}:${VERSION} --owner ${OWNER}
          \`\`\`
          NOTES_EOF
          )

          gh release create "$TAG" \
            --title "SunGather $TAG" \
            --notes "$RELEASE_NOTES" \
            --generate-notes
```

- [ ] **Step 2: Verify workflow syntax**

Run: `actionlint .github/workflows/release.yaml` (if available), otherwise visual
review.

Check:
- `workflow_dispatch` with bump choice (patch/minor/major)
- Version resolution uses `v*` tag prefix (matches existing tags: v0.5.3, v0.5.2, etc.)
- Multi-platform: amd64, arm64, arm/v7 (matches legacy docker-image.yml)
- SBOM + provenance on push
- Attestation via `actions/attest-build-provenance`
- Git tag created and pushed
- Release notes include image ref, digest, platforms, verify command
- Permissions: contents:write, packages:write, id-token:write, attestations:write

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yaml
git commit -m "feat(ci): add release workflow with SBOM, attestation, and provenance"
```

---

### Task 4: Upgrade Trivy scan to scan published container image

The existing `trivy-scan.yaml` uses the repo-operator reusable workflow which does a
filesystem scan. Replace it with a workflow that scans the published container image
from GHCR, with GitHub issue management for found vulnerabilities (matching the pattern
from container-images).

**Files:**

- Modify: `.github/workflows/trivy-scan.yaml`

- [ ] **Step 1: Replace trivy-scan.yaml**

Replace `.github/workflows/trivy-scan.yaml` with:

```yaml
# yaml-language-server: $schema=https://raw.githubusercontent.com/SchemaStore/schemastore/master/src/schemas/json/github-workflow.json

name: "Trivy Vulnerability Scan"
on:
  schedule:
    - cron: "0 6 * * *"
  workflow_dispatch: {}
permissions:
  contents: "read"
  issues: "write"
  packages: "read"
env:
  IMAGE: "ghcr.io/${{ github.repository_owner }}/sungather:latest"
jobs:
  scan:
    name: "Scan container image"
    runs-on: "ubuntu-latest"
    steps:
      - name: "Checkout"
        uses: "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd" # v6

      - name: "Login to GHCR"
        uses: "docker/login-action@b45d80f862d83dbcd57f89517bcf500b2ab88fb2" # v4
        with:
          registry: "ghcr.io"
          username: "${{ github.actor }}"
          password: "${{ secrets.GITHUB_TOKEN }}"

      - name: "Check image exists"
        id: "check"
        env:
          GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}"
        run: |
          if docker pull "$IMAGE" > /dev/null 2>&1; then
            echo "exists=true" >> "$GITHUB_OUTPUT"
          else
            echo "::warning::Image $IMAGE not found in registry, skipping scan"
            echo "exists=false" >> "$GITHUB_OUTPUT"
          fi

      - name: "Scan for vulnerabilities"
        if: "steps.check.outputs.exists == 'true'"
        uses: "aquasecurity/trivy-action@57a97c7e7821a5776cebc9bb87c984fa69cba8f1" # v0.29
        with:
          image-ref: "${{ env.IMAGE }}"
          scanners: "vuln,secret,misconfig"
          format: "json"
          output: "trivy-results.json"
          severity: "CRITICAL,HIGH,MEDIUM"
          ignore-unfixed: true
          trivyignores: ".trivyignore.yaml"

      - name: "Generate table output"
        if: "steps.check.outputs.exists == 'true'"
        uses: "aquasecurity/trivy-action@57a97c7e7821a5776cebc9bb87c984fa69cba8f1" # v0.29
        with:
          image-ref: "${{ env.IMAGE }}"
          scanners: "vuln,secret,misconfig"
          format: "table"
          severity: "CRITICAL,HIGH,MEDIUM"
          ignore-unfixed: true
          trivyignores: ".trivyignore.yaml"

      - name: "Process results and manage issue"
        if: "steps.check.outputs.exists == 'true'"
        env:
          GH_TOKEN: "${{ secrets.GITHUB_TOKEN }}"
        run: |
          # Count vulnerabilities by severity
          CRITICAL=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL")] | length' trivy-results.json 2>/dev/null || echo 0)
          HIGH=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "HIGH")] | length' trivy-results.json 2>/dev/null || echo 0)
          MEDIUM=$(jq '[.Results[]?.Vulnerabilities[]? | select(.Severity == "MEDIUM")] | length' trivy-results.json 2>/dev/null || echo 0)
          TOTAL=$((CRITICAL + HIGH + MEDIUM))

          # Ensure labels exist
          gh label create "security" --color "B60205" --description "Security vulnerability" --force 2>/dev/null || true
          gh label create "trivy" --color "1D76DB" --description "Trivy scan finding" --force 2>/dev/null || true
          gh label create "critical" --color "B60205" --description "Critical severity" --force 2>/dev/null || true
          gh label create "high" --color "D93F0B" --description "High severity" --force 2>/dev/null || true
          gh label create "medium" --color "FBCA04" --description "Medium severity" --force 2>/dev/null || true

          # Find existing issue
          ISSUE_NUMBER=$(gh issue list --label "trivy" --state open --json number --jq '.[0].number' 2>/dev/null || echo "")

          if [ "$TOTAL" -eq 0 ]; then
            echo "::notice::No vulnerabilities found"
            # Close existing issue if open
            if [ -n "$ISSUE_NUMBER" ]; then
              gh issue close "$ISSUE_NUMBER" --comment "All vulnerabilities resolved. Scan: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
            fi
            exit 0
          fi

          # Build issue title
          TITLE="[Trivy] sungather:latest"
          SEVERITY_PARTS=""
          [ "$CRITICAL" -gt 0 ] && SEVERITY_PARTS="${SEVERITY_PARTS} ${CRITICAL} critical"
          [ "$HIGH" -gt 0 ] && SEVERITY_PARTS="${SEVERITY_PARTS} ${HIGH} high"
          [ "$MEDIUM" -gt 0 ] && SEVERITY_PARTS="${SEVERITY_PARTS} ${MEDIUM} medium"
          TITLE="${TITLE} -${SEVERITY_PARTS}"

          # Build vulnerability table for CRITICAL and HIGH
          TABLE="| CVE ID | Severity | Package | Installed | Fixed |\n|--------|----------|---------|-----------|-------|\n"
          TABLE+=$(jq -r '
            [.Results[]?.Vulnerabilities[]? | select(.Severity == "CRITICAL" or .Severity == "HIGH")]
            | sort_by(.Severity) | reverse[]
            | "| \(.VulnerabilityID) | \(.Severity) | \(.PkgName) | \(.InstalledVersion) | \(.FixedVersion // "N/A") |"
          ' trivy-results.json 2>/dev/null || echo "")

          # Build issue body
          BODY=$(cat <<BODY_EOF
          ## Trivy Vulnerability Scan Results

          **Image:** \`${{ env.IMAGE }}\`
          **Scan date:** $(date -u +"%Y-%m-%d %H:%M UTC")
          **Total:** ${TOTAL} (${CRITICAL} critical, ${HIGH} high, ${MEDIUM} medium)

          ### Critical & High Vulnerabilities

          $(echo -e "$TABLE")

          ${MEDIUM:+> **${MEDIUM} medium severity** vulnerabilities omitted. See [full scan results](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}).}

          ---
          *Auto-generated by [Trivy scan](${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }})*
          BODY_EOF
          )

          # Determine labels
          LABELS="security,trivy"
          [ "$CRITICAL" -gt 0 ] && LABELS="${LABELS},critical"
          [ "$HIGH" -gt 0 ] && LABELS="${LABELS},high"
          [ "$MEDIUM" -gt 0 ] && LABELS="${LABELS},medium"

          if [ -n "$ISSUE_NUMBER" ]; then
            gh issue edit "$ISSUE_NUMBER" --title "$TITLE" --body "$BODY"
            # Reset labels (remove old severity, apply new)
            gh issue edit "$ISSUE_NUMBER" --remove-label "critical,high,medium" 2>/dev/null || true
            gh issue edit "$ISSUE_NUMBER" --add-label "$LABELS"
            echo "::notice::Updated issue #$ISSUE_NUMBER"
          else
            gh issue create --title "$TITLE" --body "$BODY" --label "$LABELS"
            echo "::notice::Created new vulnerability issue"
          fi
```

- [ ] **Step 2: Verify workflow syntax**

Run: `actionlint .github/workflows/trivy-scan.yaml` (if available), otherwise visual
review.

Check:
- Daily schedule at 6 AM UTC (unchanged)
- Scans the published `ghcr.io/.../sungather:latest` image
- Checks image exists before scanning (handles first-run gracefully)
- JSON output for issue management + table output for logs
- Creates/updates GitHub issues with vulnerability details
- Auto-closes issue when all vulns resolved
- Labels: security, trivy, critical, high, medium

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/trivy-scan.yaml
git commit -m "feat(ci): upgrade Trivy scan to scan published container image with issue management"
```

---

### Task 5: Final validation and linting

- [ ] **Step 1: Run pre-commit linting**

Run: `pre-commit run --all-files`

Expected: All checks PASS

- [ ] **Step 2: Run actionlint on all workflows**

Run: `actionlint .github/workflows/*.yaml .github/workflows/*.yml` (if available)

Expected: No errors (warnings about SC2153/SC2034 are suppressed by `.github/actionlint.yaml`)

- [ ] **Step 3: Run tests to verify nothing broken**

Run: `python3 -m pytest tests/ -v`

Expected: All 24 tests PASS

- [ ] **Step 4: Verify final workflow file list**

Run: `ls .github/workflows/`

Expected:
```text
ci.yaml
release.yaml
trivy-scan.yaml
```

Only 3 files. `docker-image.yml` and `update-addon.yml` are gone.

- [ ] **Step 5: Commit any linting fixes**

If linting made auto-fixes:

```bash
git add -A
git commit -m "chore: fix linting issues in workflow files"
```
