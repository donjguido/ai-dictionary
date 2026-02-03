# Setup Guide

## For Publishing on GitHub

### 1. Create GitHub Repository

```bash
cd ai-dictionary
git init
git add .
git commit -m "Initial commit: AI Dictionary v1"
```

Then create a repo on GitHub and push:

```bash
git remote add origin https://github.com/yourusername/ai-dictionary.git
git branch -M main
git push -u origin main
```

### 2. Enable GitHub Pages

1. Go to your repo settings
2. Navigate to **Pages** (under Code and automation)
3. Set source to: **Deploy from a branch**
4. Branch: `main`, folder: `/site`
5. Save

Your site will be live at: `https://yourusername.github.io/ai-dictionary/`

### 3. Update Links

Replace `yourusername` in these files with your actual GitHub username:
- `README.md`
- `site/index.html`

### 4. Optional: Custom Domain

If you have a domain:
1. Add a `CNAME` file in `/site/` with your domain
2. Configure DNS with your provider
3. Update GitHub Pages settings

## For Local Development

To preview the site locally:

```bash
cd ai-dictionary/site
python3 -m http.server 8000
```

Then visit: `http://localhost:8000`

## For Contributors

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add new definitions.

---

Questions? Open an issue!
