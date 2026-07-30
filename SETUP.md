# Publish this profile

This directory is the future public `Anthony-Pan` profile repository. GitHub only renders a profile README when the repository is public, has the same name as the account, and contains a non-empty root `README.md`.

## Before the first push

The generators require Python 3.9 or newer. The committed SVG assets are already generated, so Python is only required when you change `profile.json`, `projects.json`, or the generation scripts.

Review `profile.json` and `projects.json`, then create the initial commit:

```sh
git add .
git commit -m "feat: add profile README"
```

Create and push the public special repository:

```sh
gh repo create Anthony-Pan --public --source=. --remote=origin --push
```

Run **Refresh profile assets** once from the Actions tab. The workflow already requests only `contents: write`, so keep the repository’s default `GITHUB_TOKEN` permissions restricted. If an organization or enterprise policy explicitly blocks that permission, ask its administrator for the narrow exception instead of widening the default for every workflow. Its first successful run replaces the placeholder contribution strip with your live contribution animation.

## Update content later

- Edit `profile.json` for the hero identity, stack, links, and status text.
- Edit `projects.json` for the cards displayed beneath GitHub statistics.
- Replace `assets/profile.png` to change the portrait.
- The workflow refreshes live project stars/languages and the contribution animation every 12 hours.

The workflow uses commit-pinned third-party Actions and the repository-scoped `GITHUB_TOKEN`; no personal access token or secret is required.
