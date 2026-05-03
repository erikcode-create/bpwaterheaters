#!/bin/bash
set -e
cd ~ || exit

echo "Setting Up Bench..."

pip install frappe-bench
bench -v init frappe-bench --skip-assets --skip-redis-config-generation --python "$(which python)"
cd ./frappe-bench || exit

echo "Get ERPNext..."
bench get-app --skip-assets erpnext "${GITHUB_WORKSPACE}"

echo "Generating POT file..."
bench generate-pot-file --app erpnext

cd ./apps/erpnext || exit

echo "Configuring git user..."
git config user.email "${GIT_AUTHOR_EMAIL:-dev@bpwaterheaters.com}"
git config user.name "${GIT_AUTHOR_NAME:-bpwh-pr-bot}"

echo "Setting the correct git remote..."
# Here, the git remote is a local file path by default. Push generated updates to the private repo.
git remote set-url origin "https://github.com/${GITHUB_REPOSITORY:-erikcode-create/bpwaterheaters}.git"

echo "Creating a new branch..."
isodate=$(date -u +"%Y-%m-%d")
branch_name="pot_${BASE_BRANCH}_${isodate}"
git checkout -b "${branch_name}"

echo "Commiting changes..."
git add erpnext/locale/main.pot
git commit -m "chore: update POT file"

gh auth setup-git
git push -u origin "${branch_name}"

echo "Creating a PR..."
gh pr create --fill --base "${BASE_BRANCH}" --head "${branch_name}" --reviewer ${PR_REVIEWER} -R "${GITHUB_REPOSITORY:-erikcode-create/bpwaterheaters}"
