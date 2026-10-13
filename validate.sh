#!/usr/bin/env bash

set -Eeuo pipefail

# Run from the repository root, regardless of the caller's directory.
REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

PASS=0
SKIP=0
FAIL=0

green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red()    { printf '\033[31m%s\033[0m\n' "$*"; }

run_check() {
    local description="$1"
    shift

    printf '\n==> %s\n' "$description"

    if "$@"; then
        green "PASS: $description"
        PASS=$((PASS + 1))
    else
        red "FAIL: $description"
        FAIL=$((FAIL + 1))
    fi
}

skip_check() {
    yellow "SKIP: $1"
    SKIP=$((SKIP + 1))
}

echo "=================================="
echo " Homelab Repository Validation"
echo "=================================="
echo "Repository: $REPO_ROOT"

# 1. Python syntax validation
PYTHON_FILES=()
while IFS= read -r -d '' file; do
    PYTHON_FILES+=("$file")
done < <(
    find . \\
        -path './.git' -prune -o \\
        -path '*/__pycache__' -prune -o \\
        -type f -name '*.py' -print0
)

if ((${#PYTHON_FILES[@]})); then
    run_check "Python syntax (${#PYTHON_FILES[@]} files)" \\
        python3 -m py_compile "${PYTHON_FILES[@]}"
else
    skip_check "Python syntax: no Python files found"
fi

# 2. Kustomize validation (does not contact or change the cluster)
if command -v kubectl >/dev/null 2>&1; then
    if [[ -f clusters/home/kustomization.yaml ]]; then
        run_check "Kustomize build: clusters/home" 
            kubectl kustomize clusters/home
    else
        skip_check "Kustomize: clusters/home/kustomization.yaml not found"
    fi

    # Validate each app-level Kustomization independently.
    while IFS= read -r -d '' file; do
        dir="$(dirname "$file")"
        [[ "$dir" == "clusters/home" ]] && continue
        run_check "Kustomize build: $dir" kubectl kustomize "$dir"
    done < <(find apps experiments -name kustomization.yaml -type f -print0 2>/dev/null || true)
else
    skip_check "Kustomize: kubectl is not installed"
fi

# 3. Helm chart validation (only if charts exist)
if ! command -v helm >/dev/null 2>&1; then
    if find . -name Chart.yaml -not -path './.git/*' -print -quit | grep -q .; then
        red "FAIL: Helm charts exist, but helm is not installed"
        FAIL=$((FAIL + 1))
    else
        skip_check "Helm lint: no Helm charts found"
    fi
else
    CHARTS=()
    while IFS= read -r -d '' file; do
        CHARTS+=("$(dirname "$file")")
    done < <(find . -name Chart.yaml -not -path './.git/*' -print0)

    if ((${#CHARTS[@]})); then
        for chart in "${CHARTS[@]}"; do
            run_check "Helm lint: $chart" helm lint "$chart"
        done
    else
        skip_check "Helm lint: no Helm charts found"
    fi
fi

# 4. Whitespace and merge-conflict checks
if git diff --check && git diff --cached --check; then
    green "PASS: Git whitespace checks"
    PASS=$((PASS + 1))
else
    red "FAIL: Git whitespace checks"
    FAIL=$((FAIL + 1))
fi

if grep -RInE '^(<<<<<<< |=======|>>>>>>> )' 
    README.md apps clusters docs experiments 
    --exclude='*.pyc' 2>/dev/null; then
    red "FAIL: Possible merge-conflict markers found"
    FAIL=$((FAIL + 1))
else
    green "PASS: No merge-conflict markers found"
    PASS=$((PASS + 1))
fi

echo
echo "=================================="
printf 'Results: %d passed, %d skipped, %d failed\n' 
    "$PASS" "$SKIP" "$FAIL"
echo "=================================="

if ((FAIL > 0)); then
    red "Validation failed. Fix the errors before committing."
    exit 1
fi

green "Validation successful!"
